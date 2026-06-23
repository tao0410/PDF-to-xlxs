# -*- coding: utf-8 -*-
"""单文件确认弹窗 (v2.2 demo-aligned)。"""

from typing import Dict, List, Optional
from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QShortcut, QTableWidget, QVBoxLayout,
)
from table_utils import populate_table, table_to_records


class SingleConfirmDialog(QDialog):
    def __init__(self, filename: str, columns: List[str],
                 records: List[dict], field_issues: Optional[Dict[str, str]] = None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"确认提取内容 - {filename}")
        self.resize(520, 420)
        self.setMinimumSize(420, 300)
        self._cols = columns
        self._records = [dict(r) for r in records]
        self._issues = field_issues or {}
        self._confirmed = False
        self._reextract = False
        self._init_ui()
        QShortcut("Return", self, self._on_confirm)

    def _init_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(24, 28, 24, 28)
        lo.setSpacing(14)

        lo.addWidget(QLabel(
            f"提取结果（共 {len(self._records)} 条记录）"
            if len(self._records) > 1 else "提取结果："))

        self.table = QTableWidget()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        lo.addWidget(self.table, 1)

        rows = [{c: r.get(c, "") for c in self._cols} for r in self._records]
        im = {0: self._issues} if self._issues else {}
        populate_table(self.table, self._cols, rows, im)

        if self._issues:
            w = QLabel("⚠ " + "；".join(
                f"{k}字段{v}" for k, v in self._issues.items()) + "，请检查是否正确")
            w.setObjectName("warning-banner")
            w.setWordWrap(True)
            lo.addWidget(w)

        bl = QHBoxLayout()
        bl.addStretch()
        self.btn_confirm = QPushButton("确认", objectName="btn-primary")
        self.btn_reextract = QPushButton("重新提取", objectName="btn-secondary")
        self.btn_cancel = QPushButton("取消", objectName="btn-ghost")
        bl.addWidget(self.btn_confirm)
        bl.addWidget(self.btn_reextract)
        bl.addWidget(self.btn_cancel)
        lo.addLayout(bl)

        self.btn_confirm.clicked.connect(self._on_confirm)
        self.btn_reextract.clicked.connect(self._on_reextract)
        self.btn_cancel.clicked.connect(self.reject)

    def _on_confirm(self):
        self._records = table_to_records(self.table, self._cols)
        self._confirmed = True
        self.accept()

    def _on_reextract(self):
        self._reextract = True
        self.reject()

    def is_confirmed(self) -> bool: return self._confirmed
    def wants_reextract(self) -> bool: return self._reextract
    def get_records(self) -> List[dict]: return self._records
