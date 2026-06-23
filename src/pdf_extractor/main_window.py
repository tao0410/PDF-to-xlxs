# -*- coding: utf-8 -*-
"""主界面：文件管理、处理控制、总内容编辑 (v2.2)。"""

import logging
import os
import time
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
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
from excel_option_dialog import ExcelOptionDialog
from extraction_worker import ExtractionWorker
from pdf_extractor import PdfExtractor
from repeat_dialog import RepeatDialog
from session_manager import SessionManager
from single_confirm_dialog import SingleConfirmDialog
from table_utils import table_to_records
from unprocessed_dialog import UnprocessedDialog

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
        self.setWindowTitle("PDF信息提取工具")
        self.resize(1000, 700)
        self.setMinimumSize(800, 550)
        self.setAcceptDrops(True)

        self.config = ConfigManager.get_default()
        self.config_path = os.path.join(get_exe_dir(), "default.cfg")
        if not os.path.exists(self.config_path):
            bundled = os.path.join(get_app_dir(), "default.cfg")
            if os.path.exists(bundled):
                self.config_path = bundled
        if os.path.exists(self.config_path):
            self.config = ConfigManager.load(self.config_path)

        self.files: List[dict] = []           # {path, size, status, checked, exists}
        self.confirmed_records: List[dict] = []
        self.session_manager = SessionManager()
        self._worker: Optional[ExtractionWorker] = None
        self._pending_paths: List[str] = []
        self._pending_results: List[dict] = []
        self._single_file_mode = False
        self._file_start: Dict[str, float] = {}

        self._init_ui()
        self._setup_shortcuts()
        self._restore_session()
        self._update_ui_state()

    # ═══════════════ UI ═══════════════

    def _init_ui(self):
        # ── Scroll Area (supports small window sizes) ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setCentralWidget(scroll)

        central = QWidget()
        scroll.setWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(24)

        # ── Card 1: File List ──
        file_card = QFrame(objectName="card")
        fc = QVBoxLayout(file_card)
        fc.setContentsMargins(24, 24, 24, 24)
        fc.setSpacing(12)

        hdr = QHBoxLayout()
        lbl = QLabel("已选择文件", objectName="section-title")
        hdr.addWidget(lbl)
        hdr.addStretch()
        self.lbl_file_stats = QLabel("共 0 个，已处理 0 个，待处理 0 个", objectName="hint-text")
        hdr.addWidget(self.lbl_file_stats)
        fc.addLayout(hdr)

        self.file_table = QTableWidget()
        self.file_table.setColumnCount(6)
        self.file_table.setHorizontalHeaderLabels(["", "#", "文件名", "大小", "状态", "耗时"])
        hh = self.file_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        self.file_table.setColumnWidth(0, 40)
        hh.setSectionResizeMode(1, QHeaderView.Fixed)
        self.file_table.setColumnWidth(1, 40)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        self.file_table.setColumnWidth(3, 80)
        hh.setSectionResizeMode(4, QHeaderView.Fixed)
        self.file_table.setColumnWidth(4, 90)
        hh.setSectionResizeMode(5, QHeaderView.Fixed)
        self.file_table.setColumnWidth(5, 70)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.file_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setSizeAdjustPolicy(QAbstractItemView.AdjustToContents)
        self.file_table.setMinimumHeight(120)
        fc.addWidget(self.file_table)

        bot = QHBoxLayout()
        self.lbl_checked = QLabel("已选中 0 项", objectName="hint-text")
        bot.addWidget(self.lbl_checked)
        bot.addStretch()
        self.btn_open = QPushButton("打开")
        self.btn_remove = QPushButton("移除选中")
        self.btn_clear = QPushButton("清空")
        self.btn_clear.setObjectName("btn-ghost")
        bot.addWidget(self.btn_open)
        bot.addWidget(self.btn_remove)
        bot.addWidget(self.btn_clear)
        fc.addLayout(bot)
        file_card.setMinimumHeight(180)
        layout.addWidget(file_card)

        # ── Card 2: Processing ──
        proc_card = QFrame(objectName="card")
        pc = QVBoxLayout(proc_card)
        pc.setContentsMargins(24, 20, 24, 20)
        pc.setSpacing(10)

        self.lbl_banner = QLabel()
        self.lbl_banner.setVisible(False)
        self.lbl_banner.setWordWrap(True)
        pc.addWidget(self.lbl_banner)

        row = QHBoxLayout()
        self.btn_start = QPushButton("开始处理")
        self.btn_start.setObjectName("btn-primary")
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setObjectName("btn-ghost")
        self.btn_cancel.setEnabled(False)
        row.addWidget(self.btn_start)
        row.addWidget(self.btn_cancel)
        row.addStretch()
        pc.addLayout(row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        pc.addWidget(self.progress_bar)

        self.lbl_status = QLabel("就绪", objectName="hint-text")
        pc.addWidget(self.lbl_status)
        layout.addWidget(proc_card)

        # ── Card 3: Confirmed Content ──
        content_card = QFrame(objectName="card")
        cc = QVBoxLayout(content_card)
        cc.setContentsMargins(24, 20, 24, 20)
        cc.setSpacing(12)

        hdr2 = QHBoxLayout()
        lbl2 = QLabel("已确认内容", objectName="section-title")
        hdr2.addWidget(lbl2)
        self.lbl_record_stats = QLabel("共 0 条记录", objectName="hint-text")
        hdr2.addWidget(self.lbl_record_stats)
        hdr2.addStretch()
        self.btn_add_record = QPushButton("添加行")
        self.btn_delete_records = QPushButton("删除选中")
        self.btn_delete_records.setObjectName("btn-ghost")
        self.btn_clear_records = QPushButton("清空全部")
        self.btn_clear_records.setObjectName("btn-ghost")
        hdr2.addWidget(self.btn_add_record)
        hdr2.addWidget(self.btn_delete_records)
        hdr2.addWidget(self.btn_clear_records)
        cc.addLayout(hdr2)

        self.content_table = QTableWidget()
        self.content_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.content_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.content_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.content_table.setAlternatingRowColors(True)
        self.content_table.verticalHeader().setVisible(False)
        self.content_table.setSizeAdjustPolicy(QAbstractItemView.AdjustToContents)
        self.content_table.setMinimumHeight(100)
        cc.addWidget(self.content_table)
        content_card.setMinimumHeight(160)
        layout.addWidget(content_card, 1)  # stretch factor 1 — this card expands

        # ── Bottom Bar ──
        bar = QFrame(objectName="toolbar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(0, 0, 0, 0)
        self.btn_config = QPushButton("配置提取规则")
        self.btn_export = QPushButton("生成 Excel")
        self.btn_export.setObjectName("btn-primary")
        bl.addWidget(self.btn_config)
        bl.addStretch()
        bl.addWidget(self.btn_export)
        layout.addWidget(bar)

        # ── Connections ──
        self.btn_open.clicked.connect(self._open_files)
        self.btn_remove.clicked.connect(self._remove_selected_files)
        self.btn_clear.clicked.connect(self._clear_files)
        self.btn_start.clicked.connect(self._start_processing)
        self.btn_cancel.clicked.connect(self._cancel_processing)
        self.btn_config.clicked.connect(self._open_config_dialog)
        self.btn_export.clicked.connect(self._export_excel)
        self.btn_add_record.clicked.connect(self._add_content_row)
        self.btn_delete_records.clicked.connect(self._delete_content_rows)
        self.btn_clear_records.clicked.connect(self._clear_all_records)
        self.content_table.cellChanged.connect(self._on_content_changed)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+O"), self, self._open_files)
        QShortcut(QKeySequence("Ctrl+E"), self, self._export_excel)
        QShortcut(QKeySequence("Ctrl+D"), self, self._open_config_dialog)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_config)
        QShortcut(QKeySequence.Delete, self, self._delete_content_rows)

    # ═══════════════ Helpers ═══════════════

    def _content_columns(self) -> List[str]:
        cols = ConfigManager.get_column_names(self.config)
        if SOURCE_COL not in cols:
            cols.append(SOURCE_COL)
        return cols

    # ═══════════════ File Table ═══════════════

    def _refresh_file_table(self):
        self.file_table.setRowCount(len(self.files))
        for idx, f in enumerate(self.files):
            # Column 0: checkbox
            item = QTableWidgetItem()
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item.setCheckState(Qt.Checked if f.get("checked", True) else Qt.Unchecked)
            self.file_table.setItem(idx, 0, item)
            # Column 1: index
            self.file_table.setItem(idx, 1, QTableWidgetItem(str(idx + 1)))
            # Column 2: filename
            name = basename(f["path"])
            if not f.get("exists", True):
                name += " (文件不存在)"
            self.file_table.setItem(idx, 2, QTableWidgetItem(name))
            # Column 3: size
            self.file_table.setItem(idx, 3, QTableWidgetItem(format_size(f.get("size", 0))))
            # Column 4: status
            status = f.get("status", STATUS_PENDING)
            self.file_table.setItem(idx, 4, QTableWidgetItem(status))
            if status == STATUS_CONFIRMED:
                self.file_table.item(idx, 4).setForeground(Qt.darkGreen)
            elif status == STATUS_SKIPPED:
                self.file_table.item(idx, 4).setForeground(Qt.gray)
            # Column 5: elapsed time
            elapsed = f.get("elapsed", "")
            self.file_table.setItem(idx, 5, QTableWidgetItem(elapsed))
        self._update_file_stats()

    def _sync_checks(self):
        """从表格读回复选框状态。"""
        for idx in range(min(self.file_table.rowCount(), len(self.files))):
            item = self.file_table.item(idx, 0)
            if item:
                self.files[idx]["checked"] = (item.checkState() == Qt.Checked)

    def _update_file_stats(self):
        total = len(self.files)
        checked = sum(1 for f in self.files if f.get("checked", True))
        processed = sum(1 for f in self.files if f["status"] in (STATUS_CONFIRMED, STATUS_SKIPPED))
        pending = total - processed
        self.lbl_file_stats.setText(
            f"共 {total} 个，已处理 {processed} 个，待处理 {pending} 个"
        )
        self.lbl_checked.setText(f"已选中 {checked} 项")

    # ═══════════════ Content Table ═══════════════

    def _refresh_content_table(self):
        cols = self._content_columns()
        self.content_table.blockSignals(True)
        self.content_table.setColumnCount(len(cols))
        self.content_table.setHorizontalHeaderLabels(cols)
        self.content_table.setRowCount(len(self.confirmed_records))
        for row, record in enumerate(self.confirmed_records):
            for ci, cn in enumerate(cols):
                self.content_table.setItem(row, ci, QTableWidgetItem(str(record.get(cn, ""))))
        self.content_table.blockSignals(False)
        self.lbl_record_stats.setText(f"共 {len(self.confirmed_records)} 条记录")

    def _update_ui_state(self):
        has_records = len(self.confirmed_records) > 0
        has_pending = any(
            f["status"] == STATUS_PENDING and f.get("checked", True)
            for f in self.files
        )
        all_processed = (
            len(self.files) > 0 and
            all(f["status"] in (STATUS_CONFIRMED, STATUS_SKIPPED) for f in self.files)
        )
        self.btn_start.setEnabled(has_pending and self._worker is None)
        self.btn_cancel.setEnabled(self._worker is not None)
        self.btn_export.setEnabled(has_records)
        self.btn_clear_records.setEnabled(has_records)

        # Banner
        if all_processed and has_records:
            self.lbl_banner.setText(
                f"✓ 全部 {len(self.files)} 个文件处理完成，共 {len(self.confirmed_records)} 条记录"
            )
            self.lbl_banner.setObjectName("success-banner")
            self.lbl_banner.setVisible(True)
        elif self._worker:
            self.lbl_banner.setVisible(False)
        # Force restyle
        self.lbl_banner.style().unpolish(self.lbl_banner)
        self.lbl_banner.style().polish(self.lbl_banner)

    # ═══════════════ File Operations ═══════════════

    def _open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择 PDF 文件", "", "PDF 文件 (*.pdf)")
        if paths:
            self._add_files(paths)

    def _add_files(self, paths: List[str]):
        existing = {f["path"] for f in self.files}
        dups = []
        for p in paths:
            p = os.path.abspath(p)
            if not p.lower().endswith(".pdf"):
                QMessageBox.warning(self, "错误", f"不是 PDF 文件：{basename(p)}")
                continue
            if p in existing:
                dups.append(basename(p))
                continue
            if not os.path.exists(p):
                QMessageBox.warning(self, "错误", f"文件不存在：{p}")
                continue
            sz = os.path.getsize(p)
            self.files.append({
                "path": p, "size": sz, "status": STATUS_PENDING,
                "checked": True, "exists": True
            })
            existing.add(p)
            logger.info("添加文件: %s", p)
        if dups:
            QMessageBox.information(self, "提示", f"以下文件已存在，已跳过：{', '.join(dups)}")
        self._refresh_file_table()
        self._update_ui_state()
        self._save_session()

    def _remove_selected_files(self):
        rows = sorted({i.row() for i in self.file_table.selectedIndexes()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "提示", "请先选择要移除的文件行")
            return
        for r in rows:
            if r < len(self.files):
                self.files.pop(r)
        self._refresh_file_table()
        self._update_ui_state()
        self._save_session()

    def _clear_files(self):
        if not self.files:
            return
        if QMessageBox.question(self, "确认", "确定清空所有文件？") == QMessageBox.Yes:
            self.files.clear()
            self._refresh_file_table()
            self._update_ui_state()
            self._save_session()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self._add_files(paths)

    # ═══════════════ Processing ═══════════════

    def _start_processing(self):
        self._sync_checks()
        pending = [
            f for f in self.files
            if f["status"] == STATUS_PENDING and f.get("checked", True)
        ]
        if not pending:
            all_done = all(
                f["status"] in (STATUS_CONFIRMED, STATUS_SKIPPED) for f in self.files
            )
            if all_done and self.files:
                QMessageBox.information(self, "提示", "所有文件已处理完毕，请导出 Excel")
            else:
                QMessageBox.information(self, "提示", "没有待处理的文件（请勾选需处理的文件）")
            return

        self._pending_paths = [f["path"] for f in pending]
        self._single_file_mode = len(pending) == 1
        self._file_start = {}  # track start time per path
        for f in pending:
            f["status"] = STATUS_PROCESSING
            self._file_start[f["path"]] = time.time()
        self._refresh_file_table()

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.lbl_banner.setVisible(False)
        self.progress_bar.setValue(0)

        self._worker = ExtractionWorker(self.config, self._pending_paths, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.file_failed.connect(self._on_file_failed)
        self._worker.finished_all.connect(self._on_extraction_finished)
        self._worker.start()

    def _on_progress(self, cur: int, total: int, fname: str):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(cur)
        self.lbl_status.setText(f"正在处理：{basename(fname)}")

    def _on_file_failed(self, path: str, err: str):
        # Compute elapsed time for the failed file
        start = self._file_start.get(path, time.time())
        elapsed = f"{time.time() - start:.1f}s"
        for f in self.files:
            if f["path"] == path:
                f["elapsed"] = elapsed
                f["status"] = STATUS_SKIPPED
        self._refresh_file_table()

        # Show inline danger banner
        self.lbl_banner.setText(
            f"✗ {basename(path)} 提取失败：{err}")
        self.lbl_banner.setObjectName("danger-banner")
        self.lbl_banner.setVisible(True)
        self.lbl_banner.style().unpolish(self.lbl_banner)
        self.lbl_banner.style().polish(self.lbl_banner)
        # Auto-hide after 5 seconds
        QTimer.singleShot(5000, lambda: self.lbl_banner.setVisible(False))

    def _cancel_processing(self):
        if self._worker:
            self._worker.cancel()
        self.lbl_status.setText("已取消")
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
        # Store elapsed times
        now = time.time()
        for res in results:
            path = res.get("source_file", "")
            start = self._file_start.get(path, now)
            elapsed = f"{now - start:.1f}s"
            for f in self.files:
                if f["path"] == path:
                    f["elapsed"] = elapsed
                    break
        if was_cancelled:
            self.lbl_status.setText("已取消")
            self._refresh_file_table()
            self._save_session()
            return
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.lbl_status.setText("提取完成")
        if not results:
            return
        cols = ConfigManager.get_column_names(self.config)
        if self._single_file_mode and len(results) == 1:
            self._handle_single_confirm(results[0], cols)
        else:
            self._handle_batch_confirm(results, cols)

    # ═══════════════ Duplicate Detection ═══════════════

    def _detect_duplicates(self, records: List[dict], cols: List[str]) -> List[int]:
        cmp = [c for c in cols if c != SOURCE_COL]
        dup = []
        for i, rec in enumerate(records):
            for ex in self.confirmed_records:
                if all(str(rec.get(c, "")) == str(ex.get(c, "")) for c in cmp):
                    dup.append(i)
                    break
        return dup

    def _handle_duplicates(self, records: List[dict], cols: List[str]) -> List[dict]:
        dup_idx = self._detect_duplicates(records, cols)
        if not dup_idx:
            return records
        filtered = list(records)
        cmp = [c for c in cols if c != SOURCE_COL]
        for i in sorted(dup_idx, reverse=True):
            rec = filtered[i]
            dlg = RepeatDialog(cols, [rec], self)
            if dlg.exec_() != RepeatDialog.Accepted:
                filtered.pop(i)
                continue
            choice = dlg.get_choice()
            if choice == "skip":
                filtered.pop(i)
            elif choice == "overwrite":
                for j, ex in enumerate(self.confirmed_records):
                    if all(str(rec.get(c, "")) == str(ex.get(c, "")) for c in cmp):
                        self.confirmed_records[j] = rec
                        break
                filtered.pop(i)
            # "add": keep
        return filtered

    # ═══════════════ Single Confirm ═══════════════

    def _handle_single_confirm(self, result: dict, cols: List[str]):
        if result.get("status") == "failed":
            for f in self.files:
                if f["path"] == result["source_file"]:
                    f["status"] = STATUS_SKIPPED
            self._refresh_file_table()
            self._update_ui_state()
            self._save_session()
            return

        records = result.get("records", []) or [{}]
        sn = basename(result["source_file"])
        for r in records:
            r[SOURCE_COL] = sn
        issues = result.get("field_issues", {})

        while True:
            dlg = SingleConfirmDialog(sn, cols, records, issues, self)
            dlg.exec_()
            if dlg.wants_reextract():
                records = PdfExtractor(self.config).extract_single(
                    result["source_file"]).get("records", []) or [{}]
                for r in records:
                    r[SOURCE_COL] = sn
                issues = PdfExtractor(self.config).extract_single(
                    result["source_file"]).get("field_issues", {})
                continue
            if dlg.is_confirmed():
                records = dlg.get_records()
                records = self._handle_duplicates(records, cols)
                self.confirmed_records.extend(records)
                for f in self.files:
                    if f["path"] == result["source_file"]:
                        f["status"] = STATUS_CONFIRMED
            else:
                for f in self.files:
                    if f["path"] == result["source_file"]:
                        f["status"] = STATUS_PENDING
            break

        self._refresh_file_table()
        self._refresh_content_table()
        self._update_ui_state()
        self._save_session()

    # ═══════════════ Batch Confirm ═══════════════

    def _on_reextract_finished(self, results, was_cancelled, cols):
        self._reset_worker()
        if was_cancelled:
            for f in self.files:
                if f["status"] == STATUS_PROCESSING:
                    f["status"] = STATUS_PENDING
            self._refresh_file_table()
            return
        self._handle_batch_confirm(results, cols)

    def _handle_batch_confirm(self, results: List[dict], cols: List[str]):
        dc = cols + [SOURCE_COL]
        records = []
        issues_map = {}
        ok = fail = 0

        for res in results:
            if res.get("status") == "failed":
                fail += 1
                for f in self.files:
                    if f["path"] == res.get("source_file"):
                        f["status"] = STATUS_SKIPPED
                continue
            ok += 1
            sn = basename(res["source_file"])
            subs = res.get("records", []) or [{}]
            for sub in subs:
                rec = {c: sub.get(c, "") for c in cols}
                rec[SOURCE_COL] = sn
                records.append(rec)
            if res.get("field_issues"):
                issues_map[len(records) - len(subs)] = res["field_issues"]

        stats = {"total": len(results), "success": ok, "failed": fail, "records": len(records)}

        while True:
            dlg = BatchConfirmDialog(dc, records, stats, issues_map, self)
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
                    lambda r, c: self._on_reextract_finished(r, c, cols))
                self._worker.start()
                return
            if dlg.is_confirmed():
                records = dlg.get_records()
                records = self._handle_duplicates(records, cols)
                self.confirmed_records.extend(records)
                for f in self.files:
                    if f["path"] in self._pending_paths:
                        f["status"] = STATUS_CONFIRMED
            else:
                for f in self.files:
                    if f["status"] == STATUS_PROCESSING:
                        f["status"] = STATUS_PENDING
            break

        self._refresh_file_table()
        self._refresh_content_table()
        self._update_ui_state()
        self._save_session()

    # ═══════════════ Config ═══════════════

    def _open_config_dialog(self):
        pending = [f["path"] for f in self.files if f["status"] == STATUS_PENDING]
        dlg = ConfigDialog(self.config, self.config_path, pending, self)
        if dlg.exec_():
            self.config = dlg.get_config()
            self.config_path = dlg.get_config_path() or self.config_path
            self._refresh_content_table()
            self._save_session()
            ConfigManager.add_recent_config(self.config_path)

    def _load_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "加载配置", "", "配置文件 (*.cfg)")
        if path:
            self.config = ConfigManager.load(path)
            self.config_path = path
            self._refresh_content_table()
            self._save_session()
            ConfigManager.add_recent_config(path)
            QMessageBox.information(self, "成功", "配置已加载")

    def _save_config(self):
        if ConfigManager.save(self.config, self.config_path):
            QMessageBox.information(self, "成功", "配置已保存")
        else:
            QMessageBox.critical(self, "错误", "保存配置失败")

    # ═══════════════ Excel Export ═══════════════

    def _export_excel(self):
        cols = self._content_columns()
        records = list(self.confirmed_records)
        if not records:
            QMessageBox.warning(self, "提示", "没有可导出的数据")
            return

        # Check unprocessed files
        unprocessed = [
            basename(f["path"]) for f in self.files
            if f["status"] not in (STATUS_CONFIRMED, STATUS_SKIPPED)
        ]
        if unprocessed:
            dlg = UnprocessedDialog(unprocessed, self)
            if dlg.exec_() != UnprocessedDialog.Accepted:
                return
            if dlg.get_choice() == "cancel":
                return
            if dlg.get_choice() == "process":
                return

        # Format selection
        opt = ExcelOptionDialog(self)
        if opt.exec_() != ExcelOptionDialog.Accepted:
            return

        default_name = ExcelGenerator.default_filename()
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 Excel 文件", default_name, "Excel 文件 (*.xlsx)")
        if not path:
            return
        if not path.endswith(".xlsx"):
            path += ".xlsx"

        gen = ExcelGenerator(cols)
        if opt.use_template() and opt.get_template_path():
            ok = gen.generate_from_template(records, opt.get_template_path(), path)
        else:
            ok = gen.generate(records, path)

        if ok:
            mb = QMessageBox(self)
            mb.setWindowTitle("导出成功")
            mb.setText(f"Excel 文件已生成：\n{os.path.basename(path)}")
            b_open = mb.addButton("打开文件", QMessageBox.ActionRole)
            b_dir = mb.addButton("打开文件夹", QMessageBox.ActionRole)
            b_close = mb.addButton("关闭", QMessageBox.RejectRole)
            mb.exec_()
            if mb.clickedButton() == b_open:
                os.startfile(path)
            elif mb.clickedButton() == b_dir:
                os.startfile(os.path.dirname(path))
            # Always clear after export
            self.files.clear()
            self.confirmed_records.clear()
            self._refresh_file_table()
            self._refresh_content_table()
            self._update_ui_state()
            self._save_session()
            logger.info("Excel 导出成功: %s", path)
        else:
            QMessageBox.critical(self, "错误", "生成 Excel 失败，请检查磁盘空间或文件是否被占用")

    # ═══════════════ Content Editing ═══════════════

    def _add_content_row(self):
        cols = self._content_columns()
        self.confirmed_records.append({c: "" for c in cols})
        self._refresh_content_table()
        self._save_session()

    def _delete_content_rows(self):
        rows = sorted({i.row() for i in self.content_table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for r in rows:
            if r < len(self.confirmed_records):
                self.confirmed_records.pop(r)
        self._refresh_content_table()
        self._save_session()

    def _clear_all_records(self):
        if not self.confirmed_records:
            return
        n = len(self.confirmed_records)
        if QMessageBox.question(self, "确认清空",
                                f"确定清空全部已确认内容？（共 {n} 条记录）") == QMessageBox.Yes:
            self.confirmed_records.clear()
            self._refresh_content_table()
            self._update_ui_state()
            self._save_session()

    def _on_content_changed(self):
        self.confirmed_records = table_to_records(self.content_table, self._content_columns())
        self.lbl_record_stats.setText(f"共 {len(self.confirmed_records)} 条记录")
        self._save_session()

    # ═══════════════ Session ═══════════════

    def _save_session(self):
        data = SessionManager.build_session_data(
            self.config, self.config_path, self.files, self.confirmed_records)
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
            for f in self.files:
                if "checked" not in f:
                    f["checked"] = True
            self.confirmed_records = data.get("confirmed_records", [])
            missing = [basename(f["path"]) for f in self.files if not f.get("exists", True)]
            if missing:
                QMessageBox.warning(self, "提示",
                                    f"以下文件已不存在，请重新选择：{', '.join(missing)}")
            self._refresh_file_table()
            self._refresh_content_table()
            logger.info("会话已恢复")
        except Exception as e:
            logger.exception("恢复会话失败: %s", e)

    def closeEvent(self, event):
        data = SessionManager.build_session_data(
            self.config, self.config_path, self.files, self.confirmed_records)
        self.session_manager.save_now(data)
        if self._worker:
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)
