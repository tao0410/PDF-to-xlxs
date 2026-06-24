# -*- coding: utf-8 -*-
"""Excel 生成选项弹窗 (v2.2 demo-aligned)。"""

import os
from typing import Optional
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QButtonGroup, QDialog, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QPushButton, QRadioButton, QVBoxLayout,
)


class ExcelOptionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("生成 Excel 文件")
        self.resize(520, 310)
        self.setMinimumSize(420, 260)
        self._tpl = None
        self._use = False
        self._cards = []
        self._group = QButtonGroup(self)
        self._init_ui()

    def _init_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(24, 28, 24, 28)
        lo.setSpacing(14)

        lo.addWidget(QLabel("选择 Excel 导出格式", objectName="section-title"))

        # Card-style radio options
        options = [
            ("default", "使用系统默认格式", "按配置的提取区域生成标准 .xlsx 文件，表头加粗，列宽自适应"),
            ("template", "加载自定义模板", "选择一个 .xlsx 文件作为格式模板"),
        ]
        for key, title, desc in options:
            card = QFrame(objectName=("radio-card-selected" if key == "default" else "radio-card"))
            cl = QVBoxLayout(card)
            cl.setSpacing(8)

            top = QHBoxLayout()
            top.setSpacing(10)
            rb = QRadioButton()
            rb.setChecked(key == "default")
            self._group.addButton(rb)
            top.addWidget(rb, alignment=Qt.AlignTop)
            tl = QVBoxLayout()
            tl.setSpacing(2)
            tl.addWidget(QLabel(title))
            tl.itemAt(0).widget().setStyleSheet("font-weight: 600; color: #0F172A; font-size: 14px;")
            dl = QLabel(desc)
            dl.setObjectName("hint-text")
            tl.addWidget(dl)
            top.addLayout(tl)
            top.addStretch()
            cl.addLayout(top)

            if key == "template":
                tr = QHBoxLayout()
                tr.addSpacing(28)
                self.btn_pick = QPushButton("选择模板文件...")
                self.btn_pick.setObjectName("btn-small")
                self.btn_pick.setEnabled(False)
                self.lbl_tpl = QLabel("未选择", objectName="hint-text")
                tr.addWidget(self.btn_pick)
                tr.addWidget(self.lbl_tpl)
                tr.addStretch()
                cl.addLayout(tr)

            card.mousePressEvent = lambda e, r=rb: r.setChecked(True)
            rb.toggled.connect(lambda checked, c=card: self._on_card_toggle(c, checked))
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

        self.btn_pick.clicked.connect(self._pick)

    def _on_card_toggle(self, card: QFrame, checked: bool):
        card.setObjectName("radio-card-selected" if checked else "radio-card")
        card.style().unpolish(card)
        card.style().polish(card)
        # Enable/disable template picker
        if self.btn_pick:
            self.btn_pick.setEnabled(checked and card.findChild(QRadioButton) is not None)

    def _pick(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择 Excel 模板文件", "", "Excel 文件 (*.xlsx)")
        if p:
            self._tpl = p
            self._use = True
            self.lbl_tpl.setText(os.path.basename(p))

    def _ok(self):
        for card, rb, key in self._cards:
            if rb.isChecked() and key == "template":
                self._use = True
                break
            elif rb.isChecked() and key == "default":
                self._use = False
                break
        self.accept()

    def use_template(self) -> bool: return self._use
    def get_template_path(self) -> Optional[str]: return self._tpl
