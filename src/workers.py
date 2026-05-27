"""Worker layer dùng chung cho eMeX – chạy tác vụ nặng nền (export, I/O, network)
mà không khoá GUI thread, kèm Toast notification không-modal.

Mục tiêu:
- Mọi tác vụ nặng (markdown→DOCX/LaTeX/HTML, đọc/ghi file, encode ảnh, http)
  đều có thể được dispatch bằng ``run_async(parent, fn, ...)``.
- Không lặp lại boilerplate `QThread + moveToThread + signal` ở nhiều chỗ.
- Toast: thông báo hoàn tất / lỗi mà không chặn workflow như QMessageBox.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from PyQt6.QtCore import (QEasingCurve, QObject, QPoint, QPropertyAnimation,
                          Qt, QThread, QTimer, pyqtSignal)
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import (QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                              QPushButton, QVBoxLayout, QWidget)


# =============================================================================
# Generic background worker
# =============================================================================

class _Worker(QObject):
    """Wrapper cho 1 callable bất kỳ, chạy trong QThread, emit kết quả/lỗi."""

    completed = pyqtSignal(object)  # result trả về từ fn
    failed = pyqtSignal(str)         # message lỗi
    finished = pyqtSignal()           # luôn emit sau khi xong (dù lỗi hay không)

    def __init__(self, fn: Callable[..., Any], args: tuple, kwargs: dict):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.completed.emit(result)
        except Exception as exc:  # noqa: BLE001 – muốn báo mọi lỗi lên UI
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


def run_async(
    parent: QObject,
    fn: Callable[..., Any],
    *args: Any,
    on_done: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
    on_finished: Optional[Callable[[], None]] = None,
    **kwargs: Any,
) -> QThread:
    """Chạy ``fn(*args, **kwargs)`` trong QThread mới.

    Các callback ``on_done(result)`` / ``on_error(message)`` / ``on_finished()``
    được phát qua Qt signal nên luôn chạy trên main thread (parent's thread).

    Tham số ``parent`` chỉ dùng để neo lifecycle: thread/worker được tự dọn
    sau khi finished, kể cả khi parent vẫn sống.
    """
    thread = QThread(parent)
    worker = _Worker(fn, args, kwargs)
    worker.moveToThread(thread)

    if on_done is not None:
        worker.completed.connect(on_done)
    if on_error is not None:
        worker.failed.connect(on_error)
    if on_finished is not None:
        worker.finished.connect(on_finished)

    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)

    # Giữ tham chiếu khỏi bị GC trước khi finished.
    _ACTIVE_TASKS.add((thread, worker))
    thread.finished.connect(lambda: _ACTIVE_TASKS.discard((thread, worker)))

    thread.start()
    return thread


_ACTIVE_TASKS: "set[tuple[QThread, _Worker]]" = set()


# =============================================================================
# Toast notification – không-modal, tự dismiss
# =============================================================================

class Toast(QWidget):
    """Notification card nổi ở góc dưới-phải của parent.

    Dùng cho thông báo info / success / warning / error mà không cần user click.
    Stack nhiều toast theo thứ tự xuất hiện.
    """

    _stacks: "dict[int, list[Toast]]" = {}

    KIND_PALETTE = {
        "info":    ("#0f172a", "#ffffff", "#2563eb", "ℹ"),
        "success": ("#0f172a", "#ffffff", "#16a34a", "✓"),
        "warning": ("#0f172a", "#fffbeb", "#f59e0b", "⚠"),
        "error":   ("#7f1d1d", "#fef2f2", "#ef4444", "✕"),
    }

    def __init__(
        self,
        parent: QWidget,
        message: str,
        kind: str = "info",
        duration_ms: int = 3500,
        action_label: str = "",
        on_action: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        text_color, bg, accent, icon_char = self.KIND_PALETTE.get(
            kind, self.KIND_PALETTE["info"])
        self._kind = kind
        self._duration_ms = duration_ms

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet(
            f"Toast{{background:{bg};border:1px solid {accent};border-radius:10px;}}"
            f"QLabel{{background:transparent;color:{text_color};font-size:13px;}}"
            "QPushButton{background:transparent;border:0;color:#475569;font-weight:700;"
            "padding:2px 6px;border-radius:6px;}"
            "QPushButton:hover{background:rgba(15,23,42,0.06);color:#0f172a;}"
            f"QLabel#toastIcon{{color:{accent};font-weight:800;font-size:15px;}}"
            f"QPushButton#toastAction{{color:{accent};font-weight:700;}}"
            f"QPushButton#toastAction:hover{{background:rgba(37,99,235,0.08);}}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 8, 10)
        layout.setSpacing(10)

        icon = QLabel(icon_char)
        icon.setObjectName("toastIcon")
        layout.addWidget(icon)

        text = QLabel(message)
        text.setWordWrap(True)
        text.setMinimumWidth(180)
        text.setMaximumWidth(360)
        layout.addWidget(text, 1)

        if action_label and on_action is not None:
            btn = QPushButton(action_label)
            btn.setObjectName("toastAction")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda: (on_action(), self.dismiss()))
            layout.addWidget(btn)

        close_btn = QPushButton("×")
        close_btn.setFixedWidth(24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.dismiss)
        layout.addWidget(close_btn)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(15, 23, 42, 70))
        self.setGraphicsEffect(shadow)

        self.adjustSize()
        self.setFixedHeight(self.sizeHint().height())

        # Animation fade-in/out qua windowOpacity. Cần là top-level widget
        # mới đổi opacity được, nhưng vì là child widget nên dùng animation
        # vào geometry slide-in thay cho fade.
        self._slide = QPropertyAnimation(self, b"pos", self)
        self._slide.setDuration(220)
        self._slide.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.timeout.connect(self.dismiss)

    def enterEvent(self, event):  # noqa: N802 (Qt API)
        self._auto_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 (Qt API)
        if self._duration_ms > 0:
            self._auto_timer.start(max(1500, self._duration_ms // 2))
        super().leaveEvent(event)

    def show_at_corner(self) -> None:
        """Hiển thị ở góc dưới-phải của parent, stack với các toast khác."""
        parent = self.parentWidget()
        if parent is None:
            self.show()
            return

        pid = id(parent)
        stack = Toast._stacks.setdefault(pid, [])
        stack.append(self)
        self.destroyed.connect(lambda: self._on_destroyed(pid))

        self._reposition_stack(parent)
        self.show()
        self.raise_()
        if self._duration_ms > 0:
            self._auto_timer.start(self._duration_ms)

    @staticmethod
    def _on_destroyed(pid: int) -> None:
        stack = Toast._stacks.get(pid)
        if not stack:
            return
        # Cleanup: drop deleted widgets từ stack
        Toast._stacks[pid] = [t for t in stack if not _is_deleted(t)]

    def _reposition_stack(self, parent: QWidget) -> None:
        stack = Toast._stacks.get(id(parent), [])
        margin = 18
        gap = 8
        parent_rect = parent.rect()
        y = parent_rect.bottom() - margin
        for toast in reversed(stack):
            if _is_deleted(toast):
                continue
            w = toast.width()
            h = toast.height()
            target = QPoint(parent_rect.right() - margin - w, y - h)
            if toast is self and not toast.isVisible():
                # Slide-in từ ngoài phải vào
                toast.move(parent_rect.right() + 8, target.y())
                toast._slide.stop()
                toast._slide.setStartValue(toast.pos())
                toast._slide.setEndValue(target)
                toast._slide.start()
            else:
                toast.move(target)
            y -= h + gap

    def dismiss(self) -> None:
        self._auto_timer.stop()
        parent = self.parentWidget()
        if parent is not None:
            stack = Toast._stacks.get(id(parent), [])
            try:
                stack.remove(self)
            except ValueError:
                pass
            self._reposition_stack(parent)
        self.deleteLater()

    @staticmethod
    def show_toast(
        parent: QWidget,
        message: str,
        kind: str = "info",
        duration_ms: int = 3500,
        action_label: str = "",
        on_action: Optional[Callable[[], None]] = None,
    ) -> "Toast":
        toast = Toast(parent, message, kind=kind, duration_ms=duration_ms,
                       action_label=action_label, on_action=on_action)
        toast.show_at_corner()
        return toast


def _is_deleted(obj) -> bool:
    try:
        obj.parentWidget()
        return False
    except RuntimeError:
        return True
