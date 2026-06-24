# -*- coding: utf-8 -*-
"""提取规则配置窗口 (v2.2 三栏布局 + PDF 预览)。"""

import logging
import os
import re
from typing import List, Optional

from PyQt5.QtCore import QEvent, Qt, QTimer
from PyQt5.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QKeySequence
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFrame, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QShortcut,
    QSizePolicy, QSpinBox, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from config_manager import DATA_TYPES, ANCHOR_DIRECTIONS, ConfigManager
from pdf_preview_dialog import PdfPreviewDialog

logger = logging.getLogger(__name__)

LIST_COLUMNS = ["字段", "模式", "页面范围", "数据类型"]

_DPI = 150
_HL = {
    "coordinate": (220, 38, 38),
    "anchor": (245, 158, 11),
    "table_column": (37, 99, 235),
}

# 关键词高亮半透明色板
_KW_FILL_COLORS = [
    QColor(220, 38, 38, 60),
    QColor(37, 99, 235, 60),
    QColor(34, 197, 94, 60),
    QColor(245, 158, 11, 60),
    QColor(139, 92, 246, 60),
]
_KW_PEN_COLORS = [
    QColor(220, 38, 38),
    QColor(37, 99, 235),
    QColor(34, 197, 94),
    QColor(245, 158, 11),
    QColor(139, 92, 246),
]


