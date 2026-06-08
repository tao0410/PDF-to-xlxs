# -*- coding: utf-8 -*-
"""配置管理器：提取规则的 JSON 读写。"""

import json
import logging
import os
from typing import Any, Dict, List

from app_utils import get_app_dir

logger = logging.getLogger(__name__)

DATA_TYPES = ("文本", "数字", "日期")


class ConfigManager:
    """提取规则配置的读取与保存。"""

    @staticmethod
    def get_default() -> dict:
        """获取默认配置（编号、名称、日期、金额四个字段）。"""
        default_path = os.path.join(get_app_dir(), "default.cfg")
        if os.path.exists(default_path):
            try:
                with open(default_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if ConfigManager._validate_config(data):
                    return data
            except Exception as e:
                logger.warning("读取 default.cfg 失败，使用内置默认: %s", e)

        return {
            "rule_name": "默认规则",
            "regions": [
                {
                    "name": "编号",
                    "page_range": "第1页",
                    "x1": 100,
                    "y1": 200,
                    "x2": 150,
                    "y2": 220,
                    "data_type": "文本",
                },
                {
                    "name": "名称",
                    "page_range": "第1页",
                    "x1": 160,
                    "y1": 200,
                    "x2": 300,
                    "y2": 220,
                    "data_type": "文本",
                },
                {
                    "name": "日期",
                    "page_range": "第1页",
                    "x1": 310,
                    "y1": 200,
                    "x2": 400,
                    "y2": 220,
                    "data_type": "日期",
                },
                {
                    "name": "金额",
                    "page_range": "第1页",
                    "x1": 410,
                    "y1": 200,
                    "x2": 500,
                    "y2": 220,
                    "data_type": "数字",
                },
            ],
        }

    @staticmethod
    def save(config: dict, file_path: str) -> bool:
        """保存配置到 JSON 文件。"""
        try:
            if not ConfigManager._validate_config(config):
                logger.error("配置格式无效，无法保存")
                return False
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info("配置已保存: %s", file_path)
            return True
        except Exception as e:
            logger.exception("保存配置失败: %s", e)
            return False

    @staticmethod
    def load(file_path: str) -> dict:
        """从 JSON 文件加载配置，失败时返回默认配置。"""
        try:
            if not os.path.exists(file_path):
                logger.warning("配置文件不存在: %s，使用默认配置", file_path)
                return ConfigManager.get_default()
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not ConfigManager._validate_config(data):
                logger.warning("配置文件格式无效: %s，使用默认配置", file_path)
                return ConfigManager.get_default()
            logger.info("配置已加载: %s", file_path)
            return data
        except Exception as e:
            logger.exception("加载配置失败: %s，使用默认配置", e)
            return ConfigManager.get_default()

    @staticmethod
    def get_column_names(config: dict) -> List[str]:
        """获取提取区域名称列表。"""
        return [r["name"] for r in config.get("regions", [])]

    @staticmethod
    def _validate_config(config: Any) -> bool:
        """校验配置结构。"""
        if not isinstance(config, dict):
            return False
        if "rule_name" not in config or "regions" not in config:
            return False
        if not isinstance(config["regions"], list):
            return False
        for region in config["regions"]:
            if not isinstance(region, dict):
                return False
            required = ("name", "page_range", "x1", "y1", "x2", "y2", "data_type")
            if not all(k in region for k in required):
                return False
            if region["data_type"] not in DATA_TYPES:
                return False
        return True
