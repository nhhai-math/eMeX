"""Splash screen khởi động đơn giản cho eMeX."""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget

from .config import APP_NAME, APP_VERSION
from .i18n import t


FEATURE_HIGHLIGHTS: tuple[tuple[str, str], ...] = (
    ("Markdown", "#60a5fa"),
    ("MathJax/TikZ", "#2dd4bf"),
    ("Gemini AI", "#a78bfa"),
)

AUTHOR_NAME = "Nguyễn Hoàng Hải"
SUPPORT_EMAIL = "nghai.math@gmail.com"
FACEBOOK_TEXT = "facebook.com/nhhai.math"
COPYRIGHT = f"© 2026 {APP_NAME} · {AUTHOR_NAME}"


class SplashScreen(QWidget):
    """Splash frameless, vẽ trực tiếp bằng Qt để không cần asset mới."""

    CARD_W = 540
    CARD_H = 330
    SHADOW_PAD = 26
    LOGO_SIZE = 76

    def __init__(self, app_icon: QIcon | None = None) -> None:
        super().__init__(
            None,
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self._app_icon = app_icon if app_icon is not None else QIcon()
        if not self._app_icon.isNull():
            self.setWindowIcon(self._app_icon)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(
            self.CARD_W + self.SHADOW_PAD * 2,
            self.CARD_H + self.SHADOW_PAD * 2,
        )

        self._status_text = t("Đang khởi động...")
        self._tick = 0

        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

        self._center_on_screen()

    def show_message(self, text: str) -> None:
        self._status_text = text or ""
        self.update()
        QApplication.processEvents()

    def finish(self, window: QWidget | None = None) -> None:
        self._timer.stop()
        self.close()
        if window is not None:
            window.raise_()
            window.activateWindow()

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.x() + (geo.width() - self.width()) // 2,
            geo.y() + (geo.height() - self.height()) // 2,
        )

    def _on_tick(self) -> None:
        self._tick = (self._tick + 1) % 1_000_000
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt API)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        card = QRectF(self.SHADOW_PAD, self.SHADOW_PAD, self.CARD_W, self.CARD_H)
        self._paint_shadow(p, card)
        self._paint_card(p, card)

        y = card.top() + 26
        y = self._paint_logo(p, card, y) + 12
        y = self._paint_title(p, card, y) + 4
        y = self._paint_version(p, card, y) + 20
        y = self._paint_divider(p, card, y) + 16
        y = self._paint_features(p, card, y) + 16
        y = self._paint_divider(p, card, y) + 14
        self._paint_contact(p, card, y)
        self._paint_progress(p, card)

        p.end()
        del event

    def _paint_shadow(self, p: QPainter, card: QRectF) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(1, 14):
            alpha = max(5, 38 - i * 2)
            offset = i * 1.2
            rect = card.adjusted(-offset, -offset + 3.0, offset, offset + 7.0)
            p.setBrush(QColor(15, 23, 42, alpha))
            p.drawRoundedRect(rect, 18, 18)

    def _paint_card(self, p: QPainter, card: QRectF) -> None:
        grad = QLinearGradient(card.topLeft(), card.bottomRight())
        grad.setColorAt(0.0, QColor("#0f172a"))
        grad.setColorAt(0.56, QColor("#12324a"))
        grad.setColorAt(1.0, QColor("#1d4d70"))
        p.setBrush(grad)
        p.setPen(QPen(QColor("#2d5a72"), 1))
        p.drawRoundedRect(card, 16, 16)

    def _paint_logo(self, p: QPainter, card: QRectF, y: float) -> float:
        size = self.LOGO_SIZE
        rect = QRectF(card.center().x() - size / 2, y, size, size)

        if not self._app_icon.isNull():
            pixmap = self._app_icon.pixmap(size, size)
            x = int(rect.center().x() - pixmap.width() / 2)
            y_icon = int(rect.center().y() - pixmap.height() / 2)
            p.drawPixmap(x, y_icon, pixmap)
        else:
            f = QFont("Segoe UI", 26, QFont.Weight.Bold)
            p.setFont(f)
            p.setPen(QColor("#1d4ed8"))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "M")

        return rect.bottom()

    def _paint_title(self, p: QPainter, card: QRectF, y: float) -> float:
        f = QFont("Segoe UI", 24, QFont.Weight.Bold)
        p.setFont(f)
        p.setPen(QColor("#ffffff"))
        rect = QRectF(card.left(), y, card.width(), 36)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, APP_NAME)
        return rect.bottom()

    def _paint_version(self, p: QPainter, card: QRectF, y: float) -> float:
        p.setFont(QFont("Segoe UI", 9))
        p.setPen(QColor("#b7d7e8"))
        rect = QRectF(card.left(), y, card.width(), 16)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, t("v{version} · Trình soạn thảo Markdown", version=APP_VERSION))
        return rect.bottom()

    def _paint_divider(self, p: QPainter, card: QRectF, y: float) -> float:
        margin_x = 58.0
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.drawLine(
            QPointF(card.left() + margin_x, y),
            QPointF(card.right() - margin_x, y),
        )
        return y

    def _paint_features(self, p: QPainter, card: QRectF, y: float) -> float:
        p.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        fm = p.fontMetrics()
        gap = 24.0
        dot_r = 4.0
        dot_gap = 8.0
        widths = [fm.horizontalAdvance(label) for label, _color in FEATURE_HIGHLIGHTS]
        total_w = sum(widths) + (dot_r * 2 + dot_gap) * len(widths) + gap * (len(widths) - 1)
        x = card.center().x() - total_w / 2
        row_h = 22.0
        center_y = y + row_h / 2

        for (label, color_hex), width in zip(FEATURE_HIGHLIGHTS, widths):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color_hex))
            p.drawEllipse(QPointF(x + dot_r, center_y), dot_r, dot_r)

            p.setPen(QColor("#e6f3fb"))
            text_x = x + dot_r * 2 + dot_gap
            p.drawText(
                QRectF(text_x, y, width + 1, row_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                label,
            )
            x += dot_r * 2 + dot_gap + width + gap

        return y + row_h

    def _paint_contact(self, p: QPainter, card: QRectF, y: float) -> None:
        p.setFont(QFont("Segoe UI", 9))
        p.setPen(QColor("#e6f3fb"))
        p.drawText(
            QRectF(card.left(), y, card.width(), 16),
            Qt.AlignmentFlag.AlignCenter,
            f"{SUPPORT_EMAIL}  ·  {FACEBOOK_TEXT}",
        )

        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor("#91b6cc"))
        p.drawText(
            QRectF(card.left(), y + 18, card.width(), 14),
            Qt.AlignmentFlag.AlignCenter,
            COPYRIGHT,
        )

    def _paint_progress(self, p: QPainter, card: QRectF) -> None:
        p.setFont(QFont("Segoe UI", 9))
        p.setPen(QColor("#b7d7e8"))
        p.drawText(
            QRectF(card.left(), card.bottom() - 38, card.width(), 16),
            Qt.AlignmentFlag.AlignCenter,
            self._status_text,
        )

        bar_h = 3.0
        margin_x = 58.0
        bar = QRectF(
            card.left() + margin_x,
            card.bottom() - 18,
            card.width() - margin_x * 2,
            bar_h,
        )
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 42))
        p.drawRoundedRect(bar, bar_h / 2, bar_h / 2)

        sweep_w = bar.width() * 0.28
        period = bar.width() + sweep_w
        phase = (self._tick * 6.0) % period
        x_start = bar.left() + phase - sweep_w
        x_end = x_start + sweep_w
        clip_left = max(bar.left(), x_start)
        clip_right = min(bar.right(), x_end)
        if clip_right <= clip_left:
            return

        sweep = QRectF(clip_left, bar.top(), clip_right - clip_left, bar_h)
        grad = QLinearGradient(sweep.left(), 0, sweep.right(), 0)
        grad.setColorAt(0.0, QColor("#2563eb"))
        grad.setColorAt(0.5, QColor("#2dd4bf"))
        grad.setColorAt(1.0, QColor("#38bdf8"))
        p.setBrush(grad)
        p.drawRoundedRect(sweep, bar_h / 2, bar_h / 2)
