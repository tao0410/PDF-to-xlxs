# -*- coding: utf-8 -*-
"""PDF 提取后台线程。"""

import logging
from typing import List

from PyQt5.QtCore import QThread, pyqtSignal

from pdf_extractor import PdfExtractor

logger = logging.getLogger(__name__)


class ExtractionWorker(QThread):
    """在后台线程中执行 PDF 提取。"""

    progress = pyqtSignal(int, int, str)  # current, total, filename
    file_failed = pyqtSignal(str, str)  # path, error_msg
    finished_all = pyqtSignal(list, bool)  # results, was_cancelled

    def __init__(self, config: dict, pdf_paths: List[str], parent=None):
        super().__init__(parent)
        self.config = config
        self.pdf_paths = pdf_paths
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        extractor = PdfExtractor(self.config)
        results = []
        total = len(self.pdf_paths)
        for idx, path in enumerate(self.pdf_paths):
            if self._cancelled:
                logger.info("提取已取消")
                break
            self.progress.emit(idx + 1, total, path)
            result = extractor.extract_single(path)
            if result.get("status") == "failed":
                self.file_failed.emit(path, result.get("error_msg", "未知错误"))
            results.append(result)
        self.finished_all.emit(results, self._cancelled)
