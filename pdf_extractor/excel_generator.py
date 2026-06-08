# -*- coding: utf-8 -*-
"""Excel 生成器：基于 openpyxl 生成 .xlsx 文件。"""

import logging
import os
import re
from typing import List

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

HEADER_FILL = PatternFill(start_color="E5F3FF", end_color="E5F3FF", fill_type="solid")
HEADER_FONT = Font(bold=True)


class ExcelGenerator:
    """封装 openpyxl，提供统一的 Excel 生成接口。"""

    def __init__(self, columns: List[str]):
        """初始化 Excel 生成器。

        Args:
            columns: Excel 列标题列表，包含"来源文件"列
        """
        self.columns = columns

    def generate(self, data: List[dict], output_path: str, sort_key: str = "编号") -> bool:
        """生成 Excel 文件。

        Args:
            data: 要写入的数据列表
            output_path: 输出文件绝对路径
            sort_key: 排序字段名称，默认按"编号"升序

        Returns:
            生成成功返回 True，失败返回 False
        """
        try:
            sorted_data = self._sort_data(data, sort_key)
            wb = Workbook()
            ws = wb.active
            ws.title = "PDF信息汇总"

            # 写入表头
            for col_idx, col_name in enumerate(self.columns, start=1):
                cell = ws.cell(row=1, column=col_idx, value=col_name)
                cell.fill = HEADER_FILL
                cell.font = HEADER_FONT

            # 写入数据
            for row_idx, record in enumerate(sorted_data, start=2):
                for col_idx, col_name in enumerate(self.columns, start=1):
                    ws.cell(row=row_idx, column=col_idx, value=record.get(col_name, ""))

            # 自动列宽
            for col_idx, col_name in enumerate(self.columns, start=1):
                max_len = len(str(col_name))
                for row in ws.iter_rows(
                    min_row=2, max_row=ws.max_row, min_col=col_idx, max_col=col_idx
                ):
                    for cell in row:
                        if cell.value is not None:
                            max_len = max(max_len, len(str(cell.value)))
                ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 4, 50)

            out_dir = os.path.dirname(os.path.abspath(output_path))
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            wb.save(output_path)
            logger.info("Excel 已生成: %s", output_path)
            return True
        except PermissionError:
            logger.error("Excel 文件被占用，无法写入: %s", output_path)
            return False
        except OSError as e:
            if "No space left" in str(e) or getattr(e, "errno", None) == 28:
                logger.error("磁盘空间不足")
            else:
                logger.exception("生成 Excel 失败: %s", e)
            return False
        except Exception as e:
            logger.exception("生成 Excel 失败: %s", e)
            return False

    @staticmethod
    def _sort_data(data: List[dict], sort_key: str) -> List[dict]:
        """按编号升序排序（支持数字前缀）。"""

        def sort_value(record: dict):
            val = str(record.get(sort_key, ""))
            num_match = re.search(r"\d+", val)
            if num_match:
                return (0, int(num_match.group()), val)
            return (1, 0, val)

        return sorted(data, key=sort_value)

    @staticmethod
    def default_filename() -> str:
        """生成默认文件名。"""
        from datetime import datetime

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"PDF信息汇总表_{ts}.xlsx"
