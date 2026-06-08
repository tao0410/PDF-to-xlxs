# -*- coding: utf-8 -*-
"""单文件模式下的内容确认窗口。"""

from typing import Dict, List, Optional

from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)

from table_utils import highlight_empty_cells, populate_table, table_to_records


class SingleConfirmDialog(QDialog):
    """单个文件确认对话框。"""

    def __init__(
        self,
        filename: str,
        columns: List[str],
        record: dict,
        field_issues: Optional[Dict[str, str]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"确认提取内容 - {filename}")
        self.resize(600, 350)
        self._columns = columns
        self._record = dict(record)
        self._field_issues = field_issues or {}
        self._confirmed = False
        self._reextract = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("提取结果："))

        self.table = QTableWidget()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        rows = [{col: self._record.get(col, "") for col in self._columns}]
        issues_map = {0: self._field_issues} if self._field_issues else {}
        populate_table(self.table, self._columns, rows, issues_map)

        if self._field_issues:
            warnings = "；".join(f"{k}字段{ v}" for k, v in self._field_issues.items())
            layout.addWidget(QLabel(f"⚠ {warnings}，请检查是否正确"))

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_confirm = QPushButton("确认")
        self.btn_reextract = QPushButton("重新提取")
        self.btn_cancel = QPushButton("取消")
        btn_layout.addWidget(self.btn_confirm)
        btn_layout.addWidget(self.btn_reextract)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        self.btn_confirm.clicked.connect(self._on_confirm)
        self.btn_reextract.clicked.connect(self._on_reextract)
        self.btn_cancel.clicked.connect(self.reject)

    def _on_confirm(self):
        records = table_to_records(self.table, self._columns)
        if records:
            self._record = records[0]
        self._confirmed = True
        self.accept()

    def _on_reextract(self):
        self._reextract = True
        self.reject()

    def is_confirmed(self) -> bool:
        return self._confirmed

    def wants_reextract(self) -> bool:
        return self._reextract

    def get_record(self) -> dict:
        return self._record
