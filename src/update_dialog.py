"""Hộp thoại cập nhật eMeX."""
from __future__ import annotations

import re
from html import unescape

from PyQt6.QtCore import Qt, QThread, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from .updater import ReleaseInfo, UpdateDownloader, current_version, set_skipped_version
from .i18n import t


RESULT_UPDATE = 1
RESULT_LATER = 0
RESULT_SKIP = 2


def _format_release_notes(release: ReleaseInfo) -> str:
    lines: list[str] = []
    for raw_line in (release.body or "").replace("\r\n", "\n").splitlines():
        line = unescape(raw_line).strip()
        if not line:
            continue
        if re.search(r"full\s+changelog", line, re.IGNORECASE):
            continue
        if re.fullmatch(r"https?://\S+", line):
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        line = re.sub(r"^#{1,6}\s*", "", line).strip()
        line = re.sub(r"^\s*[-*]\s+", "- ", line).strip()
        line = line.replace("**", "").replace("__", "").replace("`", "")
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        if line and line not in {"What's Changed", "New Contributors"}:
            lines.append(line)

    if lines:
        return "\n".join(lines[:8])
    return t("- Bản cập nhật v{version} đã sẵn sàng để cài đặt.", version=release.version)


class UpdateDialog(QDialog):
    def __init__(self, release: ReleaseInfo, parent=None) -> None:
        super().__init__(parent)
        self._release = release
        self._downloader: UpdateDownloader | None = None
        self._thread: QThread | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle(t("Cập nhật eMeX"))
        self.setMinimumWidth(500)
        self.setMaximumWidth(580)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet("QDialog{background:#ffffff;color:#0f172a;}")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(76)
        header.setStyleSheet(
            "QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #2563eb, stop:1 #0f766e);}"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(22, 0, 22, 0)
        lbl_icon = QLabel("!")
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_icon.setFixedSize(36, 36)
        lbl_icon.setStyleSheet(
            "QLabel{background:#fef3c7;color:#b45309;border-radius:18px;"
            "font-size:24px;font-weight:900;}"
        )
        h_layout.addWidget(lbl_icon)

        h_text = QVBoxLayout()
        h_text.setSpacing(2)
        lbl_title = QLabel(t("Có phiên bản mới"))
        lbl_title.setStyleSheet("font-size:16px;font-weight:800;color:#ffffff;background:transparent;")
        h_text.addWidget(lbl_title)
        lbl_sub = QLabel(t("eMeX v{version} đã sẵn sàng để cài đặt", version=self._release.version))
        lbl_sub.setStyleSheet("font-size:12px;color:#dbeafe;background:transparent;")
        h_text.addWidget(lbl_sub)
        h_layout.addLayout(h_text)
        h_layout.addStretch()
        root.addWidget(header)

        body = QVBoxLayout()
        body.setContentsMargins(22, 18, 22, 20)
        body.setSpacing(14)

        ver_row = QHBoxLayout()
        ver_row.setSpacing(10)
        ver_row.addWidget(self._badge(f"v{current_version()}", "#64748b", "#f1f5f9"))
        arrow = QLabel("→")
        arrow.setStyleSheet("color:#94a3b8;font-size:15px;")
        ver_row.addWidget(arrow)
        ver_row.addWidget(self._badge(f"v{self._release.version}", "#ffffff", "#2563eb"))
        ver_row.addStretch()
        body.addLayout(ver_row)

        notes = _format_release_notes(self._release)
        if notes:
            lbl_notes = QLabel(t("Nội dung cập nhật:"))
            lbl_notes.setStyleSheet("font-size:12px;font-weight:700;color:#374151;")
            body.addWidget(lbl_notes)
            txt = QTextEdit()
            txt.setReadOnly(True)
            txt.setPlainText(notes)
            txt.setFixedHeight(118)
            txt.setStyleSheet(
                "QTextEdit{background:#f8fafc;border:1px solid #e2e8f0;"
                "border-radius:7px;color:#334155;font-size:12px;padding:6px;}"
            )
            body.addWidget(txt)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFixedHeight(18)
        self._progress.setStyleSheet(
            "QProgressBar{border:1px solid #e2e8f0;border-radius:5px;background:#f1f5f9;"
            "color:#334155;font-size:11px;text-align:center;}"
            "QProgressBar::chunk{background:#2563eb;border-radius:4px;}"
        )
        self._progress.hide()
        body.addWidget(self._progress)

        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet("color:#64748b;font-size:11px;")
        self._lbl_status.setWordWrap(True)
        self._lbl_status.hide()
        body.addWidget(self._lbl_status)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#e2e8f0;")
        body.addWidget(sep)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._btn_no_remind = QPushButton(t("Không nhắc lại"))
        self._btn_no_remind.setFixedHeight(34)
        self._btn_no_remind.setStyleSheet(
            "QPushButton{border:none;background:transparent;color:#94a3b8;"
            "font-size:12px;padding:0 8px;text-decoration:underline;}"
            "QPushButton:hover{color:#64748b;}"
        )
        self._btn_no_remind.clicked.connect(self._on_no_remind)
        btn_row.addWidget(self._btn_no_remind)
        btn_row.addStretch()

        self._btn_later = QPushButton(t("Nhắc lại sau"))
        self._btn_later.setFixedHeight(34)
        self._btn_later.setMinimumWidth(104)
        self._btn_later.setStyleSheet(
            "QPushButton{border:1px solid #e2e8f0;border-radius:7px;padding:0 16px;"
            "color:#374151;background:#ffffff;font-size:13px;}"
            "QPushButton:hover{background:#f1f5f9;border-color:#cbd5e1;}"
        )
        self._btn_later.clicked.connect(lambda: self.done(RESULT_LATER))
        btn_row.addWidget(self._btn_later)

        self._btn_update = QPushButton(t("Cập nhật ngay"))
        self._btn_update.setFixedHeight(34)
        self._btn_update.setMinimumWidth(126)
        self._btn_update.setStyleSheet(
            "QPushButton{background:#2563eb;border-radius:7px;padding:0 18px;color:#ffffff;"
            "font-weight:700;font-size:13px;border:none;}"
            "QPushButton:hover{background:#1d4ed8;}"
            "QPushButton:disabled{background:#93c5fd;}"
        )
        self._btn_update.clicked.connect(self._start_update)
        btn_row.addWidget(self._btn_update)

        body.addLayout(btn_row)
        root.addLayout(body)

    @staticmethod
    def _badge(text: str, color: str, bg: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color:{color};background:{bg};border-radius:6px;"
            "font-size:13px;font-weight:800;padding:4px 12px;"
        )
        return lbl

    def _on_no_remind(self) -> None:
        set_skipped_version(self._release.version)
        self.done(RESULT_SKIP)

    def _start_update(self) -> None:
        self._btn_update.setEnabled(False)
        self._btn_later.setEnabled(False)
        self._btn_no_remind.setEnabled(False)
        self._btn_update.setText(t("Đang cập nhật..."))
        self._progress.show()
        self._lbl_status.show()
        self._lbl_status.setText(t("Đang kết nối..."))

        self._thread = QThread()
        self._downloader = UpdateDownloader(self._release)
        self._downloader.moveToThread(self._thread)
        self._thread.started.connect(self._downloader.run)
        self._downloader.progress.connect(self._on_progress)
        self._downloader.finished.connect(self._on_finished)
        self._downloader.finished.connect(self._thread.quit)
        self._downloader.finished.connect(lambda *_: setattr(self, "_downloader", None))
        self._thread.finished.connect(lambda: setattr(self, "_thread", None))
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_progress(self, done: int, total: int) -> None:
        if total > 0:
            self._progress.setValue(int(done * 100 / total))
            self._lbl_status.setText(t("Đang tải: {done:.1f} / {total:.1f} MB", done=done/1_048_576, total=total/1_048_576))
        else:
            self._lbl_status.setText(t("Đang tải: {done:.1f} MB...", done=done/1_048_576))

    def _on_finished(self, success: bool, error: str) -> None:
        if success:
            self._progress.setValue(100)
            self._lbl_status.setStyleSheet("color:#16a34a;font-size:11px;")
            self._lbl_status.setText(t("Hoàn tất. Ứng dụng sẽ khởi động lại sau vài giây..."))
            self.done(RESULT_UPDATE)
            QTimer.singleShot(300, self._quit_application)
            return

        self._lbl_status.setStyleSheet("color:#ef4444;font-size:11px;")
        self._lbl_status.setText(error or t("Không thể cập nhật."))
        self._btn_update.setEnabled(True)
        self._btn_later.setEnabled(True)
        self._btn_no_remind.setEnabled(True)
        self._btn_update.setText(t("Thử lại"))

    @staticmethod
    def _quit_application() -> None:
        app = QApplication.instance()
        if app is not None:
            app.closeAllWindows()
            app.quit()

    def closeEvent(self, event) -> None:
        if self._downloader is not None:
            self._downloader.cancel()
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        super().closeEvent(event)
