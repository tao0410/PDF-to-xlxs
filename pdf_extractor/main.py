# -*- coding: utf-8 -*-
"""应用程序入口：初始化 Qt 环境并创建主窗口。"""

import os
import sys

from PyQt5.QtWidgets import QApplication

from app_utils import get_app_dir, setup_logging
from main_window import MainWindow


def main() -> int:
    """启动应用程序。"""
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("PDF信息提取与Excel生成工具")
    app.setOrganizationName("PDFExtractor")

    style_path = os.path.join(get_app_dir(), "resources", "styles.qss")
    if os.path.exists(style_path):
        try:
            with open(style_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
        except Exception:
            pass

    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
