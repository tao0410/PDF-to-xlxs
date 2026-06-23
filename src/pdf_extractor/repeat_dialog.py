# -*- coding: utf-8 -*-
"""重复内容检测弹窗 (v2.2 demo-aligned)。"""

from typing import List
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QRadioButton, QTableWidget, QVBoxLayout,
)
from table_utils import populate_table


class RepeatDialog(QDialog):
    def __init__(self, columns: List[str], records: List[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("重复内容检测")
        self.resize(520, 420)
        self.setMinimumSize(420, 340)
        self._cols = columns
        self._recs = records
        self._choice = "overwrite"  # default per demo
        self._cards = []  # radio card frames
        self._init_ui()

    def _init_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(24, 28, 24, 28)
        lo.setSpacing(14)

        lo.addWidget(QLabel("重复内容检测", objectName="section-title"))

        w = QLabel(f"⚠ 检测到 {len(self._recs)} 条内容与已确认内容完全重复")
        w.setObjectName("warning-banner")
        w.setWordWrap(True)
        lo.addWidget(w)

        self.table = QTableWidget()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        lo.addWidget(self.table, 1)
        populate_table(self.table, self._cols,
                       [{c: r.get(c, "") for c in self._cols} for r in self._recs])

        lo.addWidget(QLabel("请选择处理方式："))

        # Card-style radio items
        options = [
            ("overwrite", "覆盖", "用新提取内容替换已确认内容中的对应记录"),
            ("skip", "放弃", "跳过该条记录，不修改已确认内容"),
            ("add", "新增", "保留该条记录（将导致内容重复）"),
        ]
        for key, title, desc in options:
            card = QFrame(objectName=("radio-card-selected" if key == "overwrite" else "radio-card"))
            cl = QHBoxLayout(card)
            cl.setContentsMargins(12, 12, 16, 12)
            cl.setSpacing(10)

            rb = QRadioButton()
            rb.setChecked(key == "overwrite")
            cl.addWidget(rb, alignment=Qt.AlignTop)

            tl = QVBoxLayout()
            tl.setSpacing(2)
            tl.addWidget(QLabel(title))
            tl.itemAt(0).widget().setStyleSheet("font-weight: 600; color: #0F172A; font-size: 14px;")
            dl = QLabel(desc)
            dl.setObjectName("hint-text")
            tl.addWidget(dl)
            cl.addLayout(tl)
            cl.addStretch()

            # Click card to select radio
            card.mousePressEvent = lambda e, r=rb: r.setChecked(True)
            rb.toggled.connect(lambda checked, c=card, k=key: self._on_card_toggle(c, checked))

            lo.addWidget(card)
            self._cards.append((card, rb, key))

        bl = QHBoxLayout()
        bl.addStretch()
        for txt, obj in [("确定", "btn-primary"), ("取消", "btn-ghost")]:
            b = QPushButton(txt, objectName=obj)
            bl.addWidget(b)
        lo.addLayout(bl)

        btns = [bl.itemAt(i).widget() for i in range(bl.count()) if bl.itemAt(i).widget()]
        for b in btns:
            if b and b.text() == "确定":
                b.clicked.connect(self._ok)
            elif b and b.text() == "取消":
                b.clicked.connect(self.reject)

    def _on_card_toggle(self, card: QFrame, checked: bool):
        card.setObjectName("radio-card-selected" if checked else "radio-card")
        card.style().unpolish(card)
        card.style().polish(card)

    def _ok(self):
        for card, rb, key in self._cards:
            if rb.isChecked():
                self._choice = key
                break
        self.accept()

    def get_choice(self) -> str: return self._choice
