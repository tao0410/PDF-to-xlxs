# -*- coding: utf-8 -*-
"""提取规则配置窗口。"""

import logging
import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config_manager import (
    DATA_TYPES,
    DEFAULT_TABLE_SETTINGS,
    KEYWORD_DIRECTIONS,
    TABLE_STRATEGIES,
    ConfigManager,
)
from pdf_preview_dialog import PdfPreviewDialog

logger = logging.getLogger(__name__)

LIST_COLUMNS = ["字段名", "提取模式", "页面范围", "数据类型"]


class ConfigDialog(QDialog):
    """提取规则配置对话框。

    左侧：规则列表（QTableWidget）
    右侧：模式参数面板（根据模式动态切换）
    """

    def __init__(self, config: dict, config_path: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("配置提取规则")
        self.resize(950, 600)
        self.config = dict(config)
        self.config_path = config_path
        self.rules = list(self.config.get("rules", []))
        # 兼容旧 regions 格式
        if not self.rules and "regions" in self.config:
            for r in self.config["regions"]:
                self.rules.append({
                    "name": r.get("name", ""),
                    "mode": "coordinate",
                    "page_range": r.get("page_range", "第1页"),
                    "x1": r.get("x1", 0), "y1": r.get("y1", 0),
                    "x2": r.get("x2", 0), "y2": r.get("y2", 0),
                    "data_type": r.get("data_type", "文本"),
                })
        self._preview_dlg = None
        self._init_ui()
        self._refresh_table()

    # ── UI 搭建 ───────────────────────────────────────────

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # 规则名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("规则名称："))
        self.edit_rule_name = QLineEdit()
        self.edit_rule_name.setText(self.config.get("rule_name", "默认规则"))
        name_layout.addWidget(self.edit_rule_name)
        main_layout.addLayout(name_layout)

        # 中间：左右分栏
        body_layout = QHBoxLayout()

        # 左侧：规则列表
        left_panel = QVBoxLayout()
        self.rule_table = QTableWidget()
        self.rule_table.setColumnCount(len(LIST_COLUMNS))
        self.rule_table.setHorizontalHeaderLabels(LIST_COLUMNS)
        self.rule_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rule_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rule_table.setSelectionMode(QTableWidget.SingleSelection)
        self.rule_table.setMaximumWidth(420)
        left_panel.addWidget(self.rule_table)

        rule_btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("添加")
        self.btn_delete = QPushButton("删除")
        self.btn_up = QPushButton("上移")
        self.btn_down = QPushButton("下移")
        rule_btn_layout.addWidget(self.btn_add)
        rule_btn_layout.addWidget(self.btn_delete)
        rule_btn_layout.addWidget(self.btn_up)
        rule_btn_layout.addWidget(self.btn_down)
        left_panel.addLayout(rule_btn_layout)

        body_layout.addLayout(left_panel)

        # 右侧：参数面板（动态内容）
        self.param_stack = QVBoxLayout()
        self.grp_coordinate = self._build_coordinate_panel()
        self.grp_keyword = self._build_keyword_panel()
        self.grp_table = self._build_table_panel()
        self.param_stack.addWidget(self.grp_coordinate)
        self.param_stack.addWidget(self.grp_keyword)
        self.param_stack.addWidget(self.grp_table)
        self.param_stack.addStretch()
        body_layout.addLayout(self.param_stack)

        main_layout.addLayout(body_layout)

        # 底部按钮
        bottom_layout = QHBoxLayout()
        self.btn_save = QPushButton("保存")
        self.btn_save_as = QPushButton("另存为")
        self.btn_cancel = QPushButton("取消")
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_save)
        bottom_layout.addWidget(self.btn_save_as)
        bottom_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(bottom_layout)

        # 信号连接
        self.rule_table.currentCellChanged.connect(self._on_row_changed)
        self.btn_add.clicked.connect(self._add_rule)
        self.btn_delete.clicked.connect(self._delete_rule)
        self.btn_up.clicked.connect(lambda: self._move_rule(-1))
        self.btn_down.clicked.connect(lambda: self._move_rule(1))
        self.btn_save.clicked.connect(self._save)
        self.btn_save_as.clicked.connect(self._save_as)
        self.btn_cancel.clicked.connect(self.reject)

        # 默认选中第一行
        if self.rule_table.rowCount() > 0:
            self.rule_table.selectRow(0)

    def _build_coordinate_panel(self) -> QGroupBox:
        """坐标提取参数面板。"""
        grp = QGroupBox("坐标提取参数")
        layout = QVBoxLayout(grp)
        grid = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("X1:"))
        self.ctx_x1 = QSpinBox(); self.ctx_x1.setRange(0, 9999); row1.addWidget(self.ctx_x1)
        row1.addWidget(QLabel("Y1:"))
        self.ctx_y1 = QSpinBox(); self.ctx_y1.setRange(0, 9999); row1.addWidget(self.ctx_y1)
        grid.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("X2:"))
        self.ctx_x2 = QSpinBox(); self.ctx_x2.setRange(0, 9999); row2.addWidget(self.ctx_x2)
        row2.addWidget(QLabel("Y2:"))
        self.ctx_y2 = QSpinBox(); self.ctx_y2.setRange(0, 9999); row2.addWidget(self.ctx_y2)
        grid.addLayout(row2)

        layout.addLayout(grid)

        self.btn_pick_coord = QPushButton("选择PDF预览并框选")
        self.btn_pick_coord.clicked.connect(self._open_preview_coordinate)
        layout.addWidget(self.btn_pick_coord)
        layout.addStretch()
        return grp

    def _build_keyword_panel(self) -> QGroupBox:
        """关键词匹配参数面板。"""
        grp = QGroupBox("关键词匹配参数")
        layout = QVBoxLayout(grp)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("关键词:"))
        self.kw_keyword = QLineEdit(); self.kw_keyword.setPlaceholderText("如：编号"); row1.addWidget(self.kw_keyword)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("方向:"))
        self.kw_direction = QComboBox()
        self.kw_direction.addItems(["右侧", "下方", "左侧", "上方"])
        row2.addWidget(self.kw_direction)
        row2.addWidget(QLabel("范围(像素):"))
        self.kw_range = QSpinBox(); self.kw_range.setRange(50, 500); self.kw_range.setValue(200)
        row2.addWidget(self.kw_range)
        row2.addStretch()
        layout.addLayout(row2)

        self.btn_test_kw = QPushButton("测试关键词（预览高亮）")
        self.btn_test_kw.clicked.connect(self._open_preview_keyword)
        layout.addWidget(self.btn_test_kw)
        layout.addStretch()
        return grp

    def _build_table_panel(self) -> QGroupBox:
        """表格提取参数面板。"""
        grp = QGroupBox("表格提取参数")
        layout = QVBoxLayout(grp)

        self.btn_pick_table = QPushButton("选择PDF框选表格区域")
        self.btn_pick_table.clicked.connect(self._open_preview_table)
        layout.addWidget(self.btn_pick_table)

        self.lbl_table_region = QLabel("表格区域: 未框选")
        self.lbl_table_region.setStyleSheet("color: #666;")
        layout.addWidget(self.lbl_table_region)

        layout.addWidget(QLabel("列名映射（识别列名 → 输出字段名）："))
        self.col_map_table = QTableWidget()
        self.col_map_table.setColumnCount(2)
        self.col_map_table.setHorizontalHeaderLabels(["识别列名", "输出字段名"])
        self.col_map_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.col_map_table.setMaximumHeight(150)
        layout.addWidget(self.col_map_table)

        # 高级选项（可折叠）
        self.chk_advanced = QCheckBox("▸ 高级表格检测选项")
        self.chk_advanced.toggled.connect(self._toggle_advanced)
        layout.addWidget(self.chk_advanced)

        self.adv_widget = QWidget()
        adv_layout = QVBoxLayout(self.adv_widget)
        adv_layout.setContentsMargins(20, 0, 0, 0)

        adv_row1 = QHBoxLayout()
        adv_row1.addWidget(QLabel("列策略:"))
        self.tbl_v_strategy = QComboBox()
        self.tbl_v_strategy.addItems(TABLE_STRATEGIES)
        self.tbl_v_strategy.setCurrentText("lines")
        adv_row1.addWidget(self.tbl_v_strategy)
        adv_row1.addWidget(QLabel("行策略:"))
        self.tbl_h_strategy = QComboBox()
        self.tbl_h_strategy.addItems(TABLE_STRATEGIES)
        self.tbl_h_strategy.setCurrentText("lines")
        adv_row1.addWidget(self.tbl_h_strategy)
        adv_layout.addLayout(adv_row1)

        adv_row2 = QHBoxLayout()
        adv_row2.addWidget(QLabel("X容差:"))
        self.tbl_x_tol = QSpinBox(); self.tbl_x_tol.setRange(0, 20); self.tbl_x_tol.setValue(3)
        adv_row2.addWidget(self.tbl_x_tol)
        adv_row2.addWidget(QLabel("Y容差:"))
        self.tbl_y_tol = QSpinBox(); self.tbl_y_tol.setRange(0, 20); self.tbl_y_tol.setValue(3)
        adv_row2.addStretch()
        adv_layout.addLayout(adv_row2)

        self.adv_widget.setVisible(False)
        layout.addWidget(self.adv_widget)
        layout.addStretch()
        return grp

    def _toggle_advanced(self, checked: bool):
        self.adv_widget.setVisible(checked)
        self.chk_advanced.setText("▾ 高级表格检测选项" if checked else "▸ 高级表格检测选项")

    # ── 规则列表操作 ─────────────────────────────────────

    def _refresh_table(self):
        self.rule_table.blockSignals(True)
        self.rule_table.setRowCount(len(self.rules))
        for i, rule in enumerate(self.rules):
            mode_text = {"coordinate": "坐标提取", "keyword": "关键词匹配", "table": "表格提取"}.get(
                rule.get("mode", "coordinate"), "坐标提取")
            self.rule_table.setItem(i, 0, QTableWidgetItem(rule.get("name", "")))
            mode_combo = QComboBox()
            mode_combo.addItems(["坐标提取", "关键词匹配", "表格提取"])
            mode_idx = {"coordinate": 0, "keyword": 1, "table": 2}.get(rule.get("mode", "coordinate"), 0)
            mode_combo.setCurrentIndex(mode_idx)
            mode_combo.currentIndexChanged.connect(lambda idx, r=i: self._on_mode_changed(r, idx))
            self.rule_table.setCellWidget(i, 1, mode_combo)
            self.rule_table.setItem(i, 2, QTableWidgetItem(rule.get("page_range", "第1页")))
            dtype_combo = QComboBox()
            dtype_combo.addItems(list(DATA_TYPES))
            dtype_combo.setCurrentText(rule.get("data_type", "文本"))
            self.rule_table.setCellWidget(i, 3, dtype_combo)
        self.rule_table.blockSignals(False)

    def _on_row_changed(self, row: int, col: int, prev_row: int, prev_col: int):
        if row < 0 or row >= len(self.rules):
            return
        self._show_params(row)

    def _on_mode_changed(self, row: int, idx: int):
        mode = ["coordinate", "keyword", "table"][idx]
        self.rules[row]["mode"] = mode
        # 为新模式补充默认字段
        if mode == "coordinate":
            self.rules[row].setdefault("x1", 0)
            self.rules[row].setdefault("y1", 0)
            self.rules[row].setdefault("x2", 0)
            self.rules[row].setdefault("y2", 0)
        elif mode == "keyword":
            self.rules[row].setdefault("keyword", "")
            self.rules[row].setdefault("direction", "right")
            self.rules[row].setdefault("range", 200)
        elif mode == "table":
            self.rules[row].setdefault("table_region", [])
            self.rules[row].setdefault("column_mapping", {})
            self.rules[row].setdefault("table_settings", {})
        self._show_params(row)

    def _show_params(self, row: int):
        """根据选中行的模式显示对应参数面板。"""
        rule = self.rules[row]
        mode = rule.get("mode", "coordinate")

        self.grp_coordinate.setVisible(mode == "coordinate")
        self.grp_keyword.setVisible(mode == "keyword")
        self.grp_table.setVisible(mode == "table")

        if mode == "coordinate":
            self.ctx_x1.setValue(int(rule.get("x1", 0)))
            self.ctx_y1.setValue(int(rule.get("y1", 0)))
            self.ctx_x2.setValue(int(rule.get("x2", 0)))
            self.ctx_y2.setValue(int(rule.get("y2", 0)))
        elif mode == "keyword":
            self.kw_keyword.setText(rule.get("keyword", ""))
            dir_idx = {"right": 0, "below": 1, "left": 2, "above": 3}.get(
                rule.get("direction", "right"), 0)
            self.kw_direction.setCurrentIndex(dir_idx)
            self.kw_range.setValue(int(rule.get("range", 200)))
        elif mode == "table":
            region = rule.get("table_region", [])
            if region and len(region) == 4:
                self.lbl_table_region.setText(
                    f"表格区域: ({region[0]}, {region[1]}) - ({region[2]}, {region[3]})")
            else:
                self.lbl_table_region.setText("表格区域: 未框选")
            mapping = rule.get("column_mapping", {})
            self.col_map_table.setRowCount(len(mapping))
            for i, (src, dst) in enumerate(mapping.items()):
                self.col_map_table.setItem(i, 0, QTableWidgetItem(src))
                self.col_map_table.setItem(i, 1, QTableWidgetItem(dst))
            settings = rule.get("table_settings", {})
            self.tbl_v_strategy.setCurrentText(settings.get("vertical_strategy", "lines"))
            self.tbl_h_strategy.setCurrentText(settings.get("horizontal_strategy", "lines"))
            self.tbl_x_tol.setValue(int(settings.get("intersection_x_tolerance", 3)))
            self.tbl_y_tol.setValue(int(settings.get("intersection_y_tolerance", 3)))

    def _add_rule(self):
        rule = {"name": "新字段", "mode": "coordinate", "page_range": "第1页",
                "x1": 0, "y1": 0, "x2": 0, "y2": 0, "data_type": "文本"}
        self.rules.append(rule)
        self._refresh_table()
        self.rule_table.selectRow(len(self.rules) - 1)

    def _delete_rule(self):
        rows = sorted({idx.row() for idx in self.rule_table.selectedIndexes()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "提示", "请先选择要删除的规则")
            return
        for row in rows:
            self.rules.pop(row)
        self._refresh_table()

    def _move_rule(self, direction: int):
        row = self.rule_table.currentRow()
        if row < 0:
            return
        new_row = row + direction
        if new_row < 0 or new_row >= len(self.rules):
            return
        self.rules.insert(new_row, self.rules.pop(row))
        self._refresh_table()
        self.rule_table.selectRow(new_row)

    # ── 从面板回写当前规则 ────────────────────────────────

    def _save_current_params(self):
        """将参数面板的当前值写回选中的规则。"""
        row = self.rule_table.currentRow()
        if row < 0 or row >= len(self.rules):
            return
        rule = self.rules[row]
        mode = rule.get("mode", "coordinate")

        # 保存列表中的通用字段
        name_item = self.rule_table.item(row, 0)
        if name_item:
            rule["name"] = name_item.text()
        page_item = self.rule_table.item(row, 2)
        if page_item:
            rule["page_range"] = page_item.text()
        dtype_combo = self.rule_table.cellWidget(row, 3)
        if dtype_combo:
            rule["data_type"] = dtype_combo.currentText()

        # 保存模式特定字段
        if mode == "coordinate":
            rule["x1"] = self.ctx_x1.value()
            rule["y1"] = self.ctx_y1.value()
            rule["x2"] = self.ctx_x2.value()
            rule["y2"] = self.ctx_y2.value()
        elif mode == "keyword":
            rule["keyword"] = self.kw_keyword.text()
            rule["direction"] = ["right", "below", "left", "above"][self.kw_direction.currentIndex()]
            rule["range"] = self.kw_range.value()
        elif mode == "table":
            # 表格区域通过预览框选设置，这里只保存列名映射和高级参数
            mapping = {}
            for i in range(self.col_map_table.rowCount()):
                src_item = self.col_map_table.item(i, 0)
                dst_item = self.col_map_table.item(i, 1)
                if src_item and dst_item:
                    src = src_item.text().strip()
                    dst = dst_item.text().strip()
                    if src and dst:
                        mapping[src] = dst
            rule["column_mapping"] = mapping
            rule["table_settings"] = {
                "vertical_strategy": self.tbl_v_strategy.currentText(),
                "horizontal_strategy": self.tbl_h_strategy.currentText(),
                "intersection_x_tolerance": self.tbl_x_tol.value(),
                "intersection_y_tolerance": self.tbl_y_tol.value(),
                "snap_x_tolerance": self.tbl_x_tol.value(),
                "snap_y_tolerance": self.tbl_y_tol.value(),
            }

    # ── PDF 预览集成 ──────────────────────────────────────

    def _open_preview_coordinate(self):
        """坐标模式：打开预览框选。"""
        self._save_current_params()
        row = self.rule_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择目标规则")
            return
        path, _ = QFileDialog.getOpenFileName(self, "选择 PDF 预览文件", "", "PDF 文件 (*.pdf)")
        if not path:
            return
        self._preview_dlg = PdfPreviewDialog(path, self)
        self._preview_dlg.set_mode("coordinate")

        def on_confirm(x1, y1, x2, y2, page):
            self.ctx_x1.setValue(x1); self.ctx_y1.setValue(y1)
            self.ctx_x2.setValue(x2); self.ctx_y2.setValue(y2)
            self._save_current_params()
            page_str = f"第{page}页"
            page_item = self.rule_table.item(row, 2)
            if page_item:
                page_item.setText(page_str)

        self._preview_dlg.coordinates_confirmed.connect(on_confirm)
        self._preview_dlg.finished.connect(self._on_preview_closed)
        self._preview_dlg.show()

    def _open_preview_keyword(self):
        """关键词模式：打开预览并高亮关键词。"""
        self._save_current_params()
        path, _ = QFileDialog.getOpenFileName(self, "选择 PDF 测试文件", "", "PDF 文件 (*.pdf)")
        if not path:
            return
        keywords = []
        for rule in self.rules:
            if rule.get("mode") == "keyword" and rule.get("keyword"):
                keywords.append(rule["keyword"])
        self._preview_dlg = PdfPreviewDialog(path, self)
        self._preview_dlg.set_mode("keyword")
        self._preview_dlg.set_keywords(keywords)
        self._preview_dlg.finished.connect(self._on_preview_closed)
        self._preview_dlg.show()

    def _open_preview_table(self):
        """表格模式：打开预览框选表格区域，自动识别列名。"""
        self._save_current_params()
        row = self.rule_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择目标规则")
            return
        path, _ = QFileDialog.getOpenFileName(self, "选择 PDF 预览文件", "", "PDF 文件 (*.pdf)")
        if not path:
            return
        self._preview_dlg = PdfPreviewDialog(path, self)
        self._preview_dlg.set_mode("table")

        def on_table_region(x1, y1, x2, y2, page):
            rule = self.rules[row]
            rule["table_region"] = [x1, y1, x2, y2]
            self.lbl_table_region.setText(
                f"表格区域: ({x1}, {y1}) - ({x2}, {y2})")
            # 自动识别列名
            self._auto_detect_columns(path, [x1, y1, x2, y2], page)
            self._save_current_params()

        self._preview_dlg.table_region_confirmed.connect(on_table_region)
        self._preview_dlg.finished.connect(self._on_preview_closed)
        self._preview_dlg.show()

    def _auto_detect_columns(self, pdf_path: str, region: list, page_num: int):
        """框选表格区域后自动识别列名并填充映射子表。"""
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                page = pdf.pages[page_num - 1] if page_num <= len(pdf.pages) else pdf.pages[0]
                x1, y1, x2, y2 = region
                from pdf_extractor import PdfExtractor
                bbox = PdfExtractor._bl_bbox_to_plumber(
                    x1, y1, x2, y2, page.width, page.height)
                cropped = page.within_bbox(bbox)

                # 尝试 lines 策略（适合有边框表格）
                tables = cropped.extract_tables({
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                })
                if not tables:
                    # 回退到 text 策略（适合隐式表格）
                    tables = cropped.extract_tables({
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                    })

                if tables and tables[0]:
                    import re
                    headers = [re.sub(r"\s+", "", str(h or "")) for h in tables[0][0]]
                    # 过滤空表头
                    headers = [h for h in headers if h]
                    self.col_map_table.setRowCount(len(headers))
                    for i, h in enumerate(headers):
                        self.col_map_table.setItem(i, 0, QTableWidgetItem(h))
                        self.col_map_table.setItem(i, 1, QTableWidgetItem(h))
                    self.lbl_table_region.setText(
                        f"表格区域: ({x1}, {y1}) - ({x2}, {y2})  [已识别 {len(headers)} 列]")
                else:
                    QMessageBox.information(self, "提示",
                        "未能在表格区域中识别到列名，请调整框选范围或表格检测参数后重试")
        except Exception as e:
            logger.exception("自动识别列名失败")
            QMessageBox.warning(self, "错误", f"自动识别列名失败：{e}")

    def _on_preview_closed(self):
        self._preview_dlg = None

    # ── 保存 / 加载 ────────────────────────────────────────

    def _save(self):
        self._save_current_params()
        config = {"rule_name": self.edit_rule_name.text(), "rules": self.rules}
        if not self.config_path:
            self._save_as()
            return
        if ConfigManager.save(config, self.config_path):
            self.config = config
            QMessageBox.information(self, "成功", "配置已保存")
            self.accept()
        else:
            QMessageBox.critical(self, "错误", "保存配置失败")

    def _save_as(self):
        self._save_current_params()
        path, _ = QFileDialog.getSaveFileName(self, "保存配置", "", "配置文件 (*.cfg)")
        if not path:
            return
        if not path.endswith(".cfg"):
            path += ".cfg"
        config = {"rule_name": self.edit_rule_name.text(), "rules": self.rules}
        if ConfigManager.save(config, path):
            self.config = config
            self.config_path = path
            QMessageBox.information(self, "成功", "配置已保存")
            self.accept()
        else:
            QMessageBox.critical(self, "错误", "保存配置失败")

    def get_config(self) -> dict:
        self._save_current_params()
        return {"rule_name": self.edit_rule_name.text(), "rules": self.rules}

    def get_config_path(self) -> str:
        return self.config_path
