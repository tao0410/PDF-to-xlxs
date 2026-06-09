# -*- coding: utf-8 -*-
"""PDF 提取器：基于 pdfplumber，支持坐标/锚点/表格列三种提取模式。"""

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


class PdfExtractor:
    """封装 pdfplumber，提供三种模式的 PDF 内容提取接口。

    模式：
    - coordinate: 坐标框选提取（v1 兼容）
    - anchor: 锚点关键词提取
    - table_column: 表格列按行号提取
    """

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
        """按 rules 逐条提取，收集为一条 record。"""
        record = {}
        for rule in self.rules:
            name = rule["name"]
            mode = rule.get("mode", "coordinate")
            try:
                if mode == "coordinate":
                    value, issue = self._extract_coordinate(pdf, rule)
                elif mode == "anchor":
                    value, issue = self._extract_anchor(pdf, rule)
                elif mode == "table_column":
                    value, issue = self._extract_table_column(pdf, rule)
                else:
                    value, issue = "", f"未知提取模式: {mode}"
                record[name] = value
                if issue:
                    result["field_issues"][name] = issue
            except Exception as e:
                record[name] = ""
                result["field_issues"][name] = str(e)
                logger.warning("规则 %s 提取失败: %s", name, e)
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

    def _extract_anchor(self, pdf, rule: dict) -> Tuple[str, Optional[str]]:
        """锚点模式：搜索关键词，按指定方向和范围提取邻近文字。

        Args:
            rule: {anchor_text, direction, range, page_range, data_type}

        Returns:
            (value, issue)
        """
        anchor_text = rule.get("anchor_text", "")
        if not anchor_text:
            return "", "未配置锚点关键词"

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
                if anchor_text in text:
                    # 先尝试从同一词块内提取值（关键词后面部分）
                    value = self._extract_value_after_anchor(text, anchor_text)
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

        return "", f"未找到关键词「{anchor_text}」"

    @staticmethod
    def _extract_value_after_anchor(text: str, anchor_text: str) -> str:
        """从包含锚点关键词的文本块中提取值。

        例如: text="编号：TZY15-ECO-GY-000155", anchor_text="编号"
        → 去除 "编号" → 去除前导冒号 → "TZY15-ECO-GY-000155"
        """
        idx = text.find(anchor_text)
        if idx == -1:
            return ""
        remaining = text[idx + len(anchor_text):]
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

    @staticmethod
    def _cluster_words_to_rows(words: list) -> List[list]:
        """将词块按 Y 坐标聚类为行（容忍 ±12pt，合并续行并区分行间）。"""
        if not words:
            return []
        sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
        rows = []
        current_row = [sorted_words[0]]
        current_y = (sorted_words[0]["top"] + sorted_words[0]["bottom"]) / 2

        for w in sorted_words[1:]:
            w_y = (w["top"] + w["bottom"]) / 2
            if abs(w_y - current_y) <= 12:
                current_row.append(w)
            else:
                rows.append(current_row)
                current_row = [w]
                current_y = w_y
        rows.append(current_row)
        return rows

    # ── 表格列提取模式 ───────────────────────────────────

    def _extract_table_column(self, pdf, rule: dict) -> Tuple[str, Optional[str]]:
        """表格列模式：按列标题定位表格列，提取指定行的数据。

        Args:
            rule: {column_header, row_number, page_range}

        Returns:
            (value, issue)
        """
        column_header = rule.get("column_header", "")
        if not column_header:
            return "", "未配置列标题关键词"

        row_number = int(rule.get("row_number", 2))
        if row_number < 2:
            return "", "行号必须 >= 2（1=表头行）"

        pages = self._parse_page_range(rule.get("page_range", "第1页"), len(pdf.pages))

        for page_idx in pages:
            if page_idx < 0 or page_idx >= len(pdf.pages):
                continue
            page = pdf.pages[page_idx]
            words = page.extract_words()
            if not words:
                continue

            # 1. 找表头词块（优先匹配多列表头行，跳过孤立章节标题）
            header_word = None
            header_row_words = []
            candidates = [w for w in words if column_header in w.get("text", "")]
            for candidate in candidates:
                candidate_y = (candidate["top"] + candidate["bottom"]) / 2
                same_row = [
                    w for w in words
                    if abs((w["top"] + w["bottom"]) / 2 - candidate_y) <= 8
                ]
                if len(same_row) >= 3 or len(candidates) == 1:
                    header_word = candidate
                    header_row_words = same_row
                    break
            if not header_word:
                continue

            header_row_words.sort(key=lambda w: w["x0"])
            headers_info = [(w["x0"], w["x1"], w.get("text", "")) for w in header_row_words]

            # 2. 确定目标列的 X 范围（列间中点分割）
            col_left, col_right = None, None
            for i in range(len(headers_info)):
                hx0, hx1, htext = headers_info[i][0], headers_info[i][1], headers_info[i][2]
                if column_header in htext:
                    if i > 0:
                        col_left = (headers_info[i - 1][1] + hx0) / 2
                    else:
                        col_left = max(0, hx0 - 20)
                    if i + 1 < len(headers_info):
                        col_right = (hx1 + headers_info[i + 1][0]) / 2
                    else:
                        col_right = min(page.width, hx1 + 20)
                    break

            if col_left is None:
                continue

            # 3. 收集表头以下的词块，按 Y 聚类成行
            data_start_y = max(w["bottom"] for w in header_row_words) + 5
            data_words = [
                w for w in words
                if w["top"] >= data_start_y and w.get("text", "").strip()
            ]
            if not data_words:
                return "", f"列「{column_header}」下无数据行"

            rows = self._cluster_words_to_rows(data_words)

            # 4. 按 row_number 取指定行（row_number=2 → data_rows[0]）
            data_idx = row_number - 2  # 转为 0-based 数据行索引
            if data_idx < 0 or data_idx >= len(rows):
                return "", f"行号 {row_number} 超出数据范围（共 {len(rows)} 行数据）"

            target_row = rows[data_idx]
            col_words = []
            for w in target_row:
                w_x_center = (w["x0"] + w["x1"]) / 2
                if col_left <= w_x_center <= col_right:
                    col_words.append(w.get("text", "").strip())

            if not col_words:
                return "", f"第 {row_number} 行中未找到列「{column_header}」的数据"

            value = self._clean_text(" ".join(col_words))
            issue = self._validate_field(value, rule.get("data_type", "文本"))
            return value, issue

        return "", f"未找到列标题「{column_header}」"

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
