# -*- coding: utf-8 -*-
"""PDF 提取器：基于 pdfplumber 按坐标提取文本。"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pdfplumber

logger = logging.getLogger(__name__)

DATE_PATTERNS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%Y年%m月%d日",
]


class PdfExtractor:
    """封装 pdfplumber，提供统一的 PDF 内容提取接口。"""

    def __init__(self, config: dict):
        """初始化 PDF 提取器。

        Args:
            config: 提取规则配置字典，格式由 ConfigManager 定义
        """
        self.config = config
        self.regions = config.get("regions", [])

    def extract_single(self, pdf_path: str) -> dict:
        """提取单个 PDF 文件内容。

        Args:
            pdf_path: PDF 文件绝对路径

        Returns:
            提取结果字典，包含所有配置字段的值和提取状态
        """
        result = {
            "source_file": pdf_path,
            "status": "success",
            "error_msg": "",
            "fields": {},
            "field_issues": {},
        }
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for region in self.regions:
                    name = region["name"]
                    try:
                        value, issue = self._extract_region(pdf, region)
                        result["fields"][name] = value
                        if issue:
                            result["field_issues"][name] = issue
                    except Exception as e:
                        result["fields"][name] = ""
                        result["field_issues"][name] = str(e)
                        logger.warning("区域 %s 提取失败: %s", name, e)
        except Exception as e:
            result["status"] = "failed"
            result["error_msg"] = str(e)
            logger.exception("PDF 提取失败: %s", pdf_path)
        return result

    def extract_batch(self, pdf_paths: List[str]) -> List[dict]:
        """批量提取多个 PDF 文件内容。

        Args:
            pdf_paths: PDF 文件绝对路径列表

        Returns:
            提取结果列表，每个元素对应一个 PDF 文件的提取结果
        """
        results = []
        for path in pdf_paths:
            try:
                results.append(self.extract_single(path))
            except Exception as e:
                results.append(
                    {
                        "source_file": path,
                        "status": "failed",
                        "error_msg": str(e),
                        "fields": {},
                        "field_issues": {},
                    }
                )
        return results

    def _extract_region(self, pdf, region: dict) -> Tuple[str, Optional[str]]:
        """从 PDF 中提取单个区域内容。"""
        pages = self._parse_page_range(region.get("page_range", "第1页"), len(pdf.pages))
        x1, y1, x2, y2 = self._normalize_bbox(region, pdf, pages[0] if pages else 0)

        texts = []
        for page_idx in pages:
            if page_idx < 0 or page_idx >= len(pdf.pages):
                continue
            page = pdf.pages[page_idx]
            bbox = self._bl_bbox_to_plumber(x1, y1, x2, y2, page.width, page.height)
            cropped = page.within_bbox(bbox)
            text = cropped.extract_text() or ""
            texts.append(text)

        raw = " ".join(texts).strip()
        cleaned = self._clean_text(raw)
        issue = self._validate_field(cleaned, region.get("data_type", "文本"))
        return cleaned, issue

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

        # 纯数字
        if page_range.isdigit():
            idx = int(page_range) - 1
            if 0 <= idx < total_pages:
                return [idx]
        return [0]

    def _normalize_bbox(self, region: dict, pdf, default_page: int) -> Tuple[float, float, float, float]:
        """规范化坐标，确保在页面范围内。"""
        x1 = float(region.get("x1", 0))
        y1 = float(region.get("y1", 0))
        x2 = float(region.get("x2", 0))
        y2 = float(region.get("y2", 0))
        if pdf.pages:
            page = pdf.pages[min(default_page, len(pdf.pages) - 1)]
            x1, y1, x2, y2 = self._clip_bbox((x1, y1, x2, y2), page.width, page.height)
        return x1, y1, x2, y2

    @staticmethod
    def _bl_bbox_to_plumber(
        x1: float, y1: float, x2: float, y2: float, page_width: float, page_height: float
    ) -> Tuple[float, float, float, float]:
        """将框选配置坐标（左下角原点）转为 pdfplumber 的 (x0, top, x1, bottom)。"""
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
        # 宽松匹配 YYYY-MM-DD 变体
        if re.match(r"^\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}", value):
            return True
        return False
