# -*- coding: utf-8 -*-
"""主界面：文件管理、处理控制、总内容编辑。"""

import logging
import os
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QShortcut,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app_utils import get_app_dir, get_exe_dir
from batch_confirm_dialog import BatchConfirmDialog, SOURCE_COL
from config_dialog import ConfigDialog
from config_manager import ConfigManager
from excel_generator import ExcelGenerator
from extraction_worker import ExtractionWorker
from pdf_extractor import PdfExtractor
from session_manager import SessionManager
from single_confirm_dialog import SingleConfirmDialog
from table_utils import table_to_records

logger = logging.getLogger(__name__)

STATUS_PENDING = "待处理"
STATUS_PROCESSING = "处理中"
STATUS_CONFIRMED = "已确认"
STATUS_SKIPPED = "已跳过"


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def basename(path: str) -> str:
    return os.path.basename(path)


class MainWindow(QMainWindow):
    """主窗口。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF信息提取与Excel生成工具")
        self.resize(1000, 700)
        self.setAcceptDrops(True)

        self.config = ConfigManager.get_default()
        # 优先加载 EXE 目录下的 default.cfg（用户可覆盖），其次使用内置默认
        self.config_path = os.path.join(get_exe_dir(), "default.cfg")
        if not os.path.exists(self.config_path):
            bundled = os.path.join(get_app_dir(), "default.cfg")
            if os.path.exists(bundled):
                self.config_path = bundled
        if os.path.exists(self.config_path):
            self.config = ConfigManager.load(self.config_path)

        self.files: List[dict] = []  # {path, size, status}
        self.confirmed_records: List[dict] = []
        self.session_manager = SessionManager()
        self._worker: Optional[ExtractionWorker] = None
        self._pending_paths: List[str] = []
        self._pending_results: List[dict] = []
        self._single_file_mode = False

        self._init_ui()
        self._setup_shortcuts()
        self._restore_session()
        self._update_ui_state()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.lbl_file_stats = QLabel("已选择文件（共0个，已处理0个，待处理0个）：")
        layout.addWidget(self.lbl_file_stats)

        self.file_table = QTableWidget()
        self.file_table.setColumnCount(4)
        self.file_table.setHorizontalHeaderLabels(["序号", "文件名", "文件大小", "状态"])
        self.file_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.file_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.file_table.setAlternatingRowColors(True)
        layout.addWidget(self.file_table)

        file_btn_layout = QHBoxLayout()
        self.btn_open = QPushButton("打开")
        self.btn_remove = QPushButton("移除选中")
        self.btn_clear = QPushButton("清空列表")
        file_btn_layout.addWidget(self.btn_open)
        file_btn_layout.addWidget(self.btn_remove)
        file_btn_layout.addWidget(self.btn_clear)
        file_btn_layout.addStretch()
        layout.addLayout(file_btn_layout)

        self.btn_start = QPushButton("开始处理")
        self.btn_start.setProperty("class", "primary")
        layout.addWidget(self.btn_start)

        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("进度："))
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        layout.addLayout(progress_layout)

        self.lbl_status = QLabel("状态：就绪")
        layout.addWidget(self.lbl_status)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setEnabled(False)
        layout.addWidget(self.btn_cancel)

        layout.addWidget(QLabel("─" * 60))

        self.lbl_record_stats = QLabel("已确认内容（共0条记录）：")
        layout.addWidget(self.lbl_record_stats)

        self.content_table = QTableWidget()
        self.content_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.content_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.content_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.content_table.setAlternatingRowColors(True)
        layout.addWidget(self.content_table)

        content_btn_layout = QHBoxLayout()
        self.btn_add_record = QPushButton("添加行")
        self.btn_delete_records = QPushButton("删除选中行")
        self.btn_clear_records = QPushButton("清空全部")
        content_btn_layout.addWidget(self.btn_add_record)
        content_btn_layout.addWidget(self.btn_delete_records)
        content_btn_layout.addWidget(self.btn_clear_records)
        content_btn_layout.addStretch()
        layout.addLayout(content_btn_layout)

        bottom_layout = QHBoxLayout()
        self.btn_config = QPushButton("配置提取规则")
        self.btn_load_cfg = QPushButton("加载配置")
        self.btn_save_cfg = QPushButton("保存配置")
        self.btn_export = QPushButton("生成Excel")
        self.btn_export.setProperty("class", "primary")
        bottom_layout.addWidget(self.btn_config)
        bottom_layout.addWidget(self.btn_load_cfg)
        bottom_layout.addWidget(self.btn_save_cfg)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_export)
        layout.addLayout(bottom_layout)

        self.btn_open.clicked.connect(self._open_files)
        self.btn_remove.clicked.connect(self._remove_selected_files)
        self.btn_clear.clicked.connect(self._clear_files)
        self.btn_start.clicked.connect(self._start_processing)
        self.btn_cancel.clicked.connect(self._cancel_processing)
        self.btn_config.clicked.connect(self._open_config_dialog)
        self.btn_load_cfg.clicked.connect(self._load_config)
        self.btn_save_cfg.clicked.connect(self._save_config)
        self.btn_export.clicked.connect(self._export_excel)
        self.btn_add_record.clicked.connect(self._add_content_row)
        self.btn_delete_records.clicked.connect(self._delete_content_rows)
        self.btn_clear_records.clicked.connect(self._clear_all_records)
        self.content_table.cellChanged.connect(self._on_content_changed)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+O"), self, self._open_files)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_config)
        QShortcut(QKeySequence.Delete, self, self._delete_content_rows)

    def _content_columns(self) -> List[str]:
        cols = ConfigManager.get_column_names(self.config)
        if SOURCE_COL not in cols:
            cols.append(SOURCE_COL)
        return cols

    def _refresh_file_table(self):
        self.file_table.setRowCount(len(self.files))
        for idx, f in enumerate(self.files):
            self.file_table.setItem(idx, 0, QTableWidgetItem(str(idx + 1)))
            name = basename(f["path"])
            if not f.get("exists", True):
                name += " (文件不存在)"
            self.file_table.setItem(idx, 1, QTableWidgetItem(name))
            self.file_table.setItem(idx, 2, QTableWidgetItem(format_size(f.get("size", 0))))
            self.file_table.setItem(idx, 3, QTableWidgetItem(f.get("status", STATUS_PENDING)))
        self._update_file_stats()

    def _update_file_stats(self):
        total = len(self.files)
        processed = sum(1 for f in self.files if f["status"] in (STATUS_CONFIRMED, STATUS_SKIPPED))
        pending = total - processed
        self.lbl_file_stats.setText(
            f"已选择文件（共{total}个，已处理{processed}个，待处理{pending}个）："
        )

    def _refresh_content_table(self):
        cols = self._content_columns()
        self.content_table.blockSignals(True)
        self.content_table.setColumnCount(len(cols))
        self.content_table.setHorizontalHeaderLabels(cols)
        self.content_table.setRowCount(len(self.confirmed_records))
        for row, record in enumerate(self.confirmed_records):
            for col_idx, col_name in enumerate(cols):
                val = record.get(col_name, "")
                self.content_table.setItem(row, col_idx, QTableWidgetItem(str(val)))
        self.content_table.blockSignals(False)
        self.lbl_record_stats.setText(f"已确认内容（共{len(self.confirmed_records)}条记录）：")

    def _update_ui_state(self):
        all_done = (
            len(self.files) > 0
            and all(f["status"] in (STATUS_CONFIRMED, STATUS_SKIPPED) for f in self.files)
        )
        self.btn_export.setEnabled(all_done)
        self.btn_start.setEnabled(len(self.files) > 0 and self._worker is None)
        self.btn_clear_records.setEnabled(len(self.confirmed_records) > 0)

    def _open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择 PDF 文件", "", "PDF 文件 (*.pdf)")
        if paths:
            self._add_files(paths)

    def _add_files(self, paths: List[str]):
        existing = {f["path"] for f in self.files}
        duplicates = []
        for path in paths:
            path = os.path.abspath(path)
            if not path.lower().endswith(".pdf"):
                QMessageBox.warning(self, "错误", f"不是 PDF 文件：{basename(path)}")
                continue
            if path in existing:
                duplicates.append(basename(path))
                continue
            if not os.path.exists(path):
                QMessageBox.warning(self, "错误", f"文件不存在：{path}")
                continue
            size = os.path.getsize(path)
            self.files.append({"path": path, "size": size, "status": STATUS_PENDING, "exists": True})
            existing.add(path)
            logger.info("添加文件: %s", path)
        if duplicates:
            QMessageBox.information(self, "提示", f"以下文件已存在，已跳过：{', '.join(duplicates)}")
        self._refresh_file_table()
        self._update_ui_state()
        self._save_session()

    def _remove_selected_files(self):
        rows = sorted({idx.row() for idx in self.file_table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for row in rows:
            self.files.pop(row)
        self._refresh_file_table()
        self._update_ui_state()
        self._save_session()

    def _clear_files(self):
        if not self.files:
            return
        reply = QMessageBox.question(self, "确认", "确定清空所有文件？")
        if reply == QMessageBox.Yes:
            self.files.clear()
            self._refresh_file_table()
            self._update_ui_state()
            self._save_session()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                paths.append(url.toLocalFile())
        if paths:
            self._add_files(paths)

    def _start_processing(self):
        pending = [f for f in self.files if f["status"] == STATUS_PENDING]
        if not pending:
            QMessageBox.information(self, "提示", "没有待处理的文件")
            return
        self._pending_paths = [f["path"] for f in pending]
        self._single_file_mode = len(self.files) == 1
        for f in pending:
            f["status"] = STATUS_PROCESSING
        self._refresh_file_table()

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)

        self._worker = ExtractionWorker(self.config, self._pending_paths, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.file_failed.connect(self._on_file_failed)
        self._worker.finished_all.connect(self._on_extraction_finished)
        self._worker.start()

    def _on_progress(self, current: int, total: int, filename: str):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.lbl_status.setText(f"状态：正在处理：{basename(filename)}")

    def _on_file_failed(self, path: str, error_msg: str):
        msg = QMessageBox(self)
        msg.setWindowTitle("提取失败")
        msg.setText(f"文件 {basename(path)} 提取失败：{error_msg}")
        msg.setInformativeText("跳过该文件还是取消全部处理？")
        btn_skip = msg.addButton("跳过该文件", QMessageBox.AcceptRole)
        btn_cancel_all = msg.addButton("取消全部处理", QMessageBox.RejectRole)
        msg.exec_()
        if msg.clickedButton() == btn_skip:
            for f in self.files:
                if f["path"] == path:
                    f["status"] = STATUS_SKIPPED
        elif msg.clickedButton() == btn_cancel_all:
            if self._worker:
                self._worker.cancel()

    def _cancel_processing(self):
        if self._worker:
            self._worker.cancel()
        self.lbl_status.setText("状态：已取消")
        for f in self.files:
            if f["status"] == STATUS_PROCESSING:
                f["status"] = STATUS_PENDING
        self._refresh_file_table()
        self._reset_worker()

    def _reset_worker(self):
        self.btn_cancel.setEnabled(False)
        self.btn_start.setEnabled(True)
        self._worker = None
        self._update_ui_state()

    def _on_extraction_finished(self, results: List[dict], was_cancelled: bool = False):
        self._pending_results = results
        self._reset_worker()
        if was_cancelled:
            self.lbl_status.setText("状态：已取消")
            self._refresh_file_table()
            self._save_session()
            return
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.lbl_status.setText("状态：提取完成")

        if not results:
            return

        cols = ConfigManager.get_column_names(self.config)

        if self._single_file_mode and len(results) == 1:
            self._handle_single_confirm(results[0], cols)
        else:
            self._handle_batch_confirm(results, cols)

    def _handle_single_confirm(self, result: dict, cols: List[str]):
        if result.get("status") == "failed":
            for f in self.files:
                if f["path"] == result["source_file"]:
                    f["status"] = STATUS_SKIPPED
            self._refresh_file_table()
            self._update_ui_state()
            self._save_session()
            return

        # v2: 从 records 列表展开记录
        records = result.get("records", [])
        if not records:
            records = [{}]
        source_name = basename(result["source_file"])
        for r in records:
            r[SOURCE_COL] = source_name
        issues = result.get("field_issues", {})

        while True:
            dlg = SingleConfirmDialog(
                source_name, cols, records, issues, self
            )
            dlg.exec_()
            if dlg.wants_reextract():
                extractor_results = PdfExtractor(self.config).extract_single(
                    result["source_file"]
                )
                records = extractor_results.get("records", [])
                if not records:
                    records = [{}]
                for r in records:
                    r[SOURCE_COL] = source_name
                issues = extractor_results.get("field_issues", {})
                continue
            if dlg.is_confirmed():
                records = dlg.get_records()
                self.confirmed_records.extend(records)
                for f in self.files:
                    if f["path"] == result["source_file"]:
                        f["status"] = STATUS_CONFIRMED
                break
            else:
                for f in self.files:
                    if f["path"] == result["source_file"]:
                        f["status"] = STATUS_PENDING
                break

        self._refresh_file_table()
        self._refresh_content_table()
        self._update_ui_state()
        self._save_session()

    def _on_reextract_finished(self, results: List[dict], was_cancelled: bool, cols: List[str]):
        """批量重新提取完成回调。"""
        self._reset_worker()
        if was_cancelled:
            for f in self.files:
                if f["status"] == STATUS_PROCESSING:
                    f["status"] = STATUS_PENDING
            self._refresh_file_table()
            return
        self._handle_batch_confirm(results, cols)

    def _handle_batch_confirm(self, results: List[dict], cols: List[str]):
        display_cols = cols + [SOURCE_COL]
        records = []
        issues_map: Dict[int, Dict[str, str]] = {}
        success = 0
        failed = 0

        for result in results:
            if result.get("status") == "failed":
                failed += 1
                for f in self.files:
                    if f["path"] == result.get("source_file"):
                        f["status"] = STATUS_SKIPPED
                continue
            success += 1
            source_name = basename(result["source_file"])
            # v2: 展开 records 列表
            sub_records = result.get("records", [])
            if not sub_records:
                sub_records = [{}]
            for sub in sub_records:
                record = {col: sub.get(col, "") for col in cols}
                record[SOURCE_COL] = source_name
                records.append(record)
            if result.get("field_issues"):
                # 将 issues 标记到该结果的第一条 record
                issues_map[len(records) - len(sub_records)] = result["field_issues"]

        stats = {
            "total": len(results),
            "success": success,
            "failed": failed,
            "records": len(records),
        }

        while True:
            dlg = BatchConfirmDialog(display_cols, records, stats, issues_map, self)
            dlg.exec_()
            if dlg.wants_reextract_all():
                for f in self.files:
                    if f["path"] in self._pending_paths:
                        f["status"] = STATUS_PROCESSING
                self._refresh_file_table()
                self.btn_start.setEnabled(False)
                self.btn_cancel.setEnabled(True)
                self._worker = ExtractionWorker(self.config, self._pending_paths, self)
                self._worker.progress.connect(self._on_progress)
                self._worker.file_failed.connect(self._on_file_failed)
                self._worker.finished_all.connect(
                    lambda r, c: self._on_reextract_finished(r, c, cols)
                )
                self._worker.start()
                return
            if dlg.is_confirmed():
                records = dlg.get_records()
                self.confirmed_records.extend(records)
                for f in self.files:
                    if f["path"] in self._pending_paths:
                        f["status"] = STATUS_CONFIRMED
                break
            else:
                for f in self.files:
                    if f["status"] == STATUS_PROCESSING:
                        f["status"] = STATUS_PENDING
                break

        self._refresh_file_table()
        self._refresh_content_table()
        self._update_ui_state()
        self._save_session()

    def _open_config_dialog(self):
        dlg = ConfigDialog(self.config, self.config_path, self)
        if dlg.exec_():
            self.config = dlg.get_config()
            self.config_path = dlg.get_config_path() or self.config_path
            self._refresh_content_table()
            self._save_session()

    def _load_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "加载配置", "", "配置文件 (*.cfg)")
        if path:
            self.config = ConfigManager.load(path)
            self.config_path = path
            self._refresh_content_table()
            self._save_session()
            QMessageBox.information(self, "成功", "配置已加载")

    def _save_config(self):
        if ConfigManager.save(self.config, self.config_path):
            QMessageBox.information(self, "成功", "配置已保存")
        else:
            QMessageBox.critical(self, "错误", "保存配置失败")

    def _export_excel(self):
        cols = self._content_columns()
        records = list(self.confirmed_records)
        if not records:
            QMessageBox.warning(self, "提示", "没有可导出的数据")
            return

        default_name = ExcelGenerator.default_filename()
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 Excel 文件", default_name, "Excel 文件 (*.xlsx)"
        )
        if not path:
            return
        if not path.endswith(".xlsx"):
            path += ".xlsx"

        gen = ExcelGenerator(cols)
        if gen.generate(records, path):
            msg = QMessageBox(self)
            msg.setWindowTitle("成功")
            msg.setText(f"Excel 文件已生成：\n{path}")
            btn_open = msg.addButton("打开文件", QMessageBox.ActionRole)
            btn_folder = msg.addButton("打开文件夹", QMessageBox.ActionRole)
            btn_close = msg.addButton("关闭", QMessageBox.RejectRole)
            msg.exec_()
            clicked = msg.clickedButton()
            if clicked == btn_open:
                os.startfile(path)
            elif clicked == btn_folder:
                os.startfile(os.path.dirname(path))
            elif clicked == btn_close:
                # 导出成功后自动清空文件列表和已确认内容
                self.files.clear()
                self.confirmed_records.clear()
                self._refresh_file_table()
                self._refresh_content_table()
                self._update_ui_state()
                self._save_session()
            logger.info("Excel 导出成功: %s", path)
        else:
            QMessageBox.critical(
                self,
                "错误",
                "生成 Excel 失败，请检查磁盘空间或文件是否被其他程序占用",
            )

    def _add_content_row(self):
        cols = self._content_columns()
        record = {col: "" for col in cols}
        self.confirmed_records.append(record)
        self._refresh_content_table()
        self._save_session()

    def _delete_content_rows(self):
        rows = sorted({idx.row() for idx in self.content_table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for row in rows:
            if row < len(self.confirmed_records):
                self.confirmed_records.pop(row)
        self._refresh_content_table()
        self._save_session()

    def _clear_all_records(self):
        """一键清空全部已确认内容。"""
        if not self.confirmed_records:
            return
        count = len(self.confirmed_records)
        reply = QMessageBox.question(
            self, "确认清空",
            f"确定清空全部已确认内容？（共 {count} 条记录）"
        )
        if reply == QMessageBox.Yes:
            self.confirmed_records.clear()
            self._refresh_content_table()
            self._update_ui_state()
            self._save_session()

    def _on_content_changed(self):
        self.confirmed_records = table_to_records(self.content_table, self._content_columns())
        self.lbl_record_stats.setText(f"已确认内容（共{len(self.confirmed_records)}条记录）：")
        self._save_session()

    def _save_session(self):
        data = SessionManager.build_session_data(
            self.config,
            self.config_path,
            self.files,
            self.confirmed_records,
        )
        self.session_manager.schedule_save(data)

    def _restore_session(self):
        data = self.session_manager.restore()
        if not data:
            self._refresh_content_table()
            return
        try:
            self.config = data.get("config", self.config)
            self.config_path = data.get("config_path", self.config_path)
            self.files = SessionManager.validate_restored_files(data.get("files", []))
            self.confirmed_records = data.get("confirmed_records", [])
            missing = [basename(f["path"]) for f in self.files if not f.get("exists", True)]
            if missing:
                QMessageBox.warning(
                    self,
                    "提示",
                    f"以下文件已不存在，请重新选择：{', '.join(missing)}",
                )
            self._refresh_file_table()
            self._refresh_content_table()
            logger.info("会话已恢复")
        except Exception as e:
            logger.exception("恢复会话失败: %s", e)

    def closeEvent(self, event):
        data = SessionManager.build_session_data(
            self.config,
            self.config_path,
            self.files,
            self.confirmed_records,
        )
        self.session_manager.save_now(data)
        if self._worker:
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)
