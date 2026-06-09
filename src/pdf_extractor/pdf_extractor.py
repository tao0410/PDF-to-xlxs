# -*- coding: utf-8 -*-
"""PDF 提取器：基于 pdfplumber，支持坐标/关键词/表格三种提取模式。"""

import logging
import re
from datetime import datetime
from typing import List, Optional, Tuple

import pdfplumber

logger = logging.getLogger(__name__)

DATE_PATTERNS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%Y年%m月%d日",
]

# 默认表格检测参数
DEFAULT_TABLE_SETTINGS = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "intersection_y_tolerance": 3,
    "intersection_x_tolerance": 3,
    "snap_y_tolerance": 3,
    "snap_x_tolerance": 3,
}


class PdfExtractor:
    """封装 pdfplumber，提供三种模式的 PDF 内容提取接口。"""

    def __init__(self, config: dict):
        """初始化 PDF 提取器。

        Args:
            config: 提取规则配置字典，支持 coordinate/keyword/table 三种模式
        """
        self.config = config
        # 兼容旧版 regions 和新版 rules
        self.rules = self._resolve_rules(config)

    @staticmethod
    def _resolve_rules(config: dict) -> List[dict]:
        """将配置统一解析为 rules 列表（兼容旧 regions 格式）。"""
        if "rules" in config and config["rules"]:
            return config["rules"]
        if "regions" in config and config["regions"]:
            rules = []
            for region in config["regions"]:
                rules.append({
                    "name": region.get("name", ""),
                    "mode": "coordinate",
                    "page_range": region.get("page_range", "第1页"),
                    "x1": region.get("x1", 0),
                    "y1": region.get("y1", 0),
                    "x2": region.get("x2", 0),
                    "y2": region.get("y2", 0),
                    "data_type": region.get("data_type", "文本"),
                })
            return rules
        return []

    # ── 公开接口 ────────────────────────────────────────────

    def extract_single(self, pdf_path: str) -> dict:
        """提取单个 PDF 文件内容。

        Returns:
            {source_file, status, error_msg, records: [{col: val}], field_issues: {col: msg}}
            records 至少包含一条记录；含 table 模式时可能有多条。
        """
        result = {
            "source_file": pdf_path,
            "status": "success",
            "error_msg": "",
            "records": [],
            "field_issues": {},
        }
        try:
            with pdfplumber.open(pdf_path) as pdf:
                self._extract_all(pdf, result)
        except Exception as e:
            result["status"] = "failed"
            result["error_msg"] = str(e)
            logger.exception("PDF 提取失败: %s", pdf_path)
        return result

    def extract_batch(self, pdf_paths: List[str]) -> List[dict]:
        """批量提取多个 PDF 文件内容。"""
        results = []
        for path in pdf_paths:
            try:
                results.append(self.extract_single(path))
            except Exception as e:
                results.append({
                    "source_file": path,
                    "status": "failed",
                    "error_msg": str(e),
                    "records": [],
                    "field_issues": {},
                })
        return results

    # ── 提取调度 ────────────────────────────────────────────

    def _extract_all(self, pdf, result: dict) -> None:
        """按 rules 逐条提取，协调单值字段与多行表格输出。"""
        # 第一步：分别收集各规则的提取结果
        scalar_results = {}   # {name: (value, issue)}  用于 coordinate/keyword
        table_results = {}    # {name: ([{col: val}], issue)}  用于 table

        for rule in self.rules:
            name = rule["name"]
            mode = rule.get("mode", "coordinate")
            try:
                if mode == "coordinate":
                    value, issue = self._extract_coordinate(pdf, rule)
                    scalar_results[name] = (value, issue)
                elif mode == "keyword":
                    value, issue = self._extract_keyword(pdf, rule)
                    scalar_results[name] = (value, issue)
                elif mode == "table":
                    rows, issue = self._extract_table(pdf, rule)
                    table_results[name] = (rows, issue)
                else:
                    scalar_results[name] = ("", f"未知提取模式: {mode}")
            except Exception as e:
                scalar_results[name] = ("", str(e))
                logger.warning("规则 %s 提取失败: %s", name, e)

        # 第二步：收集 issues
        for name, (val, issue) in scalar_results.items():
            if issue:
                result["field_issues"][name] = issue
        for name, (rows, issue) in table_results.items():
            if issue:
                result["field_issues"][name] = issue

        # 第三步：确定行数（以最大的 table 行数为准）
        max_table_rows = 1
        for name, (rows, issue) in table_results.items():
            if isinstance(rows, list) and len(rows) > max_table_rows:
                max_table_rows = len(rows)

        # 第四步：生成 records
        for row_idx in range(max_table_rows):
            record = {}
            # 先填 scalar 字段（每行重复相同的值）
            for name, (value, issue) in scalar_results.items():
                record[name] = value
            # 再填 table 字段（取第 row_idx 行）
            for name, (rows, issue) in table_results.items():
                if isinstance(rows, list) and row_idx < len(rows):
                    for col, val in rows[row_idx].items():
                        record[col] = val
                else:
                    # 该 table 行数不足，填空
                    pass
            result["records"].append(record)

        # 如果没有任何提取结果，至少返回一条空记录
        if not result["records"]:
            record = {}
            for name, (value, issue) in scalar_results.items():
                record[name] = value
            result["records"].append(record)

    # ── 坐标提取模式 ───────────────────────────────────────

    def _extract_coordinate(self, pdf, rule: dict) -> Tuple[str, Optional[str]]:
        """坐标模式：按 bbox 裁剪提取文本（保留原有功能）。"""
        pages = self._parse_page_range(rule.get("page_range", "第1页"), len(pdf.pages))
        x1 = float(rule.get("x1", 0))
        y1 = float(rule.get("y1", 0))
        x2 = float(rule.get("x2", 0))
        y2 = float(rule.get("y2", 0))

        texts = []
        for page_idx in pages:
            if page_idx < 0 or page_idx >= len(pdf.pages):
                continue
            page = pdf.pages[page_idx]
            # 规范化坐标
            cx1, cy1, cx2, cy2 = self._clip_bbox((x1, y1, x2, y2), page.width, page.height)
            bbox = self._bl_bbox_to_plumber(cx1, cy1, cx2, cy2, page.width, page.height)
            cropped = page.within_bbox(bbox)
            text = cropped.extract_text() or ""
            texts.append(text)

        raw = " ".join(texts).strip()
        cleaned = self._clean_text(raw)
        issue = self._validate_field(cleaned, rule.get("data_type", "文本"))
        return cleaned, issue

    # ── 关键词匹配模式 ─────────────────────────────────────

    def _extract_keyword(self, pdf, rule: dict) -> Tuple[str, Optional[str]]:
        """关键词模式：搜索关键词，按指定方向和范围提取邻近文字。

        Args:
            rule: {keyword, direction, range, page_range, data_type}

        Returns:
            (value, issue)
        """
        keyword = rule.get("keyword", "")
        if not keyword:
            return "", "未配置关键词"

        direction = rule.get("direction", "right")
        search_range = float(rule.get("range", 200))
        pages = self._parse_page_range(rule.get("page_range", "第1页"), len(pdf.pages))

        for page_idx in pages:
            if page_idx < 0 or page_idx >= len(pdf.pages):
                continue
            page = pdf.pages[page_idx]
            words = page.extract_words()
            if not words:
                continue

            # 搜索包含关键词的词块
            for w in words:
                text = w.get("text", "").strip()
                if keyword in text:
                    # 先尝试从同一词块内提取值（关键词后面部分）
                    value = self._extract_value_after_keyword(text, keyword)
                    if value:
                        cleaned = self._clean_text(value)
                        issue = self._validate_field(cleaned, rule.get("data_type", "文本"))
                        return cleaned, issue

                    # 词块内无值，按方向搜索邻近词块
                    nearby_text = self._search_direction(words, w, direction, search_range)
                    if nearby_text:
                        cleaned = self._clean_text(nearby_text)
                        issue = self._validate_field(cleaned, rule.get("data_type", "文本"))
                        return cleaned, issue

        return "", f"未找到关键词「{keyword}」"

    @staticmethod
    def _extract_value_after_keyword(text: str, keyword: str) -> str:
        """从包含关键词的文本块中提取值。"""
        idx = text.find(keyword)
        if idx == -1:
            return ""
        remaining = text[idx + len(keyword):]
        remaining = re.sub(r"^[：:\s]+", "", remaining)
        return remaining.strip()

    @staticmethod
    def _search_direction(words: list, anchor_word: dict, direction: str,
                           search_range: float) -> str:
        """从锚点词块沿指定方向搜索邻近词块，返回拼接文本。"""
        anchor_y_center = (anchor_word["top"] + anchor_word["bottom"]) / 2
        anchor_x_center = (anchor_word["x0"] + anchor_word["x1"]) / 2

        candidates = []
        for w in words:
            if w is anchor_word:
                continue
            wx = (w["x0"] + w["x1"]) / 2
            wy = (w["top"] + w["bottom"]) / 2

            if direction == "right":
                # 同行右侧，范围从 anchor.x1 到 anchor.x1 + range
                if (abs(wy - anchor_y_center) <= 8
                        and w["x0"] >= anchor_word["x1"] - 3
                        and w["x0"] <= anchor_word["x1"] + search_range):
                    candidates.append((w["x0"], w))
            elif direction == "below":
                # 同列下方
                if (abs(wx - anchor_x_center) <= 20
                        and w["top"] >= anchor_word["bottom"] - 3
                        and w["top"] <= anchor_word["bottom"] + search_range):
                    candidates.append((w["top"], w))
            elif direction == "left":
                # 同行左侧
                if (abs(wy - anchor_y_center) <= 8
                        and w["x1"] <= anchor_word["x0"] + 3
                        and w["x1"] >= anchor_word["x0"] - search_range):
                    candidates.append((-w["x0"], w))
            elif direction == "above":
                # 同列上方
                if (abs(wx - anchor_x_center) <= 20
                        and w["bottom"] <= anchor_word["top"] + 3
                        and w["bottom"] >= anchor_word["top"] - search_range):
                    candidates.append((-w["top"], w))

        if not candidates:
            return ""

        candidates.sort(key=lambda x: x[0])
        return " ".join(w.get("text", "").strip() for _, w in candidates)

    # ── 表格结构识别模式 ───────────────────────────────────

    def _extract_table(self, pdf, rule: dict) -> Tuple[List[dict], Optional[str]]:
        """表格模式：框选表格区域，使用 pdfplumber 原生 extract_tables() 识别。

        Args:
            rule: {table_region, column_mapping, page_range, table_settings?}

        Returns:
            (rows, issue) — rows 为 [{output_col: value}] 列表
        """
        table_region = rule.get("table_region", [])
        if not table_region or len(table_region) != 4:
            return [], "未配置表格区域"

        column_mapping = rule.get("column_mapping", {})
        if not column_mapping:
            return [], "未配置列名映射"

        # 合并用户自定义的 table_settings 到默认值
        table_settings = dict(DEFAULT_TABLE_SETTINGS)
        user_settings = rule.get("table_settings", {})
        if isinstance(user_settings, dict):
            table_settings.update(user_settings)

        pages = self._parse_page_range(rule.get("page_range", "第1页"), len(pdf.pages))

        all_rows = []
        for page_idx in pages:
            if page_idx < 0 or page_idx >= len(pdf.pages):
                continue
            page = pdf.pages[page_idx]

            # 裁剪表格区域
            tx1, ty1, tx2, ty2 = table_region
            bbox = self._bl_bbox_to_plumber(tx1, ty1, tx2, ty2, page.width, page.height)
            cropped = page.within_bbox(bbox)

            # 使用 pdfplumber 原生 extract_tables()
            tables = cropped.extract_tables(table_settings)
            if not tables:
                continue

            for table in tables:
                if not table or len(table) < 2:
                    # 至少需要表头 + 一行数据
                    continue
                # 第一行是表头
                headers = [re.sub(r"\s+", "", str(h or "")) for h in table[0]]
                # 建立表头到输出列名的映射
                header_to_output = {}
                for i, h in enumerate(headers):
                    # 精确匹配
                    if h in column_mapping:
                        header_to_output[i] = column_mapping[h]
                        continue
                    # 模糊匹配：用户配置的关键词是检测到表头的子串或反之
                    for src, dst in column_mapping.items():
                        src_norm = re.sub(r"\s+", "", src)
                        if src_norm in h or h in src_norm:
                            header_to_output[i] = dst
                            break
                if not header_to_output:
                    continue

                # 数据行
                for row in table[1:]:
                    if not row or all(c is None or str(c).strip() == "" for c in row):
                        continue
                    record = {}
                    for col_idx, output_name in header_to_output.items():
                        if col_idx < len(row):
                            val = str(row[col_idx] or "").strip()
                            record[output_name] = val
                        else:
                            record[output_name] = ""
                    if record:
                        all_rows.append(record)

        if not all_rows:
            return [], f"未在表格区域中识别到数据"

        return all_rows, None

    # ── 通用工具方法 ────────────────────────────────────────

    def _parse_page_range(self, page_range: str, total_pages: int) -> List[int]:
        """解析页面范围字符串，返回 0-based 页码列表。"""
        page_range = (page_range or "第1页").strip()
        if page_range in ("所有页", "全部", "all"):
            return list(range(total_pages))

        match = re.match(r"第\s*(\d+)\s*[-~至]\s*(\d+)\s*页", page_range)
        if match:
            start = int(match.group(1)) - 1
            end = int(match.group(2)) - 1
            return list(range(max(0, start), min(total_pages, end + 1)))

        match = re.match(r"第\s*(\d+)\s*页", page_range)
        if match:
            idx = int(match.group(1)) - 1
            if 0 <= idx < total_pages:
                return [idx]
            return []

        if page_range.isdigit():
            idx = int(page_range) - 1
            if 0 <= idx < total_pages:
                return [idx]
        return [0]

    @staticmethod
    def _bl_bbox_to_plumber(
        x1: float, y1: float, x2: float, y2: float, page_width: float, page_height: float
    ) -> Tuple[float, float, float, float]:
        """将框选坐标（左下角原点）转为 pdfplumber 的 (x0, top, x1, bottom)。"""
        bl_x1, bl_y1 = min(x1, x2), min(y1, y2)
        bl_x2, bl_y2 = max(x1, x2), max(y1, y2)
        pad = 1.0
        top = max(0.0, page_height - bl_y2 - pad)
        bottom = min(page_height, page_height - bl_y1 + pad)
        left = max(0.0, bl_x1 - pad)
        right = min(page_width, bl_x2 + pad)
        return PdfExtractor._clip_bbox((left, top, right, bottom), page_width, page_height)

    @staticmethod
    def _clip_bbox(bbox: Tuple[float, float, float, float], width: float, height: float):
        """将 bbox 裁剪到页面边界内。"""
        x1, y1, x2, y2 = bbox
        x1 = max(0, min(x1, width))
        x2 = max(0, min(x2, width))
        y1 = max(0, min(y1, height))
        y2 = max(0, min(y2, height))
        return x1, y1, x2, y2

    @staticmethod
    def _clean_text(text: str) -> str:
        """去除多余空格、换行符和特殊控制字符。"""
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _validate_field(self, value: str, data_type: str) -> Optional[str]:
        """校验字段格式，返回问题描述或 None。"""
        if not value:
            return "内容为空"
        if data_type == "数字":
            try:
                float(value.replace(",", "").replace("，", ""))
            except ValueError:
                return "数字格式错误"
        elif data_type == "日期":
            if not self._is_valid_date(value):
                return "日期格式错误"
        # "列表" 和 "文本" 类型不做格式校验
        return None

    @staticmethod
    def _is_valid_date(value: str) -> bool:
        """检查是否为可识别的日期格式。"""
        for fmt in DATE_PATTERNS:
            try:
                datetime.strptime(value, fmt)
                return True
            except ValueError:
                continue
        if re.match(r"^\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}", value):
            return True
        return False
