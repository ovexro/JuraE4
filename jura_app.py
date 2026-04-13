"""
JURA Desktop Control — Premium coffee machine dashboard
"""

import json
import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QSlider, QFrame, QStackedWidget,
    QGraphicsDropShadowEffect, QDialog, QSpacerItem, QSizePolicy,
    QScrollArea, QLineEdit, QSystemTrayIcon, QMenu, QAction,
)
from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal, QSize
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QPen, QPainterPath, QLinearGradient,
    QRadialGradient, QFontDatabase, QPalette, QIcon,
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
from jura_protocol import E4_PRODUCTS, Product
from jura_wifi_v2 import WiFiV2Manager, MachineStatistics, DEFAULT_DONGLE_IP, DONGLE_PORT

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

BG           = "#0b0b13"
BG_ELEVATED  = "#111120"
BG_CARD      = "#161628"
BG_CARD_HVR  = "#1c1c34"
BORDER       = "#252540"
GOLD         = "#c8a662"
GOLD_LIGHT   = "#dcc088"
GOLD_DARK    = "#957840"
GOLD_DIMMED  = "#6e5c30"
TEXT         = "#ede4d4"
TEXT_DIM     = "#6e6e82"
TEXT_DARK    = "#0b0b13"
GREEN        = "#5ec96a"
AMBER        = "#e8a830"
RED          = "#d84040"

# Brewing animation colors
COFFEE_DARK  = "#2c1810"
COFFEE_MID   = "#4a2c1a"
COFFEE_LIGHT = "#6b3a20"
CREMA        = "#c4956a"
CREMA_LIGHT  = "#d4a878"
CUP_WHITE    = "#e8e0d4"
CUP_SHADOW   = "#b8b0a4"
CUP_RIM      = "#f5f0e8"

FONT_FAMILY = '"Noto Sans", "Cantarell", "Ubuntu", "Segoe UI", sans-serif'

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: {FONT_FAMILY};
    font-size: 13px;
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: {BG};
    width: 6px;
    margin: 0;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    min-height: 40px;
    border-radius: 3px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


def make_font(size=13, weight=QFont.Normal, spacing=0):
    f = QFont()
    f.setPointSize(size)
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


def card_shadow():
    s = QGraphicsDropShadowEffect()
    s.setBlurRadius(32)
    s.setOffset(0, 4)
    s.setColor(QColor(0, 0, 0, 90))
    return s


# ---------------------------------------------------------------------------
# Custom Widgets
# ---------------------------------------------------------------------------

class CoffeeCupIcon(QWidget):
    """Hand-painted minimalist coffee cup."""

    def __init__(self, style="coffee", size=90, parent=None):
        super().__init__(parent)
        self._style = style
        self.setFixedSize(size, size)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        gold = QColor(GOLD)
        gold_faint = QColor(GOLD)
        gold_faint.setAlpha(50)

        # Cup dimensions per style
        ratios = {
            "ristretto": (0.44, 0.38),
            "espresso":  (0.50, 0.42),
            "coffee":    (0.58, 0.52),
        }
        ch_ratio, cw_ratio = ratios.get(self._style, (0.55, 0.48))
        cup_h = h * ch_ratio
        cup_w = w * cw_ratio
        cup_top = cy + h * 0.04
        cup_bot = cup_top + cup_h
        taper = cup_w * 0.07

        pen = QPen(gold, 2.2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)

        # Cup body
        body = QPainterPath()
        body.moveTo(cx - cup_w / 2, cup_top)
        body.lineTo(cx - cup_w / 2 + taper, cup_bot)
        body.quadTo(cx, cup_bot + cup_h * 0.09, cx + cup_w / 2 - taper, cup_bot)
        body.lineTo(cx + cup_w / 2, cup_top)
        p.drawPath(body)

        # Fill (coffee level)
        fill_top = cup_top + cup_h * 0.22
        fill = QPainterPath()
        inset = taper * (fill_top - cup_top) / cup_h
        left_at_fill = cx - cup_w / 2 + inset
        right_at_fill = cx + cup_w / 2 - inset
        fill.moveTo(left_at_fill, fill_top)
        fill.lineTo(cx - cup_w / 2 + taper, cup_bot)
        fill.quadTo(cx, cup_bot + cup_h * 0.09, cx + cup_w / 2 - taper, cup_bot)
        fill.lineTo(right_at_fill, fill_top)
        fill.closeSubpath()
        fill_grad = QLinearGradient(cx, fill_top, cx, cup_bot)
        fill_grad.setColorAt(0, QColor(200, 166, 98, 35))
        fill_grad.setColorAt(1, QColor(200, 166, 98, 60))
        p.setPen(Qt.NoPen)
        p.setBrush(fill_grad)
        p.drawPath(fill)

        # Handle
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        ht = cup_top + cup_h * 0.15
        hb = cup_top + cup_h * 0.70
        hr = cx + cup_w / 2 + cup_w * 0.28
        handle = QPainterPath()
        handle.moveTo(cx + cup_w / 2, ht)
        handle.cubicTo(hr, ht, hr, hb, cx + cup_w / 2, hb)
        p.drawPath(handle)

        # Saucer
        sy = cup_bot + cup_h * 0.09
        sw = cup_w * 0.95
        p.setPen(QPen(gold, 2.0, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(cx - sw / 2, sy), QPointF(cx + sw / 2, sy))

        # Steam
        steam_pen = QPen(QColor(GOLD_LIGHT), 1.4, Qt.SolidLine, Qt.RoundCap)
        for i, xoff in enumerate([-0.14, 0.02, 0.16]):
            alpha = 65 - i * 12
            sc = QColor(GOLD_LIGHT)
            sc.setAlpha(alpha)
            steam_pen.setColor(sc)
            p.setPen(steam_pen)
            sx = cx + cup_w * xoff
            sy_base = cup_top - 4
            steam = QPainterPath()
            steam.moveTo(sx, sy_base)
            a = 3.5 + i * 0.5
            steam.cubicTo(sx - a, sy_base - 11, sx + a, sy_base - 22, sx - 1, sy_base - 32)
            p.drawPath(steam)
        p.end()


class StrengthSelector(QWidget):
    """Row of clickable dots for coffee strength."""
    changed = pyqtSignal(int)

    def __init__(self, value=4, max_val=8, parent=None):
        super().__init__(parent)
        self._value = value
        self._max = max_val
        self._dot_r = 7
        self._gap = 7
        self.setFixedSize(self._max * (self._dot_r * 2 + self._gap), self._dot_r * 2 + 8)
        self.setCursor(Qt.PointingHandCursor)

    @property
    def value(self):
        return self._value

    def set_value(self, v):
        self._value = max(1, min(v, self._max))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self._dot_r
        step = r * 2 + self._gap
        y = self.height() / 2
        for i in range(self._max):
            x = r + i * step
            if i < self._value:
                grad = QRadialGradient(x, y, r)
                grad.setColorAt(0, QColor(GOLD_LIGHT))
                grad.setColorAt(1, QColor(GOLD))
                p.setBrush(grad)
                p.setPen(Qt.NoPen)
            else:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(BORDER), 1.8))
            p.drawEllipse(QPointF(x, y), r, r)
        p.end()

    def mousePressEvent(self, event):
        step = self._dot_r * 2 + self._gap
        idx = int(event.pos().x() / step) + 1
        self.set_value(idx)
        self.changed.emit(self._value)


class TempToggle(QWidget):
    """Low / Normal / High temperature toggle."""
    changed = pyqtSignal(int)

    def __init__(self, value=1, parent=None):
        super().__init__(parent)
        self._value = value
        self._buttons = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        for label, val in [("Low", 0), ("Normal", 1), ("High", 2)]:
            btn = QPushButton(label)
            btn.setFixedHeight(30)
            btn.setFixedWidth(58)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, v=val: self._set(v))
            layout.addWidget(btn)
            self._buttons.append((btn, val))
        self._apply_style()

    @property
    def value(self):
        return self._value

    def _set(self, v):
        self._value = v
        self._apply_style()
        self.changed.emit(v)

    def _apply_style(self):
        active = f"""
            QPushButton {{
                background-color: {GOLD};
                color: {TEXT_DARK};
                border: none;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 700;
            }}
        """
        inactive = f"""
            QPushButton {{
                background-color: {BG};
                color: {TEXT_DIM};
                border: 1px solid {BORDER};
                border-radius: 6px;
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                border-color: {GOLD_DIMMED};
                color: {GOLD_LIGHT};
            }}
        """
        for btn, val in self._buttons:
            btn.setStyleSheet(active if self._value == val else inactive)


