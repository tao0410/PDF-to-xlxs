# -*- coding: utf-8 -*-
"""Excel 生成器：基于 openpyxl 生成 .xlsx 文件。"""

import logging
import os
import re
from typing import List

import shutil

from openpyxl import Workbook, load_workbook
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

    def generate_from_template(
        self, data: List[dict], template_path: str, output_path: str,
        sort_key: str = "编号"
    ) -> bool:
        """基于模板文件生成 Excel。

        复制模板文件，在第一个 sheet 中找到数据开始行（通过表头关键词匹配），
        填入数据，保留模板的格式、样式和公式。

        Args:
            data: 要写入的数据列表
            template_path: 模板 .xlsx 文件路径
            output_path: 输出文件绝对路径
            sort_key: 排序字段

        Returns:
            成功返回 True，失败返回 False
        """
        try:
            # 复制模板文件
            out_dir = os.path.dirname(os.path.abspath(output_path))
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            shutil.copy2(template_path, output_path)

            # 打开副本进行编辑
            wb = load_workbook(output_path)
            ws = wb.active

            # 查找数据起始行：搜索表头行
            header_row = None
            for row_idx in range(1, min(ws.max_row + 1, 50)):
                row_vals = []
                for col_idx in range(1, ws.max_column + 1):
                    val = ws.cell(row=row_idx, column=col_idx).value
                    row_vals.append(str(val) if val is not None else "")
                # 检查该行是否包含所有列名
                matches = sum(
                    1 for col_name in self.columns
                    if any(col_name in rv or rv in col_name for rv in row_vals if rv)
                )
                if matches >= len(self.columns) * 0.5:  # 至少匹配一半列名
                    header_row = row_idx
                    break

            if header_row is None:
                # 未找到匹配表头，假定第一行为表头，从第二行开始写入
                header_row = 1

            data_start_row = header_row + 1

            # 建立列映射：模板列名 → 列索引
            col_map = {}
            for col_idx in range(1, ws.max_column + 1):
                template_col_name = str(
                    ws.cell(row=header_row, column=col_idx).value or ""
                ).strip()
                for our_col in self.columns:
                    if our_col in template_col_name or template_col_name in our_col:
                        col_map[our_col] = col_idx
                        break

            # 对未匹配的列，追加到末尾
            next_col = ws.max_column + 1
            for our_col in self.columns:
                if our_col not in col_map:
                    col_map[our_col] = next_col
                    next_col += 1

            # 复制表头行的样式作为数据行样式参考
            ref_style_row = data_start_row
            if data_start_row > ws.max_row:
                # 如果没有数据行，使用表头行的样式
                ref_style_row = header_row

            # 写入数据
            sorted_data = self._sort_data(data, sort_key)
            for row_offset, record in enumerate(sorted_data):
                row_idx = data_start_row + row_offset
                for col_name, col_idx in col_map.items():
                    cell = ws.cell(row=row_idx, column=col_idx)
                    cell.value = record.get(col_name, "")

            # 自动调整列宽
            for col_idx in range(1, ws.max_column + 1):
                max_len = 0
                for row in ws.iter_rows(
                    min_row=1, max_row=ws.max_row,
                    min_col=col_idx, max_col=col_idx
                ):
                    for cell in row:
                        if cell.value is not None:
                            max_len = max(max_len, len(str(cell.value)))
                if max_len > 0:
                    ws.column_dimensions[get_column_letter(col_idx)].width = min(
                        max_len + 4, 50
                    )

            wb.save(output_path)
            logger.info("Excel (模板) 已生成: %s", output_path)
            return True
        except PermissionError:
            logger.error("Excel 文件被占用，无法写入: %s", output_path)
            return False
        except OSError as e:
            if "No space left" in str(e) or getattr(e, "errno", None) == 28:
                logger.error("磁盘空间不足")
            else:
                logger.exception("基于模板生成 Excel 失败: %s", e)
            return False
        except Exception as e:
            logger.exception("基于模板生成 Excel 失败: %s", e)
            return False

    @staticmethod
    def default_filename() -> str:
        """生成默认文件名。"""
        from datetime import datetime

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"PDF信息汇总表_{ts}.xlsx"
