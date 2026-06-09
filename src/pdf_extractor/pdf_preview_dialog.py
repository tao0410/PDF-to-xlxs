# -*- coding: utf-8 -*-
"""PDF 预览与可视化框选窗口。"""

import logging
import os

import fitz
from PyQt5.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRubberBand,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class PdfCanvas(QWidget):
    """PDF 预览画布，支持鼠标框选。"""

    coordinates_changed = pyqtSignal(int, int, int, int)  # x1,y1,x2,y2 in PDF coords
    mouse_moved = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._page_height = 0.0
        self._zoom = 1.0
        self._origin = QPoint(0, 0)
        self._rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self._rubber_origin = QPoint()
        self._selecting = False
        self._selection_rect = QRect()
        self.setMinimumSize(400, 300)

    def set_page_image(self, pixmap: QPixmap, page_height: float, zoom: float) -> None:
        """设置当前页渲染图像。"""
        self._pixmap = pixmap
        self._page_height = page_height
        self._zoom = zoom if zoom > 0 else 1.0
        self.setFixedSize(pixmap.size())
        self.update()

    def clear_selection(self) -> None:
        """清除框选。"""
        self._rubber_band.hide()
        self._selection_rect = QRect()
        self.coordinates_changed.emit(0, 0, 0, 0)

    def get_pdf_bbox(self) -> tuple:
        """获取当前框选的 PDF 坐标 (x1,y1,x2,y2)，左下角原点。"""
        if self._selection_rect.isNull():
            return (0, 0, 0, 0)
        return self._widget_rect_to_pdf(self._selection_rect)

    def paintEvent(self, event):
        from PyQt5.QtGui import QPainter

        painter = QPainter(self)
        if not self._pixmap.isNull():
            painter.drawPixmap(0, 0, self._pixmap)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self._pixmap.isNull():
            self._selecting = True
            self._rubber_origin = event.pos()
            self._rubber_band.setGeometry(QRect(self._rubber_origin, QPoint()))
            self._rubber_band.show()

    def mouseMoveEvent(self, event):
        pdf_x, pdf_y = self._widget_point_to_pdf(event.pos())
        self.mouse_moved.emit(int(pdf_x), int(pdf_y))
        if self._selecting:
            rect = QRect(self._rubber_origin, event.pos()).normalized()
            self._rubber_band.setGeometry(rect)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._selecting:
            self._selecting = False
            self._selection_rect = QRect(self._rubber_origin, event.pos()).normalized()
            x1, y1, x2, y2 = self._widget_rect_to_pdf(self._selection_rect)
            self.coordinates_changed.emit(int(x1), int(y1), int(x2), int(y2))

    def _widget_point_to_pdf(self, point: QPoint) -> tuple:
        """控件坐标转 PDF 坐标（左下角原点）。"""
        x = point.x() / self._zoom
        y = self._page_height - point.y() / self._zoom
        x = max(0, min(x, self._pixmap.width() / self._zoom))
        y = max(0, min(y, self._page_height))
        return x, y

    def _widget_rect_to_pdf(self, rect: QRect) -> tuple:
        """控件矩形转 PDF bbox，返回 (x1,y1,x2,y2) 左下角原点。"""
        x1_w = rect.left()
        x2_w = rect.right()
        y_top_w = rect.top()
        y_bottom_w = rect.bottom()

        pdf_x1 = x1_w / self._zoom
        pdf_x2 = x2_w / self._zoom
        pdf_y2 = self._page_height - y_top_w / self._zoom
        pdf_y1 = self._page_height - y_bottom_w / self._zoom

        page_width = self._pixmap.width() / self._zoom
        x1 = max(0, min(pdf_x1, pdf_x2, page_width))
        x2 = max(0, min(max(pdf_x1, pdf_x2), page_width))
        y1 = max(0, min(pdf_y1, pdf_y2, self._page_height))
        y2 = max(0, min(max(pdf_y1, pdf_y2), self._page_height))
        return int(x1), int(y1), int(x2), int(y2)