class StatusLED(QWidget):
    """Small connection indicator dot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor(TEXT_DIM)
        self.setFixedSize(12, 12)

    def set_connected(self):
        self._color = QColor(GREEN)
        self.update()

    def set_disconnected(self):
        self._color = QColor(TEXT_DIM)
        self.update()

    def set_warning(self):
        self._color = QColor(AMBER)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        glow = QRadialGradient(6, 6, 6)
        glow.setColorAt(0, self._color)
        c = QColor(self._color)
        c.setAlpha(0)
        glow.setColorAt(1, c)
        p.setBrush(glow)
        p.drawEllipse(0, 0, 12, 12)
        p.end()


class AlertPill(QFrame):
    """Colored status pill for alerts."""

    SEVERITY_COLORS = {
        "success": (GREEN, "#0a2010"),
        "warning": (AMBER, "#1a1400"),
        "error": (RED, "#1a0808"),
        "info": (TEXT_DIM, BG_ELEVATED),
    }

    def __init__(self, text, severity="info", parent=None):
        super().__init__(parent)
        fg, bg = self.SEVERITY_COLORS.get(severity, (TEXT_DIM, BG_ELEVATED))
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 1px solid {fg};
                border-radius: 12px;
                padding: 4px 14px;
            }}
        """)
        lbl = QLabel(text, self)
        lbl.setStyleSheet(f"color: {fg}; font-size: 11px; font-weight: 600; background: transparent; border: none;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(lbl, alignment=Qt.AlignCenter)


# ---------------------------------------------------------------------------
# Brewing Animation
# ---------------------------------------------------------------------------

class BrewingAnimationWidget(QWidget):
    """Live brewing animation — cup fills with coffee, steam rises, progress ring."""
    finished = pyqtSignal()

    def __init__(self, volume_ml=120, style="coffee", parent=None):
        super().__init__(parent)
        self._volume_ml = volume_ml
        self._style = style
        self._progress = 0.0
        self._target_progress = 0.0  # live target from machine
        self._frame = 0
        self._active = False
        self._elapsed = 0
        self._duration_ms = volume_ml * 250
        self._live_mode = False  # True when driven by real machine data
        self._waiting = True  # True until first live data or fallback timeout
        self._temperature = 0  # live temperature from machine (Celsius)
        self._show_enjoy = False  # True after 100% — shows completion message
        self._steam_particles = []
        self.setFixedSize(220, 280)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        # Fallback: exit waiting mode after 15s if no live data arrives
        self._waiting_timeout = QTimer(self)
        self._waiting_timeout.setSingleShot(True)
        self._waiting_timeout.timeout.connect(self._exit_waiting)

    def _exit_waiting(self):
        """Fallback: start non-live time-based animation if no live data arrived."""
        if self._active and self._waiting:
            self._waiting = False
            self._elapsed = 0  # Reset so non-live animation starts from 0%

    def start(self, volume_ml=None):
        if volume_ml is not None:
            self._volume_ml = volume_ml
            self._duration_ms = max(volume_ml * 250, 3000)
        self._progress = 0.0
        self._target_progress = 0.0
        self._frame = 0
        self._elapsed = 0
        self._active = True
        self._live_mode = False
        self._waiting = True
        self._temperature = 0
        self._show_enjoy = False
        self._init_steam()
        self._timer.start()
        self._waiting_timeout.start(15000)
        self.update()

    def set_live_progress(self, percent: int, temperature: int = 0):
        """Set progress from real machine data (0-100%). Switches to live mode."""
        self._live_mode = True
        self._waiting = False
        self._waiting_timeout.stop()
        self._target_progress = min(percent, 100) / 100.0
        self._temperature = temperature
        if percent >= 100 and self._active and not self._show_enjoy:
            self._show_enjoy = True
            QTimer.singleShot(2500, self.stop)

    def stop(self):
        if not self._active:
            return
        self._active = False
        self._timer.stop()
        self._waiting_timeout.stop()
        self.finished.emit()

    def _tick(self):
        self._frame += 1
        self._elapsed += 33
        if self._live_mode:
            # Smoothly interpolate toward real target
            diff = self._target_progress - self._progress
            self._progress += diff * 0.12
            if abs(diff) < 0.002:
                self._progress = self._target_progress
        elif not self._waiting:
            # Non-live fallback (only after waiting timeout expires)
            self._progress = min(1.0, self._elapsed / self._duration_ms)
        # else: waiting mode — progress stays at 0 until live data arrives
        self._update_steam()
        self.update()
        if not self._live_mode and not self._waiting and self._progress >= 1.0 and not self._show_enjoy:
            self._show_enjoy = True
            QTimer.singleShot(2500, self.stop)

    # -- Steam particle system --

    def _init_steam(self):
        import random
        self._steam_particles = [self._new_particle(random.uniform(0, 0.8)) for _ in range(6)]

    def _new_particle(self, age=0.0):
        import random
        return {
            'x': random.uniform(-0.3, 0.3),
            'age': age,
            'max_age': random.uniform(0.6, 1.1),
            'speed': random.uniform(0.008, 0.014),
            'amp': random.uniform(2.0, 5.5),
            'phase': random.uniform(0, 6.28),
        }

    def _update_steam(self):
        import random
        for p in self._steam_particles:
            p['age'] += p['speed']
        self._steam_particles = [p for p in self._steam_particles if p['age'] < p['max_age']]
        target = int(3 + 7 * self._progress)
        while len(self._steam_particles) < target:
            self._steam_particles.append(self._new_particle())

    # -- Paint --

    def paintEvent(self, _event):
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx = w / 2

        cfg = {
            "ristretto": (70, 55, 110),
            "espresso": (80, 65, 100),
            "coffee": (95, 80, 85),
        }.get(self._style, (95, 80, 85))
        cup_w, cup_h, cup_top = cfg
        cup_bot = cup_top + cup_h
        taper = cup_w * 0.08

        # Progress ring (behind cup)
        ring_cx, ring_cy = cx, cup_top + cup_h / 2
        ring_r = max(cup_w, cup_h) / 2 + 22
        p.setPen(QPen(QColor(BORDER), 3))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(ring_cx, ring_cy), ring_r, ring_r)
        p.setPen(QPen(QColor(GOLD), 3, Qt.SolidLine, Qt.RoundCap))
        arc_rect = QRectF(ring_cx - ring_r, ring_cy - ring_r, ring_r * 2, ring_r * 2)
        span = -int(self._progress * 360 * 16)
        p.drawArc(arc_rect, 90 * 16, span)

        # Cup body (ceramic)
        cup_path = QPainterPath()
        cup_path.moveTo(cx - cup_w / 2, cup_top)
        cup_path.lineTo(cx - cup_w / 2 + taper, cup_bot)
        cup_path.quadTo(cx, cup_bot + cup_h * 0.1, cx + cup_w / 2 - taper, cup_bot)
        cup_path.lineTo(cx + cup_w / 2, cup_top)
        cup_path.closeSubpath()

        cup_grad = QLinearGradient(cx - cup_w / 2, cup_top, cx + cup_w / 2, cup_top)
        cup_grad.setColorAt(0.0, QColor(CUP_SHADOW))
        cup_grad.setColorAt(0.3, QColor(CUP_WHITE))
        cup_grad.setColorAt(0.7, QColor(CUP_WHITE))
        cup_grad.setColorAt(1.0, QColor(CUP_SHADOW))
        p.setPen(QPen(QColor(CUP_RIM), 1.5))
        p.setBrush(cup_grad)
        p.drawPath(cup_path)

        # Handle
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(CUP_SHADOW), 2.5, Qt.SolidLine, Qt.RoundCap))
        ht = cup_top + cup_h * 0.15
        hb = cup_top + cup_h * 0.75
        hr = cx + cup_w / 2 + cup_w * 0.22
        handle = QPainterPath()
        handle.moveTo(cx + cup_w / 2 - 1, ht)
        handle.cubicTo(hr, ht, hr, hb, cx + cup_w / 2 - 1, hb)
        p.drawPath(handle)

        # Saucer
        sy = cup_bot + cup_h * 0.10
        p.setPen(QPen(QColor(CUP_SHADOW), 2.0, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(cx - cup_w * 0.6, sy), QPointF(cx + cup_w * 0.6, sy))

        # Coffee filling
        if self._progress > 0.01:
            fill_frac = self._progress
            fill_top = cup_bot - (cup_h * 0.85) * fill_frac
            fill_top = max(fill_top, cup_top + cup_h * 0.10)
            frac_from_top = (fill_top - cup_top) / cup_h
            left_f = (cx - cup_w / 2) + taper * frac_from_top
            right_f = (cx + cup_w / 2) - taper * frac_from_top

            fill_path = QPainterPath()
            fill_path.moveTo(left_f, fill_top)
            fill_path.lineTo(cx - cup_w / 2 + taper, cup_bot)
            fill_path.quadTo(cx, cup_bot + cup_h * 0.1, cx + cup_w / 2 - taper, cup_bot)
            fill_path.lineTo(right_f, fill_top)
            fill_path.closeSubpath()

            coffee_grad = QLinearGradient(cx, cup_bot, cx, fill_top)
            coffee_grad.setColorAt(0.0, QColor(COFFEE_DARK))
            coffee_grad.setColorAt(0.7, QColor(COFFEE_MID))
            coffee_grad.setColorAt(0.95, QColor(COFFEE_LIGHT))
            coffee_grad.setColorAt(1.0, QColor(CREMA))
            p.setPen(Qt.NoPen)
            p.setBrush(coffee_grad)
            p.save()
            p.setClipPath(cup_path)
            p.drawPath(fill_path)
            p.restore()

            # Crema line
            if fill_frac > 0.05:
                crema_w = right_f - left_f - 4
                cc = QColor(CREMA_LIGHT)
                cc.setAlpha(int(120 * min(1.0, fill_frac * 3)))
                p.setPen(Qt.NoPen)
                p.setBrush(cc)
                p.drawEllipse(QPointF(cx, fill_top + 1), crema_w / 2, 3)

        # Pouring stream
        if 0.02 < self._progress < 0.98:
            spout_y = cup_top - 30
            stream_bot = fill_top if self._progress > 0.01 else cup_top + cup_h * 0.15
            wobble = math.sin(self._frame * 0.15) * 1.2
            sc = QColor(COFFEE_DARK)
            sc.setAlpha(200)
            p.setPen(Qt.NoPen)
            p.setBrush(sc)
            p.drawRect(QRectF(cx - 1.75 + wobble, spout_y, 3.5, stream_bot - spout_y))
            # Splash droplets
            for i in range(3):
                dx = math.sin(self._frame * 0.2 + i * 2.1) * 8
                dy = math.cos(self._frame * 0.25 + i * 1.7) * 4
                dc = QColor(COFFEE_MID)
                dc.setAlpha(100)
                p.setBrush(dc)
                p.drawEllipse(QPointF(cx + dx, stream_bot + dy), 1.5, 1.5)

        # Steam particles
        for sp in self._steam_particles:
            alpha = 1.0 - (sp['age'] / sp['max_age'])
            alpha *= min(1.0, self._progress * 4)
            if alpha < 0.02:
                continue
            stc = QColor(CUP_WHITE)
            stc.setAlpha(int(alpha * 55))
            base_y = fill_top if self._progress > 0.01 else cup_top
            x = cx + sp['x'] * cup_w + math.sin(sp['phase'] + sp['age'] * 4) * sp['amp']
            y = base_y - sp['age'] * 50
            radius = 3 + sp['age'] * 8
            p.setPen(Qt.NoPen)
            p.setBrush(stc)
            p.drawEllipse(QPointF(x, y), radius, radius)

        # Percentage (above ring, always shown)
        p.setPen(QColor(GOLD))
        p.setFont(make_font(9))
        p.drawText(QRectF(ring_cx - 20, ring_cy - ring_r - 18, 40, 16),
                   Qt.AlignCenter, f"{int(self._progress * 100)}%")

        # Text baseline — always below both saucer and ring bottom
        text_base = max(sy, ring_cy + ring_r) + 4

        # Bottom text — four states: enjoy / waiting / heating / normal
        if self._show_enjoy:
            # Completion: "Enjoy your coffee!"
            p.setPen(QColor(GOLD))
            p.setFont(make_font(14, QFont.DemiBold, spacing=1))
            p.drawText(QRectF(0, text_base + 6, w, 30), Qt.AlignCenter,
                       "Enjoy your coffee!")
        elif self._waiting and self._progress < 0.01:
            # Waiting for machine — pulsing "Preparing..."
            pulse = 0.5 + 0.5 * math.sin(self._frame * 0.06)
            wait_color = QColor(GOLD_LIGHT)
            wait_color.setAlpha(int(120 + 100 * pulse))
            p.setPen(wait_color)
            p.setFont(make_font(13, QFont.DemiBold))
            p.drawText(QRectF(0, text_base + 6, w, 24), Qt.AlignCenter,
                       "Preparing\u2026")
        elif self._live_mode and self._progress < 0.02 and self._temperature > 0:
            # Heating/grinding phase — prominent pulsing display
            pulse = 0.5 + 0.5 * math.sin(self._frame * 0.08)
            heat_color = QColor(AMBER)
            heat_color.setAlpha(int(160 + 80 * pulse))
            p.setPen(heat_color)
            p.setFont(make_font(13, QFont.DemiBold))
            p.drawText(QRectF(0, text_base + 4, w, 24), Qt.AlignCenter,
                       "Heating up\u2026")
            p.setPen(QColor(AMBER))
            p.setFont(make_font(11))
            p.drawText(QRectF(0, text_base + 26, w, 22), Qt.AlignCenter,
                       f"{self._temperature}\u00b0C")
        else:
            # Normal brewing — volume + temperature
            dispensed = int(self._volume_ml * self._progress)
            p.setPen(QColor(GOLD_LIGHT))
            p.setFont(make_font(11, QFont.DemiBold))
            p.drawText(QRectF(0, text_base + 6, w, 24), Qt.AlignCenter,
                       f"{dispensed} / {self._volume_ml} ml")
            if self._live_mode and self._temperature > 0:
                p.setPen(QColor(AMBER if self._temperature < 60 else GREEN))
                p.setFont(make_font(9))
                p.drawText(QRectF(0, text_base + 28, w, 18), Qt.AlignCenter,
                           f"{self._temperature}\u00b0C")
        p.end()


# ---------------------------------------------------------------------------
# Product Card
# ---------------------------------------------------------------------------

class ProductCard(QFrame):
    brew_requested = pyqtSignal(int, int, int, int, int)  # code, strength, vol_ml, step, temp
    brew_anim_finished = pyqtSignal()  # emitted when this card's brew animation completes

    def __init__(self, product: Product, saved_prefs=None, parent=None):
        super().__init__(parent)
        self._product = product
        prefs = saved_prefs or {}
        self.setFixedWidth(240)
        self.setMinimumHeight(420)
        self.setStyleSheet(f"""
            ProductCard {{
                background-color: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 18px;
            }}
            ProductCard:hover {{
                background-color: {BG_CARD_HVR};
                border-color: {GOLD_DIMMED};
            }}
        """)
        self.setGraphicsEffect(card_shadow())

        # Stacked widget: page 0 = controls, page 1 = brewing animation
        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(0, 0, 0, 0)
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent; border: none;")
        card_layout.addWidget(self._stack)

        # Page 0: Controls
        controls = QWidget()
        controls.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(controls)
        layout.setContentsMargins(24, 28, 24, 24)
        layout.setSpacing(0)

        # Page 1: Brewing animation
        self._brew_anim = BrewingAnimationWidget(product.volume_default, product.icon_style)
        self._brew_anim.finished.connect(self._on_anim_done)
        anim_page = QWidget()
        anim_page.setStyleSheet("background: transparent; border: none;")
        anim_layout = QVBoxLayout(anim_page)
        anim_layout.setContentsMargins(10, 10, 10, 10)
        anim_layout.addWidget(self._brew_anim, alignment=Qt.AlignCenter)

        self._stack.addWidget(controls)
        self._stack.addWidget(anim_page)

        # Coffee cup icon
        icon = CoffeeCupIcon(product.icon_style, size=90)
        layout.addWidget(icon, alignment=Qt.AlignCenter)
        layout.addSpacing(16)

        # Product name
        name = QLabel(product.name.upper())
        name.setFont(make_font(16, QFont.DemiBold, spacing=3))
        name.setStyleSheet(f"color: {TEXT}; background: transparent; border: none;")
        name.setAlignment(Qt.AlignCenter)
        layout.addWidget(name)
        layout.addSpacing(22)

        # Strength (hidden for Hot Water where max=0)
        init_strength = prefs.get("strength", product.strength_default)
        self._strength = StrengthSelector(init_strength, max(product.strength_max, 1))
        if product.strength_max > 0:
            str_label = QLabel("STRENGTH")
            str_label.setFont(make_font(9, QFont.DemiBold, spacing=2))
            str_label.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
            layout.addWidget(str_label)
            layout.addSpacing(6)
            layout.addWidget(self._strength)
            layout.addSpacing(18)

        # Volume
        vol_label = QLabel("VOLUME")
        vol_label.setFont(make_font(9, QFont.DemiBold, spacing=2))
        vol_label.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
        layout.addWidget(vol_label)
        layout.addSpacing(6)

        vol_row = QHBoxLayout()
        vol_row.setSpacing(10)
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(product.volume_min)
        self._slider.setMaximum(product.volume_max)
        self._slider.setSingleStep(product.volume_step)
        self._slider.setPageStep(product.volume_step * 2)
        self._slider.setValue(prefs.get("volume", product.volume_default))
        self._slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {BORDER};
                height: 5px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {GOLD};
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {GOLD_LIGHT};
            }}
            QSlider::sub-page:horizontal {{
                background: {GOLD_DARK};
                border-radius: 2px;
            }}
        """)
        vol_row.addWidget(self._slider, stretch=1)
        init_vol = prefs.get("volume", product.volume_default)
        self._vol_label = QLabel(f"{self._snap_volume(init_vol)} ml")
        self._vol_label.setFixedWidth(52)
        self._vol_label.setFont(make_font(12, QFont.DemiBold))
        self._vol_label.setStyleSheet(f"color: {GOLD_LIGHT}; background: transparent; border: none;")
        self._vol_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        vol_row.addWidget(self._vol_label)
        layout.addLayout(vol_row)

        self._slider.valueChanged.connect(self._on_vol_changed)
        layout.addSpacing(18)

        # Temperature
        temp_label = QLabel("TEMPERATURE")
        temp_label.setFont(make_font(9, QFont.DemiBold, spacing=2))
        temp_label.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
        layout.addWidget(temp_label)
        layout.addSpacing(6)
        self._temp = TempToggle(prefs.get("temperature", product.temp_default))
        layout.addWidget(self._temp)

        layout.addStretch(1)
        layout.addSpacing(12)

        # Brew button
        self._brew_btn = QPushButton("BREW")
        self._brew_btn.setFixedHeight(46)
        self._brew_btn.setCursor(Qt.PointingHandCursor)
        self._brew_btn.setFont(make_font(12, QFont.Bold, spacing=3))
        self._brew_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {GOLD};
                color: {TEXT_DARK};
                border: none;
                border-radius: 12px;
            }}
            QPushButton:hover {{
                background-color: {GOLD_LIGHT};
            }}
            QPushButton:pressed {{
                background-color: {GOLD_DARK};
            }}
            QPushButton:disabled {{
                background-color: {BORDER};
                color: {TEXT_DIM};
            }}
        """)
        self._brew_btn.clicked.connect(self._on_brew)
        layout.addWidget(self._brew_btn)

    def _snap_volume(self, val):
        step = self._product.volume_step
        return round(val / step) * step

    def _on_vol_changed(self, val):
        snapped = self._snap_volume(val)
        self._vol_label.setText(f"{snapped} ml")

    def _on_brew(self):
        vol = self._snap_volume(self._slider.value())
        self.brew_requested.emit(
            self._product.code,
            self._strength.value,
            vol,
            self._product.volume_step,
            self._temp.value,
        )

    def set_brewing(self, active):
        if active:
            vol = self._snap_volume(self._slider.value())
            self._brew_anim.start(volume_ml=vol)
            self._stack.setCurrentIndex(1)
            self._brew_btn.setEnabled(False)
        else:
            if self._brew_anim._active:
                self._brew_anim.stop()
            self._stack.setCurrentIndex(0)
            self._brew_btn.setText("BREW")
            self._brew_btn.setEnabled(True)

    def set_brew_locked(self, locked):
        """Disable/enable BREW button without showing animation (for non-active cards)."""
        self._brew_btn.setEnabled(not locked)

    def _on_anim_done(self):
        self._stack.setCurrentIndex(0)
        self._brew_btn.setText("BREW")
        self._brew_btn.setEnabled(True)
        self.brew_anim_finished.emit()


