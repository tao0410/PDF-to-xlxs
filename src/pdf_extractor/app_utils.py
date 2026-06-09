# -*- coding: utf-8 -*-
"""应用程序公共工具：路径解析与日志配置。"""

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler


def get_app_dir() -> str:
    """获取应用程序目录（兼容 PyInstaller --onefile）。

    Runtime 文件优先级：
    1. _MEIPASS — PyInstaller --onefile 打包后的资源解压目录
    2. EXE 所在目录 — 用户手动放置的 default.cfg 等外置文件
    """
    if getattr(sys, "frozen", False):
        # 资源优先从 MEIPASS 读取（内置于 EXE）
        # 用户可覆盖文件放在 EXE 所在目录
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_exe_dir() -> str:
    """获取 EXE 所在目录（用于可写文件：default.cfg、logs/、workspace.json）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def setup_logging() -> None:
    """配置日志：按日轮转，保留最近 30 天。"""
    log_dir = os.path.join(get_exe_dir(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app.log")

    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