class PdfPreviewWidget(QWidget):
    """PDF 实时预览控件。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc = None
        self._page_idx = 0
        self._total = 0
        self._zoom_fit = True
        self._hl_bbox = None
        self._hl_color = _HL["coordinate"]
        self._hl_label = ""
        self._kws = []  # 关键词列表
        self._init_ui()

    def _init_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(8)

        # Title row with buttons
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("PDF 预览", objectName="section-title"))
        hdr.addStretch()
        self.lbl_page = QLabel(objectName="hint-text")
        hdr.addWidget(self.lbl_page)

        # "打开PDF" + "弹出" 两个常驻按钮
        self.btn_open = QPushButton("打开PDF")
        self.btn_open.setObjectName("btn-secondary")
        self.btn_popup = QPushButton("弹出")
        self.btn_popup.setObjectName("btn-secondary")
        hdr.addWidget(self.btn_open)
        hdr.addWidget(self.btn_popup)
        lo.addLayout(hdr)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignCenter)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.pic = QLabel(alignment=Qt.AlignCenter)
        self.pic.setMinimumSize(200, 200)
        self.scroll.setWidget(self.pic)
        lo.addWidget(self.scroll, 1)

        self.lbl_hl = QLabel(objectName="hint-text")
        self.lbl_hl.setVisible(False)
        lo.addWidget(self.lbl_hl)

        self._show_placeholder()

        # Navigation
        nav = QHBoxLayout()
        self.btn_prev = QPushButton("上一页")
        self.btn_next = QPushButton("下一页")
        self.btn_fit = QPushButton("适应窗口")
        self.btn_actual = QPushButton("实际大小")
        for b in (self.btn_prev, self.btn_next, self.btn_fit, self.btn_actual):
            b.setObjectName("btn-small")
        nav.addWidget(self.btn_prev)
        nav.addWidget(self.btn_next)
        nav.addStretch()
        nav.addWidget(self.btn_fit)
        nav.addWidget(self.btn_actual)
        lo.addLayout(nav)

        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        self.btn_fit.clicked.connect(lambda: self._set_zoom(True))
        self.btn_actual.clicked.connect(lambda: self._set_zoom(False))
        self._update_nav()

    def _show_placeholder(self):
        self.pic.setMinimumSize(200, 200)
        self.pic.setMaximumSize(16777215, 16777215)  # QWIDGETSIZE_MAX
        self.pic.setText("点击「打开PDF」加载文件")
        self.pic.setObjectName("preview-placeholder")
        self.pic.style().unpolish(self.pic)
        self.pic.style().polish(self.pic)

    def load(self, path: str):
        try:
            import fitz
        except ImportError:
            self.pic.setText("PyMuPDF 未安装，无法预览")
            return
        try:
            if self._doc:
                self._doc.close()
            self._doc = fitz.open(path)
            self._total = len(self._doc)
            self._page_idx = 0
            self._render()
        except Exception as e:
            logger.exception("PDF 预览加载失败")
            self._show_placeholder()

    def set_hl(self, bbox, color=None, label=""):
        self._hl_bbox = bbox
        if color:
            self._hl_color = color
        self._hl_label = label
        if bbox:
            self.lbl_hl.setText(
                f"{bbox[0]},{bbox[1]}-{bbox[2]},{bbox[3]}"
                + (f" [{label}]" if label else ""))
            self.lbl_hl.setVisible(True)
        else:
            self.lbl_hl.setVisible(False)
        if self._doc:
            self._render()

    def set_keywords(self, kws):
        """设置关键词列表用于高亮。"""
        self._kws = kws or []
        if self._doc:
            self._render()

    def go_page(self, n: int):
        if not self._doc:
            return
        idx = max(0, min(n - 1, self._total - 1))
        if idx != self._page_idx:
            self._page_idx = idx
            self._render()

    def close_doc(self):
        if self._doc:
            self._doc.close()
            self._doc = None

    # ── internals ──

    def _prev(self):
        if self._page_idx > 0:
            self._page_idx -= 1
            self._render()

    def _next(self):
        if self._page_idx < self._total - 1:
            self._page_idx += 1
            self._render()

    def _set_zoom(self, fit: bool):
        self._zoom_fit = fit
        self._render()

    def _update_nav(self):
        h = self._doc is not None
        self.btn_prev.setEnabled(h and self._page_idx > 0)
        self.btn_next.setEnabled(h and self._page_idx < self._total - 1)
        self.lbl_page.setText(
            f"第 {self._page_idx + 1} / {self._total} 页" if h else "")

    def _render(self):
        if not self._doc:
            self._show_placeholder()
            return
        try:
            page = self._doc[self._page_idx]
            r = page.rect
            if self._zoom_fit:
                vw = max(self.scroll.viewport().width() - 20, 200)
                z = vw / r.width if r.width else 1.0
            else:
                z = 1.0
            import fitz
            mat = fitz.Matrix(z, z)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            pm = QPixmap.fromImage(img)

            need_painter = bool(self._kws) or bool(self._hl_bbox)
            if need_painter:
                painter = QPainter(pm)

                # 关键词高亮：半透明填色 + 描边
                if self._kws:
                    for i, kw in enumerate(self._kws):
                        if not kw:
                            continue
                        fill = _KW_FILL_COLORS[i % len(_KW_FILL_COLORS)]
                        pen_c = _KW_PEN_COLORS[i % len(_KW_PEN_COLORS)]
                        for rect in page.search_for(kw):
                            x = int(rect.x0 * z)
                            y = int(rect.y0 * z)
                            w = int((rect.x1 - rect.x0) * z)
                            h = int((rect.y1 - rect.y0) * z)
                            painter.fillRect(x, y, w, h, fill)
                            painter.setPen(QPen(pen_c, 1))
                            painter.setBrush(Qt.NoBrush)
                            painter.drawRect(x, y, w, h)

                # 坐标框选高亮（coordinate 模式）
                if self._hl_bbox:
                    pen = QPen()
                    pen.setColor(QColor(*self._hl_color))
                    pen.setWidth(2)
                    painter.setPen(pen)
                    painter.setBrush(Qt.NoBrush)
                    x0, y0, x1, y1 = self._hl_bbox
                    px0, py0 = x0 * z, (r.height - y1) * z
                    pw, ph = (x1 - x0) * z, (y1 - y0) * z
                    painter.drawRect(int(px0), int(py0), int(pw), int(ph))

                painter.end()

            self.pic.setPixmap(pm)
            self.pic.setFixedSize(pm.size())
            self.pic.setObjectName("")
            self.pic.setStyleSheet(
                "QLabel { background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:0; }")
            self._update_nav()
        except Exception as e:
            logger.exception("PDF 渲染失败")


class ConfigDialog(QDialog):
    """提取规则配置对话框 (v2.2)。"""

    _last_row = 0

    def __init__(self, config: dict, config_path: str = "",
                 pending_paths: List[str] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("配置提取规则")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)
        self.config = dict(config)
        self.config_path = config_path
        self._pp = pending_paths or []
        self._pdf_path = None

        self.rules = list(self.config.get("rules", []))
        if not self.rules and "regions" in self.config:
            for r in self.config["regions"]:
                self.rules.append({
                    "name": r.get("name", ""), "mode": "coordinate",
                    "page_range": r.get("page_range", "第1页"),
                    "x1": r.get("x1", 0), "y1": r.get("y1", 0),
                    "x2": r.get("x2", 0), "y2": r.get("y2", 0),
                    "data_type": r.get("data_type", "文本"),
                })
        self._preview_dlg = None
        self._init_ui()
        self._refresh_table()
        self._setup_shortcuts()

        if self.rules and ConfigDialog._last_row < len(self.rules):
            self.rule_table.selectRow(ConfigDialog._last_row)

        if self._pp:
            self._pdf_path = self._pp[0]
            self._pw.load(self._pp[0])
        self._update_preview()

    # ═══════════════ UI ═══════════════

    def _init_ui(self):
        ml = QVBoxLayout(self)
        ml.setContentsMargins(16, 16, 16, 16)
        ml.setSpacing(12)

        # ── Top: rule name + fullscreen ──
        top = QHBoxLayout()
        top.addWidget(QLabel("规则名称："))
        self.edt_name = QLineEdit()
        self.edt_name.setText(self.config.get("rule_name", "默认规则"))
        self.edt_name.setMaximumWidth(320)
        top.addWidget(self.edt_name)
        top.addStretch()
        ml.addLayout(top)

        # ── Left column / Right preview (QSplitter) ──
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)

        # LEFT COLUMN
        lc = QVBoxLayout()
        lc.setSpacing(6)

        # ── Rule table card ──
        rule_card = QFrame(objectName="card")
        rule_card.setMinimumWidth(500)
        rcl = QVBoxLayout(rule_card)
        rcl.setContentsMargins(1, 6, 1, 6)
        rcl.setSpacing(8)

        self.rule_table = QTableWidget()
        self.rule_table.setColumnCount(len(LIST_COLUMNS))
        self.rule_table.setHorizontalHeaderLabels(LIST_COLUMNS)
        self.rule_table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.rule_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.rule_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rule_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.rule_table.verticalHeader().setVisible(False)
        self._col_ratios = [120, 160, 100, 120]
        self._col_total = sum(self._col_ratios)
        self.rule_table.installEventFilter(self)
        rcl.addWidget(self.rule_table)

        rb = QHBoxLayout()
        self.btn_sel_all = QPushButton("全选")
        self.btn_del = QPushButton("删除选中")
        self.btn_del.setObjectName("btn-ghost")
        self.btn_add = QPushButton("添加行")
        for b in (self.btn_sel_all, self.btn_del, self.btn_add):
            b.setObjectName("btn-small")
        rb.addWidget(self.btn_sel_all)
        rb.addWidget(self.btn_del)
        rb.addWidget(self.btn_add)
        rb.addStretch()
        rcl.addLayout(rb)
        lc.addWidget(rule_card, 1)

        # ── Mode params (plain wrapper, GroupBox provides the card styling) ──
        params_wrap = QWidget()
        pw_layout = QVBoxLayout(params_wrap)
        pw_layout.setContentsMargins(0, 0, 0, 0)
        pw_layout.setSpacing(4)

        self.grp_coord = self._mk_coord()
        self.grp_anchor = self._mk_anchor()
        self.grp_tbl = self._mk_tbl()
        pw_layout.addWidget(self.grp_coord)
        pw_layout.addWidget(self.grp_anchor)
        pw_layout.addWidget(self.grp_tbl)
        lc.addWidget(params_wrap, 0)

        left_widget = QWidget()
        left_widget.setMinimumWidth(480)
        left_widget.setLayout(lc)

        self._pw = PdfPreviewWidget()
        splitter.addWidget(left_widget)
        splitter.addWidget(self._pw)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([520, 800])
        ml.addWidget(splitter, 1)

        # ── Bottom bar ──
        bar = QFrame(objectName="toolbar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(0, 0, 0, 0)

        self.btn_load = QPushButton("加载配置")
        self.btn_load.setObjectName("btn-secondary")
        self.lbl_status = QLabel("", objectName="hint-text")
        bl.addWidget(self.btn_load)
        bl.addWidget(self.lbl_status)
        bl.addStretch()

        self.btn_save = QPushButton("保存")
        self.btn_save.setObjectName("btn-secondary")
        self.btn_saveas = QPushButton("另存为")
        self.btn_saveas.setObjectName("btn-small")
        self.btn_close = QPushButton("关闭")
        self.btn_close.setObjectName("btn-ghost")
        bl.addWidget(self.btn_save)
        bl.addWidget(self.btn_saveas)
        bl.addWidget(self.btn_close)
        ml.addWidget(bar)

        # ── Connections ──
        self.rule_table.currentCellChanged.connect(self._on_row)
        self.btn_sel_all.clicked.connect(lambda: self.rule_table.selectAll())
        self.btn_del.clicked.connect(self._del_rules)
        self.btn_add.clicked.connect(self._add_rule)
        self.btn_load.clicked.connect(self._load_cfg)
        self.btn_save.clicked.connect(self._save)
        self.btn_saveas.clicked.connect(self._save_as)
        self.btn_close.clicked.connect(self._close)

        # PDF preview connections (replacing old _preview_*)
        self._pw.btn_open.clicked.connect(self._open_pdf)
        self._pw.btn_popup.clicked.connect(self._open_popup)

        # Live highlight: form edit → auto refresh preview
        for sp in (self.sp_x1, self.sp_y1, self.sp_x2, self.sp_y2):
            sp.valueChanged.connect(self._update_preview)
        self.kw_text.textChanged.connect(self._update_preview)
        self.tc_hdr.textChanged.connect(self._update_preview)

    def eventFilter(self, obj, event):
        if obj is self.rule_table and event.type() == QEvent.Resize:
            w = self.rule_table.viewport().width()
            if w > 0:
                for i, r in enumerate(self._col_ratios):
                    self.rule_table.setColumnWidth(i, max(20, int(w * r / self._col_total)))
        return super().eventFilter(obj, event)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+S"), self, self._save)
        QShortcut(QKeySequence.Delete, self, self._del_rules)

    # ═══════════════ Mode panels ═══════════════

    def _mk_coord(self):
        g = QGroupBox("坐标提取参数")
        lo = QVBoxLayout(g)
        for row_labels in [("X1:", "sp_x1", "Y1:", "sp_y1"),
                            ("X2:", "sp_x2", "Y2:", "sp_y2")]:
            r = QHBoxLayout()
            for label, attr in [(row_labels[0], row_labels[1]), (row_labels[2], row_labels[3])]:
                r.addWidget(QLabel(label))
                sp = QSpinBox()
                sp.setRange(0, 9999)
                setattr(self, attr, sp)
                r.addWidget(sp)
            lo.addLayout(r)
        return g

    def _mk_anchor(self):
        g = QGroupBox("关键词匹配参数")
        lo = QVBoxLayout(g)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("关键词:"))
        self.kw_text = QLineEdit()
        self.kw_text.setPlaceholderText("如：编号")
        r1.addWidget(self.kw_text)
        lo.addLayout(r1)
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("方向:"))
        self.kw_dir = QComboBox()
        self.kw_dir.addItems(["右侧", "下方", "左侧", "上方"])
        r2.addWidget(self.kw_dir)
        r2.addWidget(QLabel("范围:"))
        self.kw_range = QSpinBox()
        self.kw_range.setRange(50, 500)
        self.kw_range.setValue(200)
        r2.addWidget(self.kw_range)
        r2.addStretch()
        lo.addLayout(r2)
        return g

    def _mk_tbl(self):
        g = QGroupBox("表格列提取参数")
        lo = QVBoxLayout(g)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("表头关键词:"))
        self.tc_hdr = QLineEdit()
        self.tc_hdr.setPlaceholderText("如：更改对象编号")
        r1.addWidget(self.tc_hdr)
        lo.addLayout(r1)
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("行号:"))
        self.tc_row = QSpinBox()
        self.tc_row.setRange(2, 999)
        self.tc_row.setValue(2)
        r2.addWidget(self.tc_row)
        r2.addStretch()
        lo.addLayout(r2)
        return g

    # ═══════════════ Rule table ═══════════════

    def _refresh_table(self):
        self.rule_table.setRowCount(len(self.rules))
        for i, rule in enumerate(self.rules):
            mode_map = {"coordinate": "坐标提取", "anchor": "锚点提取", "table_column": "表格列提取"}
            ni = QTableWidgetItem(rule.get("name", ""))
            ni.setTextAlignment(Qt.AlignCenter)
            self.rule_table.setItem(i, 0, ni)
            mc = QComboBox()
            mc.setStyleSheet("QComboBox{padding:0 6px;min-height:24px;}")
            mc.addItems(["坐标提取", "锚点提取", "表格列提取"])
            mi = {"coordinate": 0, "anchor": 1, "table_column": 2}.get(rule.get("mode", "coordinate"), 0)
            mc.setCurrentIndex(mi)
            mc.currentIndexChanged.connect(lambda idx, r=i: self._mode_changed(r, idx))
            self.rule_table.setCellWidget(i, 1, mc)
            pi = QTableWidgetItem(rule.get("page_range", "第1页"))
            pi.setTextAlignment(Qt.AlignCenter)
            self.rule_table.setItem(i, 2, pi)
            dc = QComboBox()
            dc.setStyleSheet("QComboBox{padding:0 6px;min-height:24px;}")
            dc.addItems(list(DATA_TYPES))
            dc.setCurrentText(rule.get("data_type", "文本"))
            self.rule_table.setCellWidget(i, 3, dc)

    def _on_row(self, row, col, prev_row, prev_col):
        # 表单此时仍是上一行的值，先写回上一行（修复切行错位/丢失）
        if prev_row is not None and 0 <= prev_row < len(self.rules) and prev_row != row:
            self._save_params(prev_row)
        if 0 <= row < len(self.rules):
            self._show_params(row)

    def _mode_changed(self, row, idx):
        mode = ["coordinate", "anchor", "table_column"][idx]
        self.rules[row]["mode"] = mode
        for k, v in {
            "x1": 0, "y1": 0, "x2": 0, "y2": 0,
            "anchor_text": "", "direction": "right", "range": 200,
            "column_header": "", "row_number": 2,
        }.items():
            self.rules[row].setdefault(k, v)
        self._show_params(row)
        self._update_preview()

    def _show_params(self, row):
        rule = self.rules[row]
        mode = rule.get("mode", "coordinate")
        self.grp_coord.setVisible(mode == "coordinate")
        self.grp_anchor.setVisible(mode == "anchor")
        self.grp_tbl.setVisible(mode == "table_column")

        if mode == "coordinate":
            self.sp_x1.setValue(int(rule.get("x1", 0)))
            self.sp_y1.setValue(int(rule.get("y1", 0)))
            self.sp_x2.setValue(int(rule.get("x2", 0)))
            self.sp_y2.setValue(int(rule.get("y2", 0)))
        elif mode == "anchor":
            self.kw_text.setText(rule.get("anchor_text", ""))
            di = {"right": 0, "below": 1, "left": 2, "above": 3}.get(rule.get("direction", "right"), 0)
            self.kw_dir.setCurrentIndex(di)
            self.kw_range.setValue(int(rule.get("range", 200)))
        elif mode == "table_column":
            self.tc_hdr.setText(rule.get("column_header", ""))
            self.tc_row.setValue(int(rule.get("row_number", 2)))
        self._update_preview()

    def _update_preview(self):
        row = self.rule_table.currentRow()
        if row < 0 or row >= len(self.rules):
            self._pw.set_hl(None)
            self._pw.set_keywords([])
            return
        mode = self.rules[row].get("mode", "coordinate")
        color = _HL.get(mode, _HL["coordinate"])
        if mode == "coordinate":
            bbox = (self.sp_x1.value(), self.sp_y1.value(),
                    self.sp_x2.value(), self.sp_y2.value())
            self._pw.set_keywords([])
            if bbox[2] > bbox[0] and bbox[3] > bbox[1]:
                rn = self.rule_table.item(row, 0)
                self._pw.set_hl(bbox, color, rn.text() if rn else "")
            else:
                self._pw.set_hl(None)
        elif mode == "anchor":
            self._pw.set_hl(None)
            self._pw.set_keywords([self.kw_text.text()])
        elif mode == "table_column":
            self._pw.set_hl(None)
            self._pw.set_keywords([self.tc_hdr.text()])
        pi = self.rule_table.item(row, 2)
        pr = pi.text() if pi else "第1页"
        nums = re.findall(r'\d+', pr)
        if nums:
            self._pw.go_page(int(nums[0]))

    def _add_rule(self):
        self.rules.append({
            "name": "新字段", "mode": "coordinate", "page_range": "第1页",
            "x1": 0, "y1": 0, "x2": 0, "y2": 0, "data_type": "文本",
        })
        self._refresh_table()
        self.rule_table.selectRow(len(self.rules) - 1)

    def _del_rules(self):
        rows = sorted({i.row() for i in self.rule_table.selectedIndexes()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "提示", "请先选择要删除的规则行")
            return
        for r in rows:
            if r < len(self.rules):
                self.rules.pop(r)
        self._refresh_table()
        self._pw.set_hl(None)
        self._pw.set_keywords([])

    def _save_params(self, row=None):
        if row is None:
            row = self.rule_table.currentRow()
        if row < 0 or row >= len(self.rules):
            return
        rule = self.rules[row]
        mode = rule.get("mode", "coordinate")
        rule["name"] = (self.rule_table.item(row, 0).text().strip()
                        if self.rule_table.item(row, 0) else rule.get("name", ""))
        rule["page_range"] = (self.rule_table.item(row, 2).text() or "第1页"
                              if self.rule_table.item(row, 2) else "第1页")
        dc = self.rule_table.cellWidget(row, 3)
        rule["data_type"] = dc.currentText() if dc else rule.get("data_type", "文本")

        if mode == "coordinate":
            rule["x1"] = self.sp_x1.value()
            rule["y1"] = self.sp_y1.value()
            rule["x2"] = self.sp_x2.value()
            rule["y2"] = self.sp_y2.value()
        elif mode == "anchor":
            rule["anchor_text"] = self.kw_text.text()
            rule["direction"] = ["right", "below", "left", "above"][self.kw_dir.currentIndex()]
            rule["range"] = self.kw_range.value()
        elif mode == "table_column":
            rule["column_header"] = self.tc_hdr.text()
            rule["row_number"] = self.tc_row.value()

    # ═══════════════ Load / Save ═══════════════

    def _load_cfg(self):
        path, _ = QFileDialog.getOpenFileName(self, "加载配置", "", "配置文件 (*.cfg)")
        if not path:
            return
        loaded = ConfigManager.load(path)
        if loaded:
            self.config = loaded
            self.config_path = path
            self.rules = list(self.config.get("rules", []))
            if not self.rules and "regions" in self.config:
                for r in self.config["regions"]:
                    self.rules.append({
                        "name": r.get("name", ""), "mode": "coordinate",
                        "page_range": r.get("page_range", "第1页"),
                        "x1": r.get("x1", 0), "y1": r.get("y1", 0),
                        "x2": r.get("x2", 0), "y2": r.get("y2", 0),
                        "data_type": r.get("data_type", "文本"),
                    })
            self.edt_name.setText(self.config.get("rule_name", "默认规则"))
            self._refresh_table()
            ConfigManager.add_recent_config(path)
            if self.rules:
                self.rule_table.selectRow(0)
            QMessageBox.information(self, "成功", "配置已加载")

    def _save(self):
        self._save_params()
        cfg = {"rule_name": self.edt_name.text(), "rules": self.rules}
        if not self.config_path:
            return self._save_as()
        if ConfigManager.save(cfg, self.config_path):
            self.config = cfg
            ConfigManager.add_recent_config(self.config_path)
            self._flash_status(f"✓ 已保存到 {os.path.basename(self.config_path)}")
        else:
            QMessageBox.critical(self, "错误", "保存配置失败")

    def _save_as(self):
        self._save_params()
        path, _ = QFileDialog.getSaveFileName(self, "保存配置", "", "配置文件 (*.cfg)")
        if not path:
            return
        if not path.endswith(".cfg"):
            path += ".cfg"
        cfg = {"rule_name": self.edt_name.text(), "rules": self.rules}
        if ConfigManager.save(cfg, path):
            self.config = cfg
            self.config_path = path
            ConfigManager.add_recent_config(path)
            self._flash_status(f"✓ 已保存到 {os.path.basename(path)}")
        else:
            QMessageBox.critical(self, "错误", "保存配置失败")

    def _flash_status(self, text):
        self.lbl_status.setText(text)
        QTimer.singleShot(3000, self.lbl_status.clear)

    def _close(self):
        row = self.rule_table.currentRow()
        if row >= 0:
            ConfigDialog._last_row = row
        self._pw.close_doc()
        self.reject()

    def get_config(self):
        self._save_params()
        return {"rule_name": self.edt_name.text(), "rules": self.rules}

    def get_config_path(self):
        return self.config_path

    # ═══════════════ PDF preview ═══════════════

    def _open_pdf(self):
        """打开/更换 PDF 文件，加载到内嵌右栏预览。"""
        self._save_params()
        path, _ = QFileDialog.getOpenFileName(self, "选择 PDF 预览文件", "", "PDF 文件 (*.pdf)")
        if not path:
            return
        self._pdf_path = path
        self._pw.load(path)
        self._update_preview()

    def _open_popup(self):
        """弹出 PdfPreviewDialog 弹窗（供框选/详细查看）。"""
        self._save_params()
        row = self.rule_table.currentRow()
        if row < 0:
            return QMessageBox.warning(self, "提示", "请先选择目标规则")
        if not self._pdf_path:
            path, _ = QFileDialog.getOpenFileName(self, "选择 PDF 预览文件", "", "PDF 文件 (*.pdf)")
            if not path:
                return
            self._pdf_path = path
            self._pw.load(path)
            self._update_preview()
        rule = self.rules[row]
        mode = rule.get("mode", "coordinate")
        self._preview_dlg = PdfPreviewDialog(self._pdf_path, self)
        self._preview_dlg.set_mode(mode)

        if mode == "anchor":
            self._preview_dlg.set_keywords([rule.get("anchor_text", "")])
        elif mode == "table_column":
            self._preview_dlg.set_keywords([rule.get("column_header", "")])
        elif mode == "coordinate":
            def cb(x1, y1, x2, y2, page):
                self.sp_x1.setValue(x1)
                self.sp_y1.setValue(y1)
                self.sp_x2.setValue(x2)
                self.sp_y2.setValue(y2)
                ps = f"第{page}页"
                if self.rule_table.item(row, 2):
                    self.rule_table.item(row, 2).setText(ps)
                self._save_params()
                self._update_preview()
            self._preview_dlg.coordinates_confirmed.connect(cb)

        self._preview_dlg.finished.connect(self._on_pv_closed)
        self._preview_dlg.show()

    def _on_pv_closed(self):
        self._preview_dlg = None