# ---------------------------------------------------------------------------
# Brew Confirmation Dialog
# ---------------------------------------------------------------------------

class BrewConfirmDialog(QDialog):
    def __init__(self, product_name, strength, volume_ml, temp, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(380, 260)

        container = QFrame(self)
        container.setGeometry(0, 0, 380, 260)
        container.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_CARD};
                border: 1px solid {GOLD_DIMMED};
                border-radius: 20px;
            }}
        """)
        container.setGraphicsEffect(card_shadow())

        lay = QVBoxLayout(container)
        lay.setContentsMargins(32, 28, 32, 24)
        lay.setSpacing(0)

        title = QLabel(f"Brew {product_name}?")
        title.setFont(make_font(18, QFont.DemiBold, spacing=1))
        title.setStyleSheet(f"color: {TEXT}; background: transparent; border: none;")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)
        lay.addSpacing(20)

        temp_name = {0: "Low", 1: "Normal", 2: "High"}.get(temp, "Normal")
        strength_text = f"Strength: {strength}/3    |    " if strength > 0 else ""
        details = QLabel(
            f"{strength_text}{volume_ml} ml    |    {temp_name}"
        )
        details.setFont(make_font(12))
        details.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
        details.setAlignment(Qt.AlignCenter)
        lay.addWidget(details)
        lay.addSpacing(30)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(14)
        cancel = QPushButton("Cancel")
        cancel.setFixedHeight(42)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setFont(make_font(12, QFont.DemiBold, spacing=1))
        cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT_DIM};
                border: 1px solid {BORDER};
                border-radius: 10px;
                padding: 0 28px;
            }}
            QPushButton:hover {{
                border-color: {TEXT_DIM};
                color: {TEXT};
            }}
        """)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        confirm = QPushButton("BREW")
        confirm.setFixedHeight(42)
        confirm.setCursor(Qt.PointingHandCursor)
        confirm.setFont(make_font(12, QFont.Bold, spacing=3))
        confirm.setStyleSheet(f"""
            QPushButton {{
                background-color: {GOLD};
                color: {TEXT_DARK};
                border: none;
                border-radius: 10px;
                padding: 0 36px;
            }}
            QPushButton:hover {{
                background-color: {GOLD_LIGHT};
            }}
        """)
        confirm.clicked.connect(self.accept)
        btn_row.addWidget(confirm)
        lay.addLayout(btn_row)


