# -*- coding: utf-8 -*-
"""配置管理器：提取规则的 JSON 读写。"""

import json
import logging
import os
from typing import Any, Dict, List

from app_utils import get_app_dir, get_exe_dir

logger = logging.getLogger(__name__)

DATA_TYPES = ("文本", "数字", "日期", "列表")
RULE_MODES = ("coordinate", "keyword", "table")
KEYWORD_DIRECTIONS = ("right", "below", "left", "above")
TABLE_STRATEGIES = ("lines", "lines_strict", "text", "explicit")

# 默认表格检测参数
DEFAULT_TABLE_SETTINGS = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "intersection_y_tolerance": 3,
    "intersection_x_tolerance": 3,
    "snap_y_tolerance": 3,
    "snap_x_tolerance": 3,
}


class ConfigManager:
    """提取规则配置的读取与保存。"""

    @staticmethod
    def get_default() -> dict:
        """获取默认配置。

        加载优先级：
        1. EXE 目录下的 default.cfg（用户可覆盖）
        2. _MEIPASS 内置 default.cfg（打包时内嵌）
        3. 硬编码内置默认值（兜底）
        """
        for base_dir in (get_exe_dir(), get_app_dir()):
            default_path = os.path.join(base_dir, "default.cfg")
            if os.path.exists(default_path):
                try:
                    with open(default_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if ConfigManager._validate_config(data):
                        return data
                except Exception as e:
                    logger.warning("读取 default.cfg 失败，尝试下一个: %s", e)

        return {
            "rule_name": "默认规则",
            "rules": [
                {
                    "name": "编号",
                    "mode": "coordinate",
                    "page_range": "第1页",
                    "x1": 100,
                    "y1": 200,
                    "x2": 150,
                    "y2": 220,
                    "data_type": "文本",
                },
                {
                    "name": "名称",
                    "mode": "coordinate",
                    "page_range": "第1页",
                    "x1": 160,
                    "y1": 200,
                    "x2": 300,
                    "y2": 220,
                    "data_type": "文本",
                },
                {
                    "name": "日期",
                    "mode": "coordinate",
                    "page_range": "第1页",
                    "x1": 310,
                    "y1": 200,
                    "x2": 400,
                    "y2": 220,
                    "data_type": "日期",
                },
                {
                    "name": "金额",
                    "mode": "coordinate",
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
        """获取输出列名列表。

        对于 coordinate/keyword 模式，直接取 rule 的 name。
        对于 table 模式，展开 column_mapping 的 values 为多个列名。
        """
        rules = ConfigManager._resolve_rules(config)
        names = []
        for rule in rules:
            if rule.get("mode") == "table":
                mapping = rule.get("column_mapping", {})
                if mapping:
                    names.extend(mapping.values())
                else:
                    names.append(rule.get("name", ""))
            else:
                names.append(rule.get("name", ""))
        return names

    @staticmethod
    def _resolve_rules(config: dict) -> List[dict]:
        """将配置解析为统一的 rules 列表（兼容旧 regions 格式）。"""
        if "rules" in config and config["rules"]:
            return config["rules"]
        if "regions" in config and config["regions"]:
            # 旧格式自动转换为新格式：mode 默认 coordinate
            rules = []
            for region in config["regions"]:
                rule = {
                    "name": region.get("name", ""),
                    "mode": "coordinate",
                    "page_range": region.get("page_range", "第1页"),
                    "x1": region.get("x1", 0),
                    "y1": region.get("y1", 0),
                    "x2": region.get("x2", 0),
                    "y2": region.get("y2", 0),
                    "data_type": region.get("data_type", "文本"),
                }
                rules.append(rule)
            return rules
        return []

    @staticmethod
    def _validate_config(config: Any) -> bool:
        """校验配置结构。

        新 schema（v2）: {rule_name, rules: [{name, mode, page_range, data_type, ...}]}
        旧 schema（v1）: {rule_name, regions: [{name, page_range, x1, y1, x2, y2, data_type}]}
        兼容读取 v1 配置。
        """
        if not isinstance(config, dict):
            return False
        if "rule_name" not in config:
            return False

        # 兼容旧版 regions 格式
        if "regions" in config:
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

        # 新版 rules 格式
        if "rules" not in config:
            return False
        if not isinstance(config["rules"], list):
            return False
        for rule in config["rules"]:
            if not isinstance(rule, dict):
                return False
            if not all(k in rule for k in ("name", "mode", "page_range", "data_type")):
                return False
            if rule["mode"] not in RULE_MODES:
                return False
            if rule["data_type"] not in DATA_TYPES:
                return False

            # 按模式校验必要字段
            if rule["mode"] == "coordinate":
                if not all(k in rule for k in ("x1", "y1", "x2", "y2")):
                    return False
            elif rule["mode"] == "keyword":
                if "keyword" not in rule:
                    return False
                if rule.get("direction", "right") not in KEYWORD_DIRECTIONS:
                    return False
            elif rule["mode"] == "table":
                if "table_region" not in rule or "column_mapping" not in rule:
                    return False
                if not isinstance(rule["table_region"], list) or len(rule["table_region"]) != 4:
                    return False
                if not isinstance(rule["column_mapping"], dict):
                    return False
        return True
