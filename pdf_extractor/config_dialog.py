# -*- coding: utf-8 -*-
"""提取规则配置窗口。"""

import logging
import os

from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from config_manager import DATA_TYPES, ConfigManager
from pdf_preview_dialog import PdfPreviewDialog

logger = logging.getLogger(__name__)

COLUMNS = ["区域名", "页面范围", "左上角X", "左上角Y", "右下角X", "右下角Y", "类型"]


class ConfigDialog(QDialog):
    """提取规则配置对话框。"""

    def __init__(self, config: dict, config_path: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("配置提取规则")
        self.resize(900, 500)
        self.config = dict(config)
        self.config_path = config_path
        self._init_ui()
        self._load_config_to_table()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("规则名称："))
        self.edit_rule_name = QLineEdit()
        self.edit_rule_name.setText(self.config.get("rule_name", "默认规则"))
        name_layout.addWidget(self.edit_rule_name)
        layout.addLayout(name_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table)

        row_btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("添加行")
        self.btn_delete = QPushButton("删除行")
        self.btn_up = QPushButton("上移")
        self.btn_down = QPushButton("下移")
        row_btn_layout.addWidget(self.btn_add)
        row_btn_layout.addWidget(self.btn_delete)
        row_btn_layout.addWidget(self.btn_up)
        row_btn_layout.addWidget(self.btn_down)
        row_btn_layout.addStretch()
        layout.addLayout(row_btn_layout)

        bottom_layout = QHBoxLayout()
        self.btn_preview = QPushButton("选择PDF预览并框选")
        self.btn_save = QPushButton("保存")
        self.btn_save_as = QPushButton("另存为")
        self.btn_cancel = QPushButton("取消")
        bottom_layout.addWidget(self.btn_preview)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_save)
        bottom_layout.addWidget(self.btn_save_as)
        bottom_layout.addWidget(self.btn_cancel)
        layout.addLayout(bottom_layout)

        self.btn_add.clicked.connect(self._add_row)
        self.btn_delete.clicked.connect(self._delete_row)
        self.btn_up.clicked.connect(lambda: self._move_row(-1))
        self.btn_down.clicked.connect(lambda: self._move_row(1))
        self.btn_preview.clicked.connect(self._open_preview)
        self.btn_save.clicked.connect(self._save)
        self.btn_save_as.clicked.connect(self._save_as)
        self.btn_cancel.clicked.connect(self.reject)

    def _load_config_to_table(self):
        regions = self.config.get("regions", [])
        self.table.setRowCount(len(regions))
        for row, region in enumerate(regions):
            self._set_row(row, region)

    def _set_row(self, row: int, region: dict):
        values = [
            region.get("name", ""),
            region.get("page_range", "第1页"),
            str(region.get("x1", 0)),
            str(region.get("y1", 0)),
            str(region.get("x2", 0)),
            str(region.get("y2", 0)),
            region.get("data_type", "文本"),
        ]
        for col, val in enumerate(values[:-1]):
            self.table.setItem(row, col, QTableWidgetItem(val))
        combo = QComboBox()
        combo.addItems(list(DATA_TYPES))
        combo.setCurrentText(values[-1])
        self.table.setCellWidget(row, 6, combo)

    def _add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._set_row(
            row,
            {
                "name": "新字段",
                "page_range": "第1页",
                "x1": 0,
                "y1": 0,
                "x2": 0,
                "y2": 0,
                "data_type": "文本",
            },
        )

    def _delete_row(self):
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "提示", "请先选择要删除的行")
            return
        for row in rows:
            self.table.removeRow(row)

    def _move_row(self, direction: int):
        row = self.table.currentRow()
        if row < 0:
            return
        new_row = row + direction
        if new_row < 0 or new_row >= self.table.rowCount():
            return
        region = self._get_row_data(row)
        self.table.removeRow(row)
        self.table.insertRow(new_row)
        self._set_row(new_row, region)
        self.table.selectRow(new_row)

    def _get_row_data(self, row: int) -> dict:
        combo = self.table.cellWidget(row, 6)
        data_type = combo.currentText() if combo else "文本"
        def cell_text(col):
            item = self.table.item(row, col)
            return item.text() if item else ""
        return {
            "name": cell_text(0),
            "page_range": cell_text(1),
            "x1": int(float(cell_text(2) or 0)),
            "y1": int(float(cell_text(3) or 0)),
            "x2": int(float(cell_text(4) or 0)),
            "y2": int(float(cell_text(5) or 0)),
            "data_type": data_type,
        }

    def _table_to_config(self) -> dict:
        regions = []
        for row in range(self.table.rowCount()):
            regions.append(self._get_row_data(row))
        return {"rule_name": self.edit_rule_name.text(), "regions": regions}

    def _open_preview(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择要配置的提取规则行")
            return
        path, _ = QFileDialog.getOpenFileName(self, "选择 PDF 预览文件", "", "PDF 文件 (*.pdf)")
        if not path:
            return
        dlg = PdfPreviewDialog(path, self)
        dlg.coordinates_confirmed.connect(
            lambda x1, y1, x2, y2, page: self._fill_coords(row, x1, y1, x2, y2, page)
        )
        dlg.exec_()

    def _fill_coords(self, row: int, x1: int, y1: int, x2: int, y2: int, page: int):
        self.table.item(row, 2).setText(str(x1))
        self.table.item(row, 3).setText(str(y1))
        self.table.item(row, 4).setText(str(x2))
        self.table.item(row, 5).setText(str(y2))
        self.table.item(row, 1).setText(f"第{page}页")

    def _save(self):
        self.config = self._table_to_config()
        if not self.config_path:
            self._save_as()
            return
        if ConfigManager.save(self.config, self.config_path):
            QMessageBox.information(self, "成功", "配置已保存")
            self.accept()
        else:
            QMessageBox.critical(self, "错误", "保存配置失败")

    def _save_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存配置", "", "配置文件 (*.cfg)")
        if not path:
            return
        if not path.endswith(".cfg"):
            path += ".cfg"
        self.config = self._table_to_config()
        if ConfigManager.save(self.config, path):
            self.config_path = path
            QMessageBox.information(self, "成功", "配置已保存")
            self.accept()
        else:
            QMessageBox.critical(self, "错误", "保存配置失败")

    def get_config(self) -> dict:
        return self._table_to_config()

    def get_config_path(self) -> str:
        return self.config_path