# ---------------------------------------------------------------------------
# First-Launch Setup Screen
# ---------------------------------------------------------------------------

class SetupScreen(QWidget):
    """One-time setup: user pastes their auth hash (extracted from PCAP)."""
    hash_submitted = pyqtSignal(str)  # the 64-char hex hash

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(2)

        center = QVBoxLayout()
        center.setSpacing(0)
        center.setAlignment(Qt.AlignHCenter)

        brand = QLabel("JURA")
        brand.setFont(make_font(36, QFont.Light, spacing=14))
        brand.setStyleSheet(f"color: {GOLD}; border: none;")
        brand.setAlignment(Qt.AlignCenter)
        center.addWidget(brand)
        center.addSpacing(6)

        sub = QLabel("DESKTOP CONTROL")
        sub.setFont(make_font(11, QFont.Normal, spacing=4))
        sub.setStyleSheet(f"color: {TEXT_DIM}; border: none;")
        sub.setAlignment(Qt.AlignCenter)
        center.addWidget(sub)
        center.addSpacing(8)

        line = QFrame()
        line.setFixedSize(60, 2)
        line.setStyleSheet(f"background-color: {GOLD_DIMMED};")
        center.addWidget(line, alignment=Qt.AlignCenter)
        center.addSpacing(32)

        title = QLabel("First-time setup")
        title.setFont(make_font(16, QFont.DemiBold))
        title.setStyleSheet(f"color: {TEXT}; border: none;")
        title.setAlignment(Qt.AlignCenter)
        center.addWidget(title)
        center.addSpacing(12)

        desc = QLabel(
            "Paste your WiFi Connect V2 authentication hash below.\n"
            "To get it, capture network traffic while J.O.E. connects,\n"
            "then run:  python3 tools/extract_hash.py capture.pcap"
        )
        desc.setFont(make_font(11))
        desc.setStyleSheet(f"color: {TEXT_DIM}; border: none;")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setFixedWidth(440)
        center.addWidget(desc, alignment=Qt.AlignCenter)
        center.addSpacing(24)

        # Hash input
        input_frame = QFrame()
        input_frame.setFixedWidth(480)
        input_frame.setStyleSheet("background: transparent; border: none;")
        inp_lay = QVBoxLayout(input_frame)
        inp_lay.setContentsMargins(0, 0, 0, 0)
        inp_lay.setSpacing(12)

        self._hash_input = QLineEdit()
        self._hash_input.setPlaceholderText("64-character hex hash (e.g. CCC3B0FDD2EE...)")
        self._hash_input.setFixedHeight(44)
        self._hash_input.setFont(make_font(11))
        self._hash_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {BG_ELEVATED};
                color: {GOLD_LIGHT};
                border: 1px solid {BORDER};
                border-radius: 10px;
                padding: 0 14px;
                font-family: monospace;
            }}
            QLineEdit:focus {{ border-color: {GOLD_DIMMED}; }}
        """)
        inp_lay.addWidget(self._hash_input)

        save_btn = QPushButton("SAVE & CONNECT")
        save_btn.setFixedHeight(46)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setFont(make_font(12, QFont.Bold, spacing=2))
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {GOLD};
                color: {TEXT_DARK};
                border: none;
                border-radius: 12px;
            }}
            QPushButton:hover {{ background-color: {GOLD_LIGHT}; }}
        """)
        save_btn.clicked.connect(self._on_submit)
        inp_lay.addWidget(save_btn)

        center.addWidget(input_frame, alignment=Qt.AlignCenter)
        center.addSpacing(16)

        self._error_label = QLabel("")
        self._error_label.setFont(make_font(11))
        self._error_label.setStyleSheet(f"color: {RED}; border: none;")
        self._error_label.setAlignment(Qt.AlignCenter)
        self._error_label.setFixedWidth(440)
        center.addWidget(self._error_label, alignment=Qt.AlignCenter)

        outer.addLayout(center)
        outer.addStretch(3)

    def _on_submit(self):
        raw = self._hash_input.text().strip()
        # Accept with or without spaces/colons
        cleaned = raw.replace(" ", "").replace(":", "").replace("-", "")
        if len(cleaned) != 64:
            self._error_label.setText(
                f"Hash must be exactly 64 hex characters (got {len(cleaned)})"
            )
            return
        try:
            bytes.fromhex(cleaned)
        except ValueError:
            self._error_label.setText("Invalid hex characters in hash")
            return
        self._error_label.setText("")
        self.hash_submitted.emit(cleaned.upper())


# ---------------------------------------------------------------------------
# Connection Screen
# ---------------------------------------------------------------------------

