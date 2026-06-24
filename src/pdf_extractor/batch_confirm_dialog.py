# -*- coding: utf-8 -*-
"""多文件模式下的批量确认窗口。"""

from typing import Dict, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from table_utils import populate_table, table_to_records, WordWrapDelegate

SOURCE_COL = "来源文件"


class BatchConfirmDialog(QDialog):
    """批量确认对话框。"""

    def __init__(
        self,
        columns: List[str],
        records: List[dict],
        stats: dict,
        field_issues_map: Optional[Dict[int, Dict[str, str]]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("批量确认提取内容")
        self.resize(900, 500)
        self._columns = columns
        self._records = records
        self._stats = stats
        self._field_issues_map = field_issues_map or {}
        self._confirmed = False
        self._reextract_all = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        s = self._stats
        layout.addWidget(
            QLabel(
                f"处理结果：共处理{s.get('total', 0)}个文件，"
                f"成功{s.get('success', 0)}个，失败{s.get('failed', 0)}个，"
                f"总记录数{s.get('records', 0)}条"
            )
        )

        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.CurrentChanged)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().sectionResized.connect(
            lambda _old, _new, _idx: self.table.resizeRowsToContents())
        layout.addWidget(self.table)

        populate_table(self.table, self._columns, self._records, self._field_issues_map, widget_type="item")

        delegate = WordWrapDelegate(self.table)
        for ci in range(self.table.columnCount()):
            self.table.setItemDelegateForColumn(ci, delegate)
        self.table.resizeRowsToContents()

        row_btn = QHBoxLayout()
        self.btn_add_row = QPushButton("添加行", objectName="btn-small")
        self.btn_delete_rows = QPushButton("删除选中行", objectName="btn-small")
        row_btn.addWidget(self.btn_add_row)
        row_btn.addWidget(self.btn_delete_rows)
        row_btn.addStretch()
        layout.addLayout(row_btn)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_confirm_all = QPushButton("全部确认", objectName="btn-primary")
        self.btn_reextract_all = QPushButton("重新提取全部", objectName="btn-secondary")
        self.btn_cancel = QPushButton("取消", objectName="btn-ghost")
        btn_layout.addWidget(self.btn_confirm_all)
        btn_layout.addWidget(self.btn_reextract_all)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        self.btn_add_row.clicked.connect(self._add_row)
        self.btn_delete_rows.clicked.connect(self._delete_rows)
        self.btn_confirm_all.clicked.connect(self._on_confirm_all)
        self.btn_reextract_all.clicked.connect(self._on_reextract_all)
        self.btn_cancel.clicked.connect(self.reject)

    def _add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col_idx in range(len(self._columns)):
            self.table.setItem(row, col_idx, QTableWidgetItem(""))

    def _delete_rows(self):
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "提示", "请先选择要删除的行")
            return
        for row in rows:
            self.table.removeRow(row)

    def _on_confirm_all(self):
        self._records = table_to_records(self.table, self._columns)
        self._confirmed = True
        self.accept()

    def _on_reextract_all(self):
        self._reextract_all = True
        self.reject()

    def is_confirmed(self) -> bool:
        return self._confirmed

    def wants_reextract_all(self) -> bool:
        return self._reextract_all

    def get_records(self) -> List[dict]:
        return table_to_records(self.table, self._columns)
