# -*- coding: utf-8 -*-
"""会话管理器：工作区状态自动保存与恢复。"""

import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtCore import QTimer

from app_utils import get_exe_dir

logger = logging.getLogger(__name__)

SESSION_FILE = "workspace.json"
FILE_STATUSES = ("待处理", "处理中", "已确认", "已跳过")


class SessionManager:
    """管理工作区持久化：文件列表、已确认数据、配置路径。"""

    def __init__(self, save_callback: Optional[Callable[[], Dict[str, Any]]] = None):
        self._save_callback = save_callback
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(500)
        self._debounce_timer.timeout.connect(self._do_save)
        self._pending_data: Optional[Dict[str, Any]] = None

    @property
    def session_path(self) -> str:
        return os.path.join(get_exe_dir(), SESSION_FILE)

    def schedule_save(self, data: Dict[str, Any]) -> None:
        """防抖保存（500ms）。"""
        self._pending_data = data
        self._debounce_timer.start()

    def save_now(self, data: Dict[str, Any]) -> bool:
        """立即保存会话。"""
        try:
            with open(self.session_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("会话已保存")
            return True
        except Exception as e:
            logger.exception("保存会话失败: %s", e)
            return False

    def _do_save(self) -> None:
        if self._pending_data is not None:
            self.save_now(self._pending_data)

    def restore(self) -> Optional[Dict[str, Any]]:
        """恢复会话，损坏时返回 None。"""
        try:
            if not os.path.exists(self.session_path):
                return None
            with open(self.session_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                logger.warning("会话文件格式无效")
                return None
            logger.info("会话已恢复")
            return data
        except Exception as e:
            logger.exception("恢复会话失败: %s", e)
            return None

    def clear(self) -> None:
        """清除会话文件。"""
        try:
            if os.path.exists(self.session_path):
                os.remove(self.session_path)
        except Exception as e:
            logger.warning("清除会话失败: %s", e)

    @staticmethod
    def build_session_data(
        config: dict,
        config_path: str,
        files: List[dict],
        confirmed_records: List[dict],
    ) -> Dict[str, Any]:
        """构建会话数据结构。"""
        return {
            "config": config,
            "config_path": config_path,
            "files": files,
            "confirmed_records": confirmed_records,
        }

    @staticmethod
    def validate_restored_files(files: List[dict]) -> List[dict]:
        """校验恢复的文件路径，标记缺失文件。"""
        validated = []
        for item in files:
            path = item.get("path", "")
            exists = os.path.exists(path)
            validated.append({**item, "exists": exists})
        return validated