class ConnectionScreen(QWidget):
    """Minimal connection splash — auto-connects on show, manual IP fallback."""
    manual_connect = pyqtSignal(str, int)   # (ip, port)
    retry_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(2)

        center = QVBoxLayout()
        center.setSpacing(0)
        center.setAlignment(Qt.AlignHCenter)

        # Logo
        brand = QLabel("JURA")
        brand.setFont(make_font(36, QFont.Light, spacing=14))
        brand.setStyleSheet(f"color: {GOLD}; border: none;")
        brand.setAlignment(Qt.AlignCenter)
        center.addWidget(brand)
        center.addSpacing(6)

        sub = QLabel("DESKTOP CONTROL")
        sub.setFont(make_font(11, QFont.Normal, spacing=4))
        sub.setStyleSheet(f"color: {TEXT_DIM}; border: none;")
        sub.setAlignment(Qt.AlignCenter)
        center.addWidget(sub)
        center.addSpacing(8)

        line = QFrame()
        line.setFixedSize(60, 2)
        line.setStyleSheet(f"background-color: {GOLD_DIMMED};")
        center.addWidget(line, alignment=Qt.AlignCenter)
        center.addSpacing(40)

        # Status message (shown during auto-connect)
        self._status = QLabel("")
        self._status.setFont(make_font(12))
        self._status.setStyleSheet(f"color: {TEXT_DIM}; border: none;")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setWordWrap(True)
        self._status.setFixedWidth(500)
        self._status.setMinimumHeight(80)
        center.addWidget(self._status, alignment=Qt.AlignCenter)
        center.addSpacing(28)

        # Fallback UI — individual widgets (no container to avoid Fusion phantom borders)
        ip_row = QHBoxLayout()
        ip_row.setContentsMargins(0, 0, 0, 0)
        ip_row.setSpacing(8)
        ip_row.setAlignment(Qt.AlignCenter)

        self._ip_input = QLineEdit()
        self._ip_input.setPlaceholderText(f"Dongle IP  (e.g. {DEFAULT_DONGLE_IP})")
        self._ip_input.setFixedSize(230, 42)
        self._ip_input.setFont(make_font(12))
        self._ip_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {BG_ELEVATED};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 10px;
                padding: 0 14px;
            }}
            QLineEdit:focus {{ border-color: {GOLD_DIMMED}; }}
        """)
        ip_row.addWidget(self._ip_input)

        self._connect_btn = QPushButton("CONNECT")
        self._connect_btn.setFixedSize(100, 42)
        self._connect_btn.setCursor(Qt.PointingHandCursor)
        self._connect_btn.setFont(make_font(11, QFont.Bold, spacing=1))
        self._connect_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {GOLD};
                color: {TEXT_DARK};
                border: none;
                border-radius: 10px;
            }}
            QPushButton:hover {{ background-color: {GOLD_LIGHT}; }}
        """)
        self._connect_btn.clicked.connect(self._on_manual_connect)
        ip_row.addWidget(self._connect_btn)

        center.addLayout(ip_row)
        center.addSpacing(22)

        self._retry_btn = QPushButton("RETRY DISCOVERY")
        self._retry_btn.setFixedSize(200, 38)
        self._retry_btn.setCursor(Qt.PointingHandCursor)
        self._retry_btn.setFont(make_font(10, QFont.DemiBold, spacing=1))
        self._retry_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT_DIM};
                border: 1px solid {BORDER};
                border-radius: 10px;
            }}
            QPushButton:hover {{
                border-color: {GOLD_DIMMED};
                color: {GOLD_LIGHT};
            }}
        """)
        self._retry_btn.clicked.connect(self.retry_requested.emit)
        center.addWidget(self._retry_btn, alignment=Qt.AlignCenter)

        # Initially hidden
        self._fallback_widgets = [self._ip_input, self._connect_btn, self._retry_btn]
        for w in self._fallback_widgets:
            w.hide()

        outer.addLayout(center)
        outer.addStretch(3)

        # Animated dots timer
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate_dots)
        self._dots = 0
        self._anim_base_text = ""

    def show_status(self, msg, color=TEXT_DIM):
        """Show status text (e.g. 'Discovering machine...'), hide fallback."""
        self._status.setText(msg)
        self._status.setStyleSheet(f"color: {color}; border: none;")
        for w in self._fallback_widgets:
            w.hide()

    def start_animation(self, base_text="Connecting"):
        self._anim_base_text = base_text
        self._dots = 0
        self._status.setText(base_text)
        self._status.setStyleSheet(f"color: {GOLD}; border: none;")
        for w in self._fallback_widgets:
            w.hide()
        self._anim_timer.start(400)

    def stop_animation(self):
        self._anim_timer.stop()

    def _animate_dots(self):
        self._dots = (self._dots + 1) % 4
        self._status.setText(self._anim_base_text + "." * self._dots)

    def show_fallback(self, error_msg, default_ip=DEFAULT_DONGLE_IP):
        """Show error and manual connection controls."""
        self.stop_animation()
        self._status.setText(error_msg)
        self._status.setStyleSheet(f"color: {AMBER}; border: none;")
        self._ip_input.setText(default_ip)
        for w in self._fallback_widgets:
            w.show()

    def _on_manual_connect(self):
        ip = self._ip_input.text().strip()
        if not ip:
            self._status.setText("Enter the dongle's IP address")
            self._status.setStyleSheet(f"color: {RED}; border: none;")
            return
        self.start_animation("Connecting")
        self.manual_connect.emit(ip, DONGLE_PORT)


# ---------------------------------------------------------------------------
# Statistics & Maintenance Screen
# ---------------------------------------------------------------------------

class StatCounterCard(QFrame):
    """Product counter card for the statistics screen."""

    def __init__(self, product_name, icon_style="coffee", parent=None):
        super().__init__(parent)
        self._count = 0
        self.setFixedSize(200, 180)
        self.setStyleSheet(f"""
            StatCounterCard {{
                background-color: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 16px;
            }}
        """)
        self.setGraphicsEffect(card_shadow())

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        lay.setSpacing(0)

        icon = CoffeeCupIcon(icon_style, size=52)
        lay.addWidget(icon, alignment=Qt.AlignCenter)
        lay.addSpacing(12)

        self._num = QLabel("\u2014")
        self._num.setFont(make_font(28, QFont.DemiBold))
        self._num.setStyleSheet(f"color: {GOLD}; background: transparent; border: none;")
        self._num.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._num)
        lay.addSpacing(4)

        name = QLabel(product_name.upper())
        name.setFont(make_font(9, QFont.DemiBold, spacing=2))
        name.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
        name.setAlignment(Qt.AlignCenter)
        lay.addWidget(name)

    def set_count(self, count):
        self._count = count
        self._num.setText(f"{count:,}")


class MaintenanceBar(QWidget):
    """Progress bar for maintenance status (cleaning, descaling, filter)."""

    def __init__(self, label, parent=None):
        super().__init__(parent)
        self._pct = -1
        self._count = 0
        self.setFixedHeight(56)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        # Top row: label + percentage + count
        top = QHBoxLayout()
        top.setSpacing(0)
        lbl = QLabel(label)
        lbl.setFont(make_font(11, QFont.DemiBold))
        lbl.setStyleSheet(f"color: {TEXT}; border: none;")
        top.addWidget(lbl)
        top.addStretch()
        self._pct_label = QLabel("\u2014")
        self._pct_label.setFont(make_font(11, QFont.DemiBold))
        self._pct_label.setStyleSheet(f"color: {TEXT_DIM}; border: none;")
        top.addWidget(self._pct_label)
        top.addSpacing(16)
        self._count_label = QLabel("")
        self._count_label.setFont(make_font(10))
        self._count_label.setStyleSheet(f"color: {TEXT_DIM}; border: none;")
        self._count_label.setFixedWidth(80)
        self._count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top.addWidget(self._count_label)
        lay.addLayout(top)

        # Bar
        self._bar = QWidget()
        self._bar.setFixedHeight(10)
        lay.addWidget(self._bar)

    def set_data(self, pct, count):
        self._pct = pct
        self._count = count
        if pct < 0:
            self._pct_label.setText("N/A")
            self._pct_label.setStyleSheet(f"color: {TEXT_DIM}; border: none;")
            self._count_label.setText("")
            self._bar.setStyleSheet(f"""
                background-color: {BORDER};
                border-radius: 5px;
            """)
        else:
            color = GREEN if pct > 50 else (AMBER if pct > 20 else RED)
            self._pct_label.setText(f"{pct}%")
            self._pct_label.setStyleSheet(f"color: {color}; border: none;")
            self._count_label.setText(f"{count} cycle{'s' if count != 1 else ''}")
            self._bar.setStyleSheet(f"""
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {color}, stop:{max(pct / 100, 0.01)} {color},
                    stop:{min(pct / 100 + 0.005, 1)} {BORDER}, stop:1 {BORDER}
                );
                border-radius: 5px;
            """)

    def paintEvent(self, event):
        super().paintEvent(event)


class StatisticsScreen(QWidget):
    """Full-screen statistics and maintenance view."""
    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stats = None

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Header
        header = QFrame()
        header.setFixedHeight(72)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_ELEVATED};
                border-bottom: 1px solid {BORDER};
            }}
        """)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(24, 0, 32, 0)

        back_btn = QPushButton("\u2190")
        back_btn.setFixedSize(40, 36)
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setFont(make_font(18))
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {GOLD};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
            QPushButton:hover {{
                border-color: {GOLD};
                background-color: {BG_CARD};
            }}
        """)
        back_btn.clicked.connect(self.back_requested.emit)
        h_lay.addWidget(back_btn)
        h_lay.addSpacing(16)

        brand = QLabel("JURA")
        brand.setFont(make_font(20, QFont.Light, spacing=8))
        brand.setStyleSheet(f"color: {GOLD}; background: transparent; border: none;")
        h_lay.addWidget(brand)
        h_lay.addSpacing(12)

        title = QLabel("STATISTICS & MAINTENANCE")
        title.setFont(make_font(11, QFont.Normal, spacing=3))
        title.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
        h_lay.addWidget(title)
        h_lay.addStretch()

        self._refresh_btn = QPushButton("REFRESH")
        self._refresh_btn.setFixedHeight(32)
        self._refresh_btn.setCursor(Qt.PointingHandCursor)
        self._refresh_btn.setFont(make_font(10, QFont.DemiBold, spacing=1))
        self._refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {GOLD_DIMMED};
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                border-color: {GOLD};
                color: {GOLD};
            }}
        """)
        h_lay.addWidget(self._refresh_btn)

        main.addWidget(header)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content.setStyleSheet("border: none;")
        c_lay = QVBoxLayout(content)
        c_lay.setContentsMargins(48, 36, 48, 40)
        c_lay.setSpacing(0)

        # -- Beverages section --
        bev_label = QLabel("B E V E R A G E S")
        bev_label.setFont(make_font(10, QFont.DemiBold, spacing=4))
        bev_label.setStyleSheet(f"color: {TEXT_DIM}; border: none;")
        bev_label.setAlignment(Qt.AlignCenter)
        c_lay.addWidget(bev_label)
        c_lay.addSpacing(24)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(24)
        cards_row.setAlignment(Qt.AlignCenter)

        self._espresso_card = StatCounterCard("Espresso", "espresso")
        self._coffee_card = StatCounterCard("Coffee", "coffee")
        self._hotwater_card = StatCounterCard("Hot Water", "coffee")
        cards_row.addWidget(self._espresso_card)
        cards_row.addWidget(self._coffee_card)
        cards_row.addWidget(self._hotwater_card)
        c_lay.addLayout(cards_row)
        c_lay.addSpacing(16)

        self._total_label = QLabel("")
        self._total_label.setFont(make_font(12))
        self._total_label.setStyleSheet(f"color: {TEXT_DIM}; border: none;")
        self._total_label.setAlignment(Qt.AlignCenter)
        c_lay.addWidget(self._total_label)
        c_lay.addSpacing(36)

        # Divider
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {BORDER};")
        c_lay.addWidget(divider)
        c_lay.addSpacing(36)

        # -- Maintenance section --
        maint_label = QLabel("M A I N T E N A N C E")
        maint_label.setFont(make_font(10, QFont.DemiBold, spacing=4))
        maint_label.setStyleSheet(f"color: {TEXT_DIM}; border: none;")
        maint_label.setAlignment(Qt.AlignCenter)
        c_lay.addWidget(maint_label)
        c_lay.addSpacing(28)

        bars_container = QWidget()
        bars_container.setFixedWidth(520)
        bars_lay = QVBoxLayout(bars_container)
        bars_lay.setContentsMargins(0, 0, 0, 0)
        bars_lay.setSpacing(16)

        self._clean_bar = MaintenanceBar("Cleaning")
        self._descale_bar = MaintenanceBar("Descaling")
        self._filter_bar = MaintenanceBar("Filter")
        bars_lay.addWidget(self._clean_bar)
        bars_lay.addWidget(self._descale_bar)
        bars_lay.addWidget(self._filter_bar)

        c_lay.addWidget(bars_container, alignment=Qt.AlignCenter)
        c_lay.addSpacing(36)

        # Status line
        self._status_label = QLabel("")
        self._status_label.setFont(make_font(10))
        self._status_label.setStyleSheet(f"color: {TEXT_DIM}; border: none;")
        self._status_label.setAlignment(Qt.AlignCenter)
        c_lay.addWidget(self._status_label)

        c_lay.addStretch()

        scroll.setWidget(content)
        main.addWidget(scroll, stretch=1)

        # Loading animation
        self._load_timer = QTimer(self)
        self._load_timer.timeout.connect(self._animate_loading)
        self._load_dots = 0

    def set_refresh_handler(self, handler):
        self._refresh_btn.clicked.connect(handler)

    def show_loading(self):
        self._status_label.setText("Loading statistics")
        self._status_label.setStyleSheet(f"color: {GOLD}; border: none;")
        self._refresh_btn.setEnabled(False)
        self._load_dots = 0
        self._load_timer.start(400)

    def _animate_loading(self):
        self._load_dots = (self._load_dots + 1) % 4
        self._status_label.setText("Loading statistics" + "." * self._load_dots)

    def update_statistics(self, stats: MachineStatistics):
        self._stats = stats
        self._load_timer.stop()
        self._refresh_btn.setEnabled(True)

        # Product counters
        self._espresso_card.set_count(stats.espresso_count)
        self._coffee_card.set_count(stats.coffee_count)
        self._hotwater_card.set_count(stats.hotwater_count)
        self._total_label.setText(
            f"Total: {stats.total_products:,} beverages"
            if stats.total_products > 0
            else "Total: \u2014"
        )

        # Maintenance bars
        self._clean_bar.set_data(stats.cleaning_pct, stats.cleaning_count)
        self._descale_bar.set_data(stats.descaling_pct, stats.descaling_count)
        self._filter_bar.set_data(stats.filter_pct, stats.filter_count)

        import datetime
        now = datetime.datetime.now().strftime("%H:%M")
        self._status_label.setText(f"Last refreshed at {now}")
        self._status_label.setStyleSheet(f"color: {TEXT_DIM}; border: none;")


