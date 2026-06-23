# -*- coding: utf-8 -*-
"""未处理文件提醒弹窗 (v2.2 demo-aligned)。"""

from typing import List
from PyQt5.QtWidgets import (
    QDialog, QFrame, QLabel, QPushButton, QVBoxLayout,
)


class UnprocessedDialog(QDialog):
    def __init__(self, unprocessed_files: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("存在未处理信息")
        self.resize(440, 330)
        self.setMinimumSize(360, 260)
        self._files = unprocessed_files
        self._choice = "cancel"
        self._init_ui()

    def _init_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(24, 28, 24, 28)
        lo.setSpacing(14)

        lo.addWidget(QLabel("存在未处理信息", objectName="section-title"))

        w = QLabel(f"⚠ 当前还有 {len(self._files)} 个文件未处理")
        w.setObjectName("warning-banner")
        w.setWordWrap(True)
        lo.addWidget(w)

        # File list with bg-hover (#F8FAFC) per demo
        f = QFrame()
        f.setStyleSheet(
            "QFrame { background: #F8FAFC; border-radius: 8px; padding: 12px 16px; }")
        fl = QVBoxLayout(f)
        fl.addWidget(QLabel("未处理文件："))
        fl.addWidget(QLabel("\n".join(f"• {x}" for x in self._files)))
        lo.addWidget(f)

        for txt, obj in [("继续生成", "btn-primary"), ("处理文件", "btn-secondary"), ("取消", "btn-ghost")]:
            b = QPushButton(txt, objectName=obj)
            b.setMinimumHeight(40)
            lo.addWidget(b)

        btns = [lo.itemAt(i).widget() for i in range(lo.count()) if isinstance(lo.itemAt(i).widget(), QPushButton)]
        for b in btns:
            if b and b.text() == "继续生成":
                b.clicked.connect(self._cont)
            elif b and b.text() == "处理文件":
                b.clicked.connect(self._proc)
            elif b and b.text() == "取消":
                b.clicked.connect(self.reject)

    def _cont(self):
        self._choice = "continue"
        self.accept()

    def _proc(self):
        self._choice = "process"
        self.accept()

    def get_choice(self) -> str: return self._choice