class PdfPreviewDialog(QDialog):
    """PDF 预览与坐标提取对话框。

    支持三种模式：
    - coordinate: 原有坐标框选（默认）
    - anchor: 锚点关键词高亮
    - table_column: 表格列表头关键词高亮
    """

    coordinates_confirmed = pyqtSignal(int, int, int, int, int)  # x1,y1,x2,y2,page(1-based) — coordinate 模式

    def __init__(self, pdf_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDF预览与坐标提取")
        self.resize(900, 700)
        self._pdf_path = pdf_path
        self._doc = None
        self._current_page = 0
        self._zoom = 1.0
        self._fit_mode = "fit"
        self._pdf_bbox = (0, 0, 0, 0)
        self._mode = "coordinate"  # 当前预览模式
        self._keywords = []        # 关键词列表（keyword 模式高亮用）

        self._init_ui()
        self._load_pdf()

    def set_mode(self, mode: str) -> None:
        """设置预览模式: 'coordinate' | 'anchor' | 'table_column'"""
        self._mode = mode
        if mode == "coordinate":
            self.setWindowTitle("PDF预览 — 坐标框选")
            self.btn_confirm.setText("确认坐标")
            self.lbl_status.setText("请框选要提取的区域，或直接查看 PDF 内容")
        elif mode == "anchor":
            self.setWindowTitle("PDF预览 — 锚点关键词测试")
            self.btn_confirm.setText("确认坐标")
            self.lbl_status.setText("彩色高亮为关键词匹配位置")
        elif mode == "table_column":
            self.setWindowTitle("PDF预览 — 表格列定位测试")
            self.btn_confirm.setText("确认坐标")
            self.lbl_status.setText("高亮为表头关键词匹配位置")

    def set_keywords(self, keywords: list) -> None:
        """设置需要高亮的关键词列表（anchor / table_column 模式）。"""
        self._keywords = keywords or []
        if self._doc:
            self._render_page()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.btn_prev = QPushButton("上一页")
        self.btn_next = QPushButton("下一页")
        self.lbl_page = QLabel("第 0 页 / 共 0 页")
        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_out = QPushButton("-")
        self.btn_fit = QPushButton("适应窗口")
        self.btn_actual = QPushButton("实际大小")
        toolbar.addWidget(self.btn_prev)
        toolbar.addWidget(self.btn_next)
        toolbar.addWidget(self.lbl_page)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_zoom_in)
        toolbar.addWidget(self.btn_zoom_out)
        toolbar.addWidget(self.btn_fit)
        toolbar.addWidget(self.btn_actual)
        layout.addLayout(toolbar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.canvas = PdfCanvas()
        self.scroll_area.setWidget(self.canvas)
        layout.addWidget(self.scroll_area, stretch=1)

        coord_layout = QHBoxLayout()
        self.lbl_mouse = QLabel("当前坐标：X: 0, Y: 0")
        self.lbl_bbox = QLabel("框选区域：左: 0, 上: 0, 右: 0, 下: 0")
        coord_layout.addWidget(self.lbl_mouse)
        coord_layout.addWidget(self.lbl_bbox)
        layout.addLayout(coord_layout)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #0078D7; font-weight: bold;")
        layout.addWidget(self.lbl_status)

        btn_layout = QHBoxLayout()
        self.btn_clear = QPushButton("清除框选")
        self.btn_confirm = QPushButton("确认坐标")
        self.btn_close = QPushButton("关闭")
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_confirm)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next.clicked.connect(self._next_page)
        self.btn_zoom_in.clicked.connect(lambda: self._change_zoom(1.25))
        self.btn_zoom_out.clicked.connect(lambda: self._change_zoom(0.8))
        self.btn_fit.clicked.connect(self._fit_window)
        self.btn_actual.clicked.connect(self._actual_size)
        self.btn_clear.clicked.connect(self._clear_selection)
        self.btn_confirm.clicked.connect(self._confirm_coords)
        self.btn_close.clicked.connect(self.reject)
        self.canvas.coordinates_changed.connect(self._on_bbox_changed)
        self.canvas.mouse_moved.connect(self._on_mouse_moved)

    def _load_pdf(self):
        try:
            if not os.path.exists(self._pdf_path):
                QMessageBox.critical(self, "错误", "PDF 文件不存在")
                self.reject()
                return
            self._doc = fitz.open(self._pdf_path)
            self._current_page = 0
            self._render_page()
        except Exception as e:
            logger.exception("打开 PDF 失败")
            QMessageBox.critical(self, "错误", f"无法打开 PDF 文件：{e}")
            self.reject()

    def _render_page(self):
        if not self._doc:
            return
        page = self._doc[self._current_page]
        page_h = page.rect.height

        # 关键词模式：先画高亮再渲染
        if self._mode in ("anchor", "table_column") and self._keywords:
            self._draw_highlights(page)

        if self._fit_mode == "fit":
            viewport = self.scroll_area.viewport().size()
            scale_x = (viewport.width() - 20) / page.rect.width
            scale_y = (viewport.height() - 20) / page.rect.height
            self._zoom = min(scale_x, scale_y, 3.0)
            if self._zoom <= 0:
                self._zoom = 1.0
        elif self._fit_mode == "actual":
            self._zoom = 1.0

        mat = fitz.Matrix(self._zoom, self._zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(img.copy())
        self.canvas.set_page_image(pixmap, page_h, self._zoom)

        total = len(self._doc)
        self.lbl_page.setText(f"第 {self._current_page + 1} 页 / 共 {total} 页")
        self.btn_prev.setEnabled(self._current_page > 0)
        self.btn_next.setEnabled(self._current_page < total - 1)

    def _draw_highlights(self, page) -> None:
        """在 PDF 页面上用半透明矩形标注关键词匹配位置。"""
        colors = [
            (1, 0.3, 0.3),   # 红
            (0.3, 0.6, 1),   # 蓝
            (0.3, 0.8, 0.4),  # 绿
            (1, 0.7, 0.2),   # 橙
            (0.7, 0.4, 1),   # 紫
        ]
        for i, kw in enumerate(self._keywords):
            if not kw:
                continue
            color = colors[i % len(colors)]
            areas = page.search_for(kw)
            for rect in areas:
                page.draw_rect(rect, color=color, fill=color, fill_opacity=0.2,
                               width=0.5, overlay=True)

    def _prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._clear_selection()
            self._render_page()

    def _next_page(self):
        if self._doc and self._current_page < len(self._doc) - 1:
            self._current_page += 1
            self._clear_selection()
            self._render_page()

    def _change_zoom(self, factor: float):
        self._fit_mode = "custom"
        self._zoom = max(0.25, min(self._zoom * factor, 5.0))
        self._render_page()

    def _fit_window(self):
        self._fit_mode = "fit"
        self._render_page()

    def _actual_size(self):
        self._fit_mode = "actual"
        self._render_page()

    def _clear_selection(self):
        self.canvas.clear_selection()
        self._pdf_bbox = (0, 0, 0, 0)
        self.lbl_bbox.setText("框选区域：左: 0, 上: 0, 右: 0, 下: 0")

    def _on_mouse_moved(self, x: int, y: int):
        self.lbl_mouse.setText(f"当前坐标：X: {x}, Y: {y}")

    def _on_bbox_changed(self, x1: int, y1: int, x2: int, y2: int):
        self._pdf_bbox = (x1, y1, x2, y2)
        self.lbl_bbox.setText(
            f"框选区域：左: {x1}, 下: {y1}, 右: {x2}, 上: {y2}"
        )

    def _confirm_coords(self):
        x1, y1, x2, y2 = self._pdf_bbox
        if x1 == x2 and y1 == y2:
            QMessageBox.warning(self, "提示", "请先框选提取区域")
            return
        page_num = self._current_page + 1

        self.coordinates_confirmed.emit(x1, y1, x2, y2, page_num)
        self.lbl_status.setText(
            f"坐标已确认（第 {page_num} 页），可继续框选下一条规则"
        )
        self._clear_selection()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit_mode == "fit" and self._doc:
            self._render_page()

    def closeEvent(self, event):
        if self._doc:
            self._doc.close()
        super().closeEvent(event)