# ---------------------------------------------------------------------------
# Dashboard Screen
# ---------------------------------------------------------------------------

class DashboardScreen(QWidget):
    brew_requested = pyqtSignal(int, int, int, int, int)
    stats_requested = pyqtSignal()

    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._cards = []
        self._alert_pills = []
        self._brewing_card_idx = None  # index of the card currently brewing

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Header
        header = QFrame()
        header.setFixedHeight(72)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_ELEVATED};
                border-bottom: 1px solid {BORDER};
            }}
        """)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(32, 0, 32, 0)

        brand = QLabel("JURA")
        brand.setFont(make_font(20, QFont.Light, spacing=8))
        brand.setStyleSheet(f"color: {GOLD}; background: transparent; border: none;")
        h_lay.addWidget(brand)
        h_lay.addSpacing(12)

        self._machine_label = QLabel("E4")
        self._machine_label.setFont(make_font(13, QFont.Normal, spacing=1))
        self._machine_label.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
        h_lay.addWidget(self._machine_label)
        h_lay.addStretch()

        self._led = StatusLED()
        h_lay.addWidget(self._led)
        h_lay.addSpacing(8)
        self._conn_label = QLabel("Connected")
        self._conn_label.setFont(make_font(11))
        self._conn_label.setStyleSheet(f"color: {GREEN}; background: transparent; border: none;")
        h_lay.addWidget(self._conn_label)
        h_lay.addSpacing(16)

        stats_btn = QPushButton("Statistics")
        stats_btn.setFixedHeight(32)
        stats_btn.setCursor(Qt.PointingHandCursor)
        stats_btn.setFont(make_font(10, QFont.DemiBold))
        stats_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {GOLD_DIMMED};
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                border-color: {GOLD};
                color: {GOLD};
            }}
        """)
        stats_btn.clicked.connect(self.stats_requested.emit)
        h_lay.addWidget(stats_btn)
        h_lay.addSpacing(8)

        disc_btn = QPushButton("Disconnect")
        disc_btn.setFixedHeight(32)
        disc_btn.setCursor(Qt.PointingHandCursor)
        disc_btn.setFont(make_font(10, QFont.DemiBold))
        disc_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT_DIM};
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                border-color: {RED};
                color: {RED};
            }}
        """)
        disc_btn.setObjectName("disconnectBtn")
        h_lay.addWidget(disc_btn)
        self._disconnect_btn = disc_btn

        main.addWidget(header)

        # Product cards area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent; border: none;")
        scroll_lay = QVBoxLayout(scroll_content)
        scroll_lay.setContentsMargins(0, 40, 0, 40)

        self._cards_layout = QHBoxLayout()
        self._cards_layout.setSpacing(28)
        self._cards_layout.setAlignment(Qt.AlignCenter)

        for product in E4_PRODUCTS:
            saved = settings.get_product(product.name) if settings else {}
            card = ProductCard(product, saved)
            card.brew_requested.connect(self._on_card_brew)
            card.brew_anim_finished.connect(self._on_brew_anim_finished)
            self._cards.append(card)
            self._cards_layout.addWidget(card)

        scroll_lay.addLayout(self._cards_layout)
        scroll_lay.addStretch()
        scroll.setWidget(scroll_content)
        main.addWidget(scroll, stretch=1)

        # Status / alert bar
        self._alert_bar = QFrame()
        self._alert_bar.setMinimumHeight(52)
        self._alert_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_ELEVATED};
                border-top: 1px solid {BORDER};
            }}
        """)
        self._alert_layout = QHBoxLayout(self._alert_bar)
        self._alert_layout.setContentsMargins(32, 8, 32, 8)
        self._alert_layout.setSpacing(8)

        status_icon = QLabel("STATUS")
        status_icon.setFont(make_font(9, QFont.DemiBold, spacing=2))
        status_icon.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
        self._alert_layout.addWidget(status_icon)
        self._alert_layout.addSpacing(8)
        self._alert_layout.addStretch()

        main.addWidget(self._alert_bar)

        # Toast area
        self._toast = QLabel("")
        self._toast.setFixedHeight(0)
        self._toast.setAlignment(Qt.AlignCenter)
        self._toast.setStyleSheet(f"""
            background-color: {GREEN};
            color: {TEXT_DARK};
            font-size: 12px;
            font-weight: 700;
            border: none;
        """)
        main.addWidget(self._toast)

        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._hide_toast)

    def _on_card_brew(self, code, strength, vol_ml, step, temp):
        product_name = next(
            (p.name for p in E4_PRODUCTS if p.code == code), "Coffee"
        )
        dlg = BrewConfirmDialog(product_name, strength, vol_ml, temp, self)
        dlg.move(
            self.mapToGlobal(self.rect().center()) - dlg.rect().center()
        )
        if dlg.exec_() == QDialog.Accepted:
            self.brew_requested.emit(code, strength, vol_ml, step, temp)
            # Animate ONLY the card being brewed; lock the others
            self._brewing_card_idx = None
            for i, card in enumerate(self._cards):
                if card._product.code == code:
                    card.set_brewing(True)
                    self._brewing_card_idx = i
                else:
                    card.set_brew_locked(True)

    def set_machine_info(self, info):
        short = info[:40] if len(info) > 40 else info
        self._machine_label.setText(short)

    def set_connected(self):
        self._led.set_connected()
        self._conn_label.setText("Connected")
        self._conn_label.setStyleSheet(f"color: {GREEN}; background: transparent; border: none;")

    def set_disconnected(self):
        self._led.set_disconnected()
        self._conn_label.setText("Disconnected")
        self._conn_label.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")

    def set_reconnecting(self):
        self._led.set_warning()
        self._conn_label.setText("Reconnecting...")
        self._conn_label.setStyleSheet(f"color: {AMBER}; background: transparent; border: none;")

    def update_alerts(self, alerts):
        # Clear old pills (keep the STATUS label and spacer)
        while self._alert_layout.count() > 3:
            item = self._alert_layout.takeAt(2)
            if item.widget():
                item.widget().deleteLater()

        if not alerts:
            pill = AlertPill("All clear", "success")
            self._alert_layout.insertWidget(2, pill)
        else:
            for _, name, severity in alerts:
                pill = AlertPill(name, severity)
                self._alert_layout.insertWidget(self._alert_layout.count() - 1, pill)

    def on_brew_started(self):
        self._show_toast("Brewing started!", GREEN)

    def on_brew_progress(self, percent, temperature):
        """Forward live brew progress to the active card's animation only."""
        if self._brewing_card_idx is not None:
            card = self._cards[self._brewing_card_idx]
            card._brew_anim.set_live_progress(percent, temperature)

    def on_brew_error(self, msg):
        self._show_toast(f"Brew failed: {msg}", RED)
        self._brewing_card_idx = None
        for card in self._cards:
            card.set_brewing(False)
            card.set_brew_locked(False)

    def on_brew_status_clear(self):
        """Safety clear — resets all cards (idempotent with _on_brew_anim_finished)."""
        self._brewing_card_idx = None
        for card in self._cards:
            card.set_brewing(False)
            card.set_brew_locked(False)

    def _on_brew_anim_finished(self):
        """Active card's animation completed — show enjoy toast, unlock other cards."""
        self._show_toast("Enjoy your coffee!", GOLD)
        self._brewing_card_idx = None
        for card in self._cards:
            card.set_brew_locked(False)

    def _show_toast(self, text, color):
        self._toast.setText(text)
        self._toast.setFixedHeight(36)
        self._toast.setStyleSheet(f"""
            background-color: {color};
            color: {TEXT_DARK};
            font-size: 12px;
            font-weight: 700;
            border: none;
        """)
        self._toast_timer.start(3000)

    def _hide_toast(self):
        self._toast.setFixedHeight(0)
        self._toast.setText("")


