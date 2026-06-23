# -*- coding: utf-8 -*-
"""批量确认弹窗 (v2.2 demo-aligned)。"""

from typing import Dict, List, Optional
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QShortcut, QTableWidget, QVBoxLayout,
)
from table_utils import populate_table, table_to_records

SOURCE_COL = "来源文件"


class BatchConfirmDialog(QDialog):
    def __init__(self, columns: List[str], records: List[dict],
                 stats: dict, field_issues_map: Optional[Dict[int, Dict[str, str]]] = None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量确认提取内容")
        self.resize(580, 520)
        self.setMinimumSize(480, 360)
        self._cols = columns
        self._recs = records
        self._stats = stats
        self._im = field_issues_map or {}
        self._confirmed = False
        self._reextract = False
        self._init_ui()
        QShortcut("Return", self, self._on_confirm)

    def _init_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(24, 28, 24, 28)
        lo.setSpacing(14)
        lo.addWidget(QLabel("批量确认提取内容", objectName="section-title"))

        # Stats row with semantic colors
        s = self._stats
        sr = QHBoxLayout()
        sr.setSpacing(16)
        items = [
            ("共处理", str(s.get('total', 0)), "#0F172A"),
            ("成功", str(s.get('success', 0)), "#15803D"),
            ("失败", str(s.get('failed', 0)), "#DC2626"),
            ("总记录", str(s.get('records', 0)), "#0F172A"),
        ]
        for label, val, color in items:
            f = QFrame(objectName="stat-card")
            fl = QVBoxLayout(f)
            fl.setContentsMargins(16, 8, 16, 8)
            fl.setSpacing(2)
            vl = QLabel(val, objectName="stat-value", alignment=Qt.AlignCenter)
            vl.setStyleSheet(f"color: {color};")
            ll = QLabel(label, objectName="stat-label", alignment=Qt.AlignCenter)
            fl.addWidget(vl)
            fl.addWidget(ll)
            sr.addWidget(f)
        sr.addStretch()
        lo.addLayout(sr)

        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        lo.addWidget(self.table, 1)
        populate_table(self.table, self._cols, self._recs, self._im)

        bl = QHBoxLayout()
        bl.addStretch()
        for txt, obj in [("全部确认", "btn-primary"), ("重新提取全部", "btn-secondary"), ("取消", "btn-ghost")]:
            b = QPushButton(txt, objectName=obj)
            bl.addWidget(b)
        lo.addLayout(bl)

        btns = [bl.itemAt(i).widget() for i in range(bl.count()) if bl.itemAt(i).widget()]
        for b in btns:
            if b and b.text() == "全部确认":
                b.clicked.connect(self._on_confirm)
            elif b and b.text() == "重新提取全部":
                b.clicked.connect(self._on_reextract)
            elif b and b.text() == "取消":
                b.clicked.connect(self.reject)

    def _on_confirm(self):
        self._recs = table_to_records(self.table, self._cols)
        self._confirmed = True
        self.accept()

    def _on_reextract(self):
        self._reextract = True
        self.reject()

    def is_confirmed(self) -> bool: return self._confirmed
    def wants_reextract_all(self) -> bool: return self._reextract
    def get_records(self) -> List[dict]: return table_to_records(self.table, self._cols)
