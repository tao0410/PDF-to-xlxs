# -*- coding: utf-8 -*-
"""表格工具：异常单元格高亮等。"""

from typing import Dict, List, Optional, Set

from PyQt5.QtCore import QRect, QSize, Qt
from PyQt5.QtGui import QColor, QFont, QPainter
from PyQt5.QtWidgets import (
    QLineEdit, QPlainTextEdit, QStyle, QStyledItemDelegate,
    QTableWidget, QTableWidgetItem,
)

WARNING_BG = QColor("#FFF2CC")

# QLineEdit 嵌入表格时的样式：未聚焦时像普通文本，聚焦后显示绿色边框
LINEEDIT_FLAT_STYLE = """
QLineEdit {
    border: none; background: transparent; padding: 4px 8px;
    font-size: 15px; color: #334155;
}
QLineEdit:focus {
    border: 1px solid #15803D; background: #FFFFFF; border-radius: 3px;
}
"""
LINEEDIT_WARNING_STYLE = """
QLineEdit {
    border: none; background-color: #FFF2CC; padding: 4px 8px;
    font-size: 15px; color: #334155;
}
QLineEdit:focus {
    border: 1px solid #15803D; background-color: #FFF2CC; border-radius: 3px;
}
"""

# QPlainTextEdit 嵌入表格时的样式：多行自动换行，关闭滚动条，聚焦绿边框
TEXTEDIT_FLAT_STYLE = """
QPlainTextEdit {
    border: none; background: transparent; padding: 4px 8px;
    font-size: 15px; color: #334155;
}
QPlainTextEdit:focus {
    border: 1px solid #15803D; background: #FFFFFF; border-radius: 3px;
}
"""
TEXTEDIT_WARNING_STYLE = """
QPlainTextEdit {
    border: none; background-color: #FFF2CC; padding: 4px 8px;
    font-size: 15px; color: #334155;
}
QPlainTextEdit:focus {
    border: 1px solid #15803D; background-color: #FFF2CC; border-radius: 3px;
}
"""


class WordWrapDelegate(QStyledItemDelegate):
    """表格单元格 word-wrap 绘制 + QPlainTextEdit 编辑器（无浮窗）。"""

    def paint(self, painter, option, index):
        text = index.data() or ""
        painter.save()
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(QColor("#334155"))
        rect = option.rect.adjusted(4, 4, -4, -4)
        painter.drawText(rect, Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, text)
        painter.restore()

    def sizeHint(self, option, index):
        fm = option.fontMetrics
        text = index.data() or ""
        avail = max(option.rect.width() - 8, 50)
        bound = fm.boundingRect(QRect(0, 0, avail, 0), Qt.TextWordWrap | Qt.AlignLeft, text)
        return QSize(option.rect.width(), max(bound.height() + 16, fm.height() + 8))

    def createEditor(self, parent, option, index):
        editor = QPlainTextEdit(parent)
        editor.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        editor.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        editor.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        editor.setTabChangesFocus(True)
        return editor

    def setEditorData(self, editor, index):
        editor.setPlainText(index.data() or "")

    def setModelData(self, editor, model, index):
        model.setData(index, editor.toPlainText())

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


def populate_table(
    table: QTableWidget,
    columns: List[str],
    rows: List[dict],
    field_issues: Optional[Dict[int, Dict[str, str]]] = None,
    widget_type: str = "item",
) -> None:
    """填充表格数据，高亮异常单元格。

    widget_type:
      - "item"    : 默认 QTableWidgetItem（只读或 delegate 编辑）
      - "lineedit": 每格嵌入 QLineEdit（单行直接编辑，无浮窗）
      - "textedit": 每格嵌入 QPlainTextEdit（多行自动换行编辑）
    """
    table.setColumnCount(len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.setRowCount(len(rows))
    field_issues = field_issues or {}

    for row_idx, record in enumerate(rows):
        issues = field_issues.get(row_idx, {})
        for col_idx, col_name in enumerate(columns):
            value = record.get(col_name, "")
            text = str(value) if value is not None else ""

            if widget_type == "lineedit":
                widget = QLineEdit(text)
                if col_name in issues:
                    widget.setStyleSheet(LINEEDIT_WARNING_STYLE)
                else:
                    widget.setStyleSheet(LINEEDIT_FLAT_STYLE)
                table.setCellWidget(row_idx, col_idx, widget)
            elif widget_type == "textedit":
                widget = QPlainTextEdit()
                widget.setPlainText(text)
                if col_name in issues:
                    widget.setStyleSheet(TEXTEDIT_WARNING_STYLE)
                else:
                    widget.setStyleSheet(TEXTEDIT_FLAT_STYLE)
                table.setCellWidget(row_idx, col_idx, widget)
            else:
                item = QTableWidgetItem(text)
                if col_name in issues:
                    item.setBackground(WARNING_BG)
                table.setItem(row_idx, col_idx, item)


def table_to_records(table: QTableWidget, columns: List[str]) -> List[dict]:
    """从表格读取数据为字典列表（兼容 QPlainTextEdit / QLineEdit / QTableWidgetItem）。"""
    records = []
    for row in range(table.rowCount()):
        record = {}
        for col_idx, col_name in enumerate(columns):
            widget = table.cellWidget(row, col_idx)
            if isinstance(widget, QPlainTextEdit):
                record[col_name] = widget.toPlainText()
            elif isinstance(widget, QLineEdit):
                record[col_name] = widget.text()
            else:
                item = table.item(row, col_idx)
                record[col_name] = item.text() if item else ""
        records.append(record)
    return records


def highlight_empty_cells(table: QTableWidget, columns: List[str], skip_cols: Optional[Set[str]] = None) -> Dict[int, Dict[str, str]]:
    """高亮空单元格，返回 issues 字典（兼容 QPlainTextEdit / QLineEdit / QTableWidgetItem）。"""
    skip_cols = skip_cols or set()
    issues: Dict[int, Dict[str, str]] = {}
    for row in range(table.rowCount()):
        row_issues = {}
        for col_idx, col_name in enumerate(columns):
            if col_name in skip_cols:
                continue

            widget = table.cellWidget(row, col_idx)
            if isinstance(widget, QPlainTextEdit):
                text = widget.toPlainText().strip()
                if not text:
                    row_issues[col_name] = "内容为空"
                    widget.setStyleSheet(TEXTEDIT_WARNING_STYLE)
            elif isinstance(widget, QLineEdit):
                text = widget.text().strip()
                if not text:
                    row_issues[col_name] = "内容为空"
                    widget.setStyleSheet(LINEEDIT_WARNING_STYLE)
            else:
                item = table.item(row, col_idx)
                text = item.text().strip() if item else ""
                if not text:
                    row_issues[col_name] = "内容为空"
                    if item:
                        item.setBackground(WARNING_BG)
        if row_issues:
            issues[row] = row_issues
    return issues


def insert_row_with_lineedit(table: QTableWidget, columns: List[str], row: Optional[int] = None) -> None:
    """在表格中插入一行带 QLineEdit 控件的新行。"""
    if row is None:
        row = table.rowCount()
    table.insertRow(row)
    for col_idx in range(len(columns)):
        line_edit = QLineEdit("")
        line_edit.setStyleSheet(LINEEDIT_FLAT_STYLE)
        table.setCellWidget(row, col_idx, line_edit)