# ---------------------------------------------------------------------------
# Settings Persistence
# ---------------------------------------------------------------------------

SETTINGS_DIR = os.path.expanduser("~/.config/jura-desktop")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")


class Settings:
    """Persists user preferences across sessions."""

    def __init__(self):
        self._data = {}
        self._load()

    def _load(self):
        try:
            with open(SETTINGS_FILE) as f:
                self._data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self._data = {}

    def save(self):
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        tmp = SETTINGS_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self._data, f, indent=2)
        os.replace(tmp, SETTINGS_FILE)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def get_product(self, product_name):
        """Get saved preferences for a product (strength, volume, temperature)."""
        return self._data.get(f"product_{product_name.lower()}", {})

    def set_product(self, product_name, strength, volume, temperature):
        self._data[f"product_{product_name.lower()}"] = {
            "strength": strength,
            "volume": volume,
            "temperature": temperature,
        }


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY_MS = 5000


class JuraApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JURA Desktop Control")
        self.setMinimumSize(900, 680)
        self.resize(1060, 740)
        self.setStyleSheet(STYLESHEET)

        self._settings = Settings()
        self._wifi = WiFiV2Manager()
        self._user_disconnect = False
        self._reconnecting = False
        self._reconnect_attempts = 0
        self._tried_scan = False

        # Apply saved auth hash (overrides the module default)
        saved_hash = self._settings.get("auth_hash")
        if saved_hash:
            self._wifi._auth_hash = saved_hash

        # Stacked views
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._setup_screen = SetupScreen()
        self._conn_screen = ConnectionScreen()
        self._dashboard = DashboardScreen(self._settings)
        self._stats_screen = StatisticsScreen()
        self._stack.addWidget(self._setup_screen)   # index 0
        self._stack.addWidget(self._conn_screen)    # index 1
        self._stack.addWidget(self._dashboard)      # index 2
        self._stack.addWidget(self._stats_screen)   # index 3

        # Wire up setup screen
        self._setup_screen.hash_submitted.connect(self._on_hash_submitted)

        # Wire up connection screen
        self._conn_screen.manual_connect.connect(self._on_manual_connect)
        self._conn_screen.retry_requested.connect(self._on_retry)

        # Wire up dashboard
        self._dashboard._disconnect_btn.clicked.connect(self._on_disconnect)
        self._dashboard.brew_requested.connect(self._on_brew)
        self._dashboard.stats_requested.connect(self._on_show_stats)

        # Wire up statistics screen
        self._stats_screen.back_requested.connect(self._on_stats_back)
        self._stats_screen.set_refresh_handler(self._on_stats_refresh)

        # Wire up WiFi V2 signals
        self._wifi.scan_finished.connect(self._on_scan_finished)
        self._wifi.connect_ok.connect(self._on_connected)
        self._wifi.connect_fail.connect(self._on_connect_failed)
        self._wifi.disconnected.connect(self._on_disconnected)
        self._wifi.status_update.connect(self._on_status)
        self._wifi.brew_started.connect(self._on_brew_started)
        self._wifi.brew_progress.connect(self._on_brew_progress)
        self._wifi.brew_error.connect(self._on_brew_error)
        self._wifi.error.connect(self._on_error)
        self._wifi.statistics_ready.connect(self._on_statistics_ready)

        # Brew completion timer
        self._brew_timer = QTimer(self)
        self._brew_timer.setSingleShot(True)
        self._brew_timer.timeout.connect(self._dashboard.on_brew_status_clear)

        # Brew safety timeout (120s max brew time)
        self._brew_safety_timer = QTimer(self)
        self._brew_safety_timer.setSingleShot(True)
        self._brew_safety_timer.timeout.connect(self._on_brew_timeout)

        # Reconnect timer
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._try_reconnect)

        # System tray
        self._quitting = False
        self._setup_tray()

        # Launch: setup screen if no hash, otherwise auto-connect
        if self._wifi._auth_hash:
            self._stack.setCurrentWidget(self._conn_screen)
            QTimer.singleShot(300, self._auto_connect)
        else:
            self._stack.setCurrentWidget(self._setup_screen)

    # ======================================================================
    # System tray
    # ======================================================================

    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._tray = None
            return

        self._tray = QSystemTrayIcon(self)
        icon_path = os.path.join(APP_DIR, "icon_256.png")
        if os.path.exists(icon_path):
            self._tray.setIcon(QIcon(icon_path))
        self._tray.setToolTip("JURA Desktop Control")
        self._tray.activated.connect(self._on_tray_activated)

        menu = QMenu()
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {BG_CARD};
                color: {TEXT};
                border: 1px solid {BORDER};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 12px;
            }}
            QMenu::item:selected {{
                background-color: {GOLD_DARK};
                color: {TEXT_DARK};
            }}
            QMenu::separator {{
                height: 1px;
                background: {BORDER};
                margin: 4px 8px;
            }}
        """)

        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self._tray_show)
        menu.addAction(show_action)
        menu.addSeparator()

        self._tray_espresso = QAction("Brew Espresso", self)
        self._tray_espresso.triggered.connect(lambda: self._tray_brew(0x02))
        menu.addAction(self._tray_espresso)

        self._tray_coffee = QAction("Brew Coffee", self)
        self._tray_coffee.triggered.connect(lambda: self._tray_brew(0x03))
        menu.addAction(self._tray_coffee)

        self._tray_hotwater = QAction("Brew Hot Water", self)
        self._tray_hotwater.triggered.connect(lambda: self._tray_brew(0x0D))
        menu.addAction(self._tray_hotwater)

        menu.addSeparator()
        self._tray_status = QAction("Not connected", self)
        self._tray_status.setEnabled(False)
        menu.addAction(self._tray_status)
        menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._tray_quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.show()
        self._update_tray_brew_actions(False)

    def _update_tray_brew_actions(self, connected):
        if not self._tray:
            return
        for action in (self._tray_espresso, self._tray_coffee, self._tray_hotwater):
            action.setEnabled(connected)
        self._tray_status.setText(
            "Connected" if connected else "Not connected"
        )

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._tray_show()

    def _tray_show(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _tray_brew(self, product_code):
        """Quick-brew from tray with saved preferences."""
        if not self._wifi.is_connected or self._wifi.is_brewing:
            return
        self._tray_show()
        product = next((p for p in E4_PRODUCTS if p.code == product_code), None)
        if not product:
            return
        saved = self._settings.get_product(product.name)
        strength = saved.get("strength", product.strength_default)
        volume = saved.get("volume", product.volume_default)
        temp = saved.get("temperature", product.temp_default)
        # Show confirmation dialog (safety — don't brew without user seeing it)
        from jura_app import BrewConfirmDialog
        dlg = BrewConfirmDialog(product.name, strength, volume, temp, self)
        dlg.move(self.mapToGlobal(self.rect().center()) - dlg.rect().center())
        if dlg.exec_() == QDialog.Accepted:
            self._on_brew(product_code, strength, volume, product.volume_step, temp)
            self._dashboard._brewing_card_idx = None
            for i, card in enumerate(self._dashboard._cards):
                if card._product.code == product_code:
                    card.set_brewing(True)
                    self._dashboard._brewing_card_idx = i
                else:
                    card.set_brew_locked(True)

    def _tray_quit(self):
        self._quitting = True
        self.close()

    # ======================================================================
    # Setup
    # ======================================================================

    def _on_hash_submitted(self, auth_hash):
        self._settings.set("auth_hash", auth_hash)
        self._settings.save()
        self._wifi._auth_hash = auth_hash
        self._stack.setCurrentWidget(self._conn_screen)
        QTimer.singleShot(300, self._auto_connect)

    # ======================================================================
    # Auto-connect flow
    # ======================================================================

    def _auto_connect(self):
        """Try saved IP first, fall back to UDP discovery."""
        self._tried_scan = False
        saved_ip = self._settings.get("dongle_ip")
        if saved_ip:
            self._conn_screen.start_animation("Connecting")
            self._wifi.connect_machine(saved_ip)
        else:
            self._conn_screen.start_animation("Discovering machine")
            self._wifi.scan()

    def _on_scan_finished(self, devices):
        if devices:
            dev = devices[0]
            self._conn_screen.start_animation("Connecting")
            self._wifi.connect_machine(dev.ip, dev.port)
        else:
            self._conn_screen.show_fallback(
                "No JURA machine found on the network.\n"
                "Make sure the WiFi Connect dongle is plugged in\n"
                "and the machine is powered on.",
                DEFAULT_DONGLE_IP,
            )

    def _on_manual_connect(self, ip, port):
        self._wifi.connect_machine(ip, port)

    def _on_retry(self):
        self._conn_screen.start_animation("Discovering machine")
        self._wifi.scan()

    # ======================================================================
    # Connection callbacks
    # ======================================================================

    def _on_connected(self, info):
        self._reconnecting = False
        self._reconnect_attempts = 0
        self._conn_screen.stop_animation()

        # Save the working IP for next launch
        if self._wifi._dongle_ip:
            self._settings.set("dongle_ip", self._wifi._dongle_ip)
            self._settings.save()

        self._dashboard.set_machine_info(info)
        self._dashboard.set_connected()
        self._stack.setCurrentWidget(self._dashboard)
        self._update_tray_brew_actions(True)

    def _on_connect_failed(self, msg):
        # During reconnect — retry after delay
        if self._reconnecting:
            self._reconnect_attempts += 1
            if self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                self._reconnecting = False
                self._dashboard.set_disconnected()
                self._stack.setCurrentWidget(self._conn_screen)
                self._conn_screen.show_fallback(
                    "Connection lost — could not reconnect.",
                    self._settings.get("dongle_ip", DEFAULT_DONGLE_IP),
                )
            else:
                self._reconnect_timer.start(RECONNECT_DELAY_MS)
            return

        # During initial connect — try scan as fallback
        if not self._tried_scan:
            self._tried_scan = True
            self._conn_screen.start_animation("Discovering machine")
            self._wifi.scan()
            return

        # All attempts exhausted — show manual fallback
        self._conn_screen.show_fallback(
            f"Connection failed: {msg}",
            self._settings.get("dongle_ip", DEFAULT_DONGLE_IP),
        )

    def _on_disconnected(self):
        self._brew_safety_timer.stop()
        self._dashboard.on_brew_status_clear()
        self._update_tray_brew_actions(False)

        if self._user_disconnect:
            self._user_disconnect = False
            self._dashboard.set_disconnected()
            self._stack.setCurrentWidget(self._conn_screen)
            self._conn_screen.show_status("Disconnected", AMBER)
            for w in self._conn_screen._fallback_widgets:
                w.show()
            self._conn_screen._ip_input.setText(
                self._settings.get("dongle_ip", DEFAULT_DONGLE_IP)
            )
            return

        # Unexpected disconnect — auto-reconnect
        self._reconnecting = True
        self._reconnect_attempts = 0
        self._dashboard.set_reconnecting()
        self._try_reconnect()

    def _try_reconnect(self):
        ip = self._settings.get("dongle_ip", DEFAULT_DONGLE_IP)
        self._wifi.connect_machine(ip)

    # ======================================================================
    # User actions
    # ======================================================================

    def _on_disconnect(self):
        self._user_disconnect = True
        self._reconnecting = False
        self._reconnect_timer.stop()
        self._wifi.disconnect_machine()

    def _on_brew(self, code, strength, vol_ml, step, temp):
        if self._wifi.is_brewing:
            self._dashboard.on_brew_error("A brew is already in progress")
            return
        self._brew_timer.stop()  # Cancel any stale brew-clear from old status polls
        # Save preferences
        product = next((p for p in E4_PRODUCTS if p.code == code), None)
        if product:
            self._settings.set_product(product.name, strength, vol_ml, temp)
            self._settings.save()
        self._wifi.brew(code, strength, vol_ml, step, temp)

    # ======================================================================
    # Status & brew callbacks
    # ======================================================================

    def _on_status(self, alerts):
        self._dashboard.update_alerts(alerts)
        if any(bit == 31 for bit, _, _ in alerts):
            # Only start brew cleanup timer if a brew animation is active —
            # bit 31 persists from old brews and would kill new animations
            if self._dashboard._brewing_card_idx is not None:
                self._brew_timer.start(3000)
                self._brew_safety_timer.stop()
        if self._wifi.is_brewing:
            critical_bits = {0, 1, 2, 4, 5, 6, 10}
            for bit, name, _ in alerts:
                if bit in critical_bits:
                    self._dashboard.on_brew_error(f"Machine alert: {name}")
                    self._brew_safety_timer.stop()
                    break

    def _on_brew_started(self):
        self._brew_timer.stop()  # Cancel any stale brew-clear from old status polls
        self._dashboard.on_brew_started()
        self._brew_safety_timer.start(120_000)

    def _on_brew_progress(self, percent, temperature):
        self._dashboard.on_brew_progress(percent, temperature)
        if percent >= 100:
            self._brew_safety_timer.stop()
            self._brew_timer.start(3000)

    def _on_brew_error(self, msg):
        self._dashboard.on_brew_error(msg)
        self._brew_safety_timer.stop()

    def _on_brew_timeout(self):
        self._dashboard.on_brew_error("Brew timed out (120s)")
        self._dashboard.on_brew_status_clear()

    def _on_error(self, msg):
        if self._stack.currentWidget() == self._conn_screen:
            self._conn_screen.show_fallback(
                msg, self._settings.get("dongle_ip", DEFAULT_DONGLE_IP)
            )

    # ======================================================================
    # Statistics
    # ======================================================================

    def _on_show_stats(self):
        self._stats_screen.show_loading()
        self._stack.setCurrentWidget(self._stats_screen)
        self._wifi.read_statistics()

    def _on_stats_back(self):
        self._stack.setCurrentWidget(self._dashboard)

    def _on_stats_refresh(self):
        self._stats_screen.show_loading()
        self._wifi.read_statistics()

    def _on_statistics_ready(self, stats):
        self._stats_screen.update_statistics(stats)

    def closeEvent(self, event):
        # Minimize to tray instead of quitting (if tray is available)
        if self._tray and not self._quitting:
            event.ignore()
            self.hide()
            self._tray.showMessage(
                "JURA Desktop Control",
                "Running in the background. Right-click the tray icon for options.",
                QSystemTrayIcon.Information,
                2000,
            )
            return
        # Actually quitting
        self._reconnect_timer.stop()
        if self._tray:
            self._tray.hide()
        self._wifi.disconnect_and_wait(timeout=3)
        self._wifi.shutdown()
        event.accept()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BG))
    palette.setColor(QPalette.WindowText, QColor(TEXT))
    palette.setColor(QPalette.Base, QColor(BG_ELEVATED))
    palette.setColor(QPalette.AlternateBase, QColor(BG_CARD))
    palette.setColor(QPalette.Text, QColor(TEXT))
    palette.setColor(QPalette.Button, QColor(BG_CARD))
    palette.setColor(QPalette.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.Highlight, QColor(GOLD))
    palette.setColor(QPalette.HighlightedText, QColor(TEXT_DARK))
    app.setPalette(palette)

    icon_path = os.path.join(APP_DIR, "icon_256.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = JuraApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
