# -*- coding: utf-8 -*-
"""表格工具：异常单元格高亮等。"""

from typing import Dict, List, Optional, Set

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem

WARNING_BG = QColor("#FEF3C7")


def populate_table(
    table: QTableWidget,
    columns: List[str],
    rows: List[dict],
    field_issues: Optional[Dict[int, Dict[str, str]]] = None,
) -> None:
    """填充表格数据，高亮异常单元格。"""
    table.setColumnCount(len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.setRowCount(len(rows))
    field_issues = field_issues or {}

    for row_idx, record in enumerate(rows):
        issues = field_issues.get(row_idx, {})
        for col_idx, col_name in enumerate(columns):
            value = record.get(col_name, "")
            item = QTableWidgetItem(str(value) if value is not None else "")
            if col_name in issues:
                item.setBackground(WARNING_BG)
            table.setItem(row_idx, col_idx, item)


def table_to_records(table: QTableWidget, columns: List[str]) -> List[dict]:
    """从表格读取数据为字典列表。"""
    records = []
    for row in range(table.rowCount()):
        record = {}
        for col_idx, col_name in enumerate(columns):
            item = table.item(row, col_idx)
            record[col_name] = item.text() if item else ""
        records.append(record)
    return records


def highlight_empty_cells(table: QTableWidget, columns: List[str], skip_cols: Optional[Set[str]] = None) -> Dict[int, Dict[str, str]]:
    """高亮空单元格，返回 issues 字典。"""
    skip_cols = skip_cols or set()
    issues: Dict[int, Dict[str, str]] = {}
    for row in range(table.rowCount()):
        row_issues = {}
        for col_idx, col_name in enumerate(columns):
            if col_name in skip_cols:
                continue
            item = table.item(row, col_idx)
            text = item.text().strip() if item else ""
            if not text:
                row_issues[col_name] = "内容为空"
                if item:
                    item.setBackground(WARNING_BG)
        if row_issues:
            issues[row] = row_issues
    return issues
