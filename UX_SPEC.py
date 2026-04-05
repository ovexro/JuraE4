"""
JURA Desktop Control — Premium UX Improvements Specification
=============================================================

Complete, implementable PyQt5 specifications for each enhancement.
All code references the existing theme constants from jura_app.py.

Existing theme palette (for reference):
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

Additional colors introduced by this spec:
    COFFEE_DARK    = "#2c1810"   # Dark coffee liquid (ristretto / top of cup)
    COFFEE_MID     = "#4a2c1a"   # Mid coffee tone
    COFFEE_LIGHT   = "#6b3a20"   # Lighter coffee (crema edge)
    CREMA          = "#c4956a"   # Crema surface color
    CREMA_LIGHT    = "#d4a878"   # Crema highlight
    STEAM_COLOR    = "#ede4d4"   # Steam wisps (same as TEXT, faded)
    CUP_WHITE      = "#e8e0d4"   # Ceramic cup body
    CUP_SHADOW     = "#b8b0a4"   # Cup body shadow side
    CUP_RIM        = "#f5f0e8"   # Cup rim highlight
"""


# ============================================================================
# 1. BREWING ANIMATION (P0 — Must Have)
# ============================================================================
"""
OVERVIEW:
    When the user clicks BREW and confirms, the product card transitions into
    a full-card brewing animation. The existing CoffeeCupIcon is replaced by
    a BrewingAnimationWidget that renders:
      - A ceramic coffee cup (white/cream, more realistic than the line-art icon)
      - Liquid pouring from the top (a stream from a spout above the cup)
      - The cup gradually filling with dark coffee
      - A crema layer forming on top of the liquid
      - Steam wisps rising from the surface, intensifying as the cup fills
      - A circular progress ring around the cup
      - Volume text (e.g., "67 / 120 ml") below the cup

TIMING:
    The animation duration is proportional to volume:
        duration_ms = volume_ml * 250
    So: 25ml = 6.25s, 40ml = 10s, 120ml = 30s, 240ml = 60s
    The QTimer ticks at 33ms intervals (~30 fps).
    Progress goes from 0.0 to 1.0 over duration_ms.

CLASS: BrewingAnimationWidget(QWidget)

    __init__(self, volume_ml, product_style, parent=None):
        self._volume_ml = volume_ml
        self._style = product_style  # "ristretto", "espresso", "coffee"
        self._progress = 0.0         # 0.0 to 1.0
        self._frame = 0              # monotonic frame counter
        self._active = False
        self._steam_particles = []   # list of (x_offset, y_offset, age, speed, amplitude)
        self.setFixedSize(220, 260)  # fits inside the card where icon + controls were

        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 fps
        self._timer.timeout.connect(self._tick)

    # -- Signals --
    finished = pyqtSignal()          # emitted when progress reaches 1.0

    def start(self):
        self._progress = 0.0
        self._frame = 0
        self._active = True
        self._duration_ms = self._volume_ml * 250
        self._elapsed = 0
        self._init_steam_particles()
        self._timer.start()

    def stop(self):
        self._active = False
        self._timer.stop()
        self.finished.emit()

    def _tick(self):
        self._frame += 1
        self._elapsed += 33
        self._progress = min(1.0, self._elapsed / self._duration_ms)
        self._update_steam_particles()
        self.update()  # triggers paintEvent
        if self._progress >= 1.0:
            # Hold the full-cup state for 1.5 seconds, then emit finished
            QTimer.singleShot(1500, self.stop)
            self._timer.stop()

    # -- Steam Particle System --
    # Each particle: [x_base, y, age, max_age, speed, amplitude, phase]

    def _init_steam_particles(self):
        self._steam_particles = []
        # Pre-populate 8 particles at random phases
        import random
        for _ in range(8):
            self._steam_particles.append(self._new_steam_particle(random.uniform(0, 1)))

    def _new_steam_particle(self, age_fraction=0.0):
        import random
        return {
            'x_base': random.uniform(-0.3, 0.3),  # fraction of cup width
            'y': 0.0,
            'age': age_fraction,     # 0.0 to 1.0
            'max_age': random.uniform(0.7, 1.2),
            'speed': random.uniform(0.008, 0.015),
            'amplitude': random.uniform(2.0, 6.0),
            'phase': random.uniform(0, 6.28),
        }

    def _update_steam_particles(self):
        import math, random
        for p in self._steam_particles:
            p['age'] += p['speed']
            p['y'] = p['age'] * 50  # pixels upward
        # Remove dead particles, add new ones
        self._steam_particles = [p for p in self._steam_particles if p['age'] < p['max_age']]
        # More steam as cup fills (3 particles when empty, 10 when full)
        target_count = int(3 + 7 * self._progress)
        while len(self._steam_particles) < target_count:
            self._steam_particles.append(self._new_steam_particle())

    # -- Paint --
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx = w / 2

        # --- Geometry (all coordinates relative to widget) ---
        # Cup dimensions vary by style
        cup_configs = {
            "ristretto": {"cup_w": 70, "cup_h": 55, "cup_top": 100},
            "espresso":  {"cup_w": 80, "cup_h": 65, "cup_top": 90},
            "coffee":    {"cup_w": 95, "cup_h": 80, "cup_top": 75},
        }
        cfg = cup_configs.get(self._style, cup_configs["coffee"])
        cup_w = cfg["cup_w"]
        cup_h = cfg["cup_h"]
        cup_top = cfg["cup_top"]
        cup_bot = cup_top + cup_h
        taper = cup_w * 0.08  # bottom is slightly narrower

        # Spout position (where liquid pours from)
        spout_x = cx
        spout_y = cup_top - 30

        # --- 1. Draw circular progress ring (behind the cup) ---
        ring_cx, ring_cy = cx, cup_top + cup_h / 2
        ring_r = max(cup_w, cup_h) / 2 + 20
        # Background ring (dim)
        p.setPen(QPen(QColor(BORDER), 3))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(ring_cx, ring_cy), ring_r, ring_r)
        # Progress arc (gold)
        p.setPen(QPen(QColor(GOLD), 3, Qt.SolidLine, Qt.RoundCap))
        arc_rect = QRectF(ring_cx - ring_r, ring_cy - ring_r, ring_r * 2, ring_r * 2)
        # Qt arcs: start at 12 o'clock (90*16), sweep clockwise (negative)
        span = -int(self._progress * 360 * 16)
        p.drawArc(arc_rect, 90 * 16, span)

        # --- 2. Draw the cup body (ceramic) ---
        # Cup is a trapezoid with rounded bottom
        cup_path = QPainterPath()
        cup_path.moveTo(cx - cup_w/2, cup_top)
        cup_path.lineTo(cx - cup_w/2 + taper, cup_bot)
        cup_path.quadTo(cx, cup_bot + cup_h * 0.1, cx + cup_w/2 - taper, cup_bot)
        cup_path.lineTo(cx + cup_w/2, cup_top)
        cup_path.closeSubpath()

        # Cup fill gradient (ceramic white with subtle shading)
        cup_grad = QLinearGradient(cx - cup_w/2, cup_top, cx + cup_w/2, cup_top)
        cup_grad.setColorAt(0.0, QColor(CUP_SHADOW))
        cup_grad.setColorAt(0.3, QColor(CUP_WHITE))
        cup_grad.setColorAt(0.7, QColor(CUP_WHITE))
        cup_grad.setColorAt(1.0, QColor(CUP_SHADOW))
        p.setPen(QPen(QColor(CUP_RIM), 1.5))
        p.setBrush(cup_grad)
        p.drawPath(cup_path)

        # Cup handle
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(CUP_SHADOW), 2.5, Qt.SolidLine, Qt.RoundCap))
        handle_path = QPainterPath()
        ht = cup_top + cup_h * 0.15
        hb = cup_top + cup_h * 0.75
        hr = cx + cup_w/2 + cup_w * 0.22
        handle_path.moveTo(cx + cup_w/2 - 1, ht)
        handle_path.cubicTo(hr, ht, hr, hb, cx + cup_w/2 - 1, hb)
        p.drawPath(handle_path)

        # Saucer line
        sy = cup_bot + cup_h * 0.10
        p.setPen(QPen(QColor(CUP_SHADOW), 2.0, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(cx - cup_w * 0.6, sy), QPointF(cx + cup_w * 0.6, sy))

        # --- 3. Draw coffee liquid filling the cup ---
        if self._progress > 0.01:
            # Liquid fills from bottom up
            # fill_fraction maps progress to how full the cup is visually
            fill_fraction = self._progress
            fill_top = cup_bot - (cup_h * 0.85) * fill_fraction  # leave rim
            # Clamp: never above cup_top + 10% (leave visible rim)
            fill_top = max(fill_top, cup_top + cup_h * 0.10)

            # Calculate cup width at fill_top (linear interpolation due to taper)
            frac_from_top = (fill_top - cup_top) / cup_h
            left_at_fill = (cx - cup_w/2) + taper * frac_from_top
            right_at_fill = (cx + cup_w/2) - taper * frac_from_top

            fill_path = QPainterPath()
            fill_path.moveTo(left_at_fill, fill_top)
            fill_path.lineTo(cx - cup_w/2 + taper, cup_bot)
            fill_path.quadTo(cx, cup_bot + cup_h * 0.1, cx + cup_w/2 - taper, cup_bot)
            fill_path.lineTo(right_at_fill, fill_top)
            fill_path.closeSubpath()

            # Coffee gradient: darker at bottom, slight crema glow at top
            coffee_grad = QLinearGradient(cx, cup_bot, cx, fill_top)
            coffee_grad.setColorAt(0.0, QColor(COFFEE_DARK))
            coffee_grad.setColorAt(0.7, QColor(COFFEE_MID))
            coffee_grad.setColorAt(0.95, QColor(COFFEE_LIGHT))
            coffee_grad.setColorAt(1.0, QColor(CREMA))
            p.setPen(Qt.NoPen)
            p.setBrush(coffee_grad)
            # Clip to cup interior
            p.save()
            p.setClipPath(cup_path)
            p.drawPath(fill_path)
            p.restore()

            # Crema line: a thin highlighted ellipse at the liquid surface
            if fill_fraction > 0.05:
                crema_y = fill_top + 1
                crema_w = right_at_fill - left_at_fill - 4
                p.setPen(Qt.NoPen)
                crema_c = QColor(CREMA_LIGHT)
                crema_c.setAlpha(int(120 * min(1.0, fill_fraction * 3)))
                p.setBrush(crema_c)
                p.drawEllipse(QPointF(cx, crema_y), crema_w / 2, 3)

        # --- 4. Draw pouring stream ---
        if 0.02 < self._progress < 0.98:
            import math
            # Stream from spout to liquid surface (or cup rim if cup is empty)
            stream_top = spout_y
            stream_bot = fill_top if self._progress > 0.01 else cup_top + cup_h * 0.15
            stream_width = 3.5
            # Slight wobble
            wobble = math.sin(self._frame * 0.15) * 1.2
            stream_c = QColor(COFFEE_DARK)
            stream_c.setAlpha(200)
            p.setPen(Qt.NoPen)
            p.setBrush(stream_c)
            p.drawRect(QRectF(
                spout_x - stream_width/2 + wobble,
                stream_top,
                stream_width,
                stream_bot - stream_top
            ))
            # Splash droplets at impact point
            for i in range(3):
                dx = math.sin(self._frame * 0.2 + i * 2.1) * 8
                dy = math.cos(self._frame * 0.25 + i * 1.7) * 4
                drop_c = QColor(COFFEE_MID)
                drop_c.setAlpha(100)
                p.setBrush(drop_c)
                p.drawEllipse(QPointF(spout_x + dx, stream_bot + dy), 1.5, 1.5)

        # --- 5. Draw steam ---
        import math
        for sp in self._steam_particles:
            alpha = 1.0 - (sp['age'] / sp['max_age'])  # fade out as age increases
            alpha *= min(1.0, self._progress * 4)       # less visible when cup is nearly empty
            if alpha < 0.02:
                continue
            steam_c = QColor(STEAM_COLOR)
            steam_c.setAlpha(int(alpha * 60))
            x = cx + sp['x_base'] * cup_w + math.sin(sp['phase'] + sp['age'] * 4) * sp['amplitude']
            y = (fill_top if self._progress > 0.01 else cup_top) - sp['y']
            radius = 3 + sp['age'] * 8  # grows as it rises
            p.setPen(Qt.NoPen)
            p.setBrush(steam_c)
            p.drawEllipse(QPointF(x, y), radius, radius)

        # --- 6. Volume text below saucer ---
        dispensed = int(self._volume_ml * self._progress)
        text = f"{dispensed} / {self._volume_ml} ml"
        p.setPen(QColor(GOLD_LIGHT))
        font = QFont()
        font.setPointSize(11)
        font.setWeight(QFont.DemiBold)
        p.setFont(font)
        text_rect = QRectF(0, sy + 12, w, 24)
        p.drawText(text_rect, Qt.AlignCenter, text)

        # --- 7. Percentage in the progress ring ---
        pct = f"{int(self._progress * 100)}%"
        p.setPen(QColor(GOLD))
        font.setPointSize(9)
        font.setWeight(QFont.Normal)
        p.setFont(font)
        # Place at top of the ring
        p.drawText(QRectF(ring_cx - 20, ring_cy - ring_r - 18, 40, 16),
                   Qt.AlignCenter, pct)

        p.end()


INTEGRATION WITH ProductCard:
    The ProductCard gets a QStackedWidget internally:
      - Page 0: normal controls (icon, strength, volume, temp, brew button) — existing layout
      - Page 1: BrewingAnimationWidget

    When set_brewing(True) is called, switch to page 1 and call widget.start().
    When the animation finishes (or machine reports brew complete), switch back to page 0.

    Modified ProductCard.__init__:
        # Wrap existing layout in a widget for stacking
        self._controls_page = QWidget()
        # ... (move existing layout into self._controls_page)

        self._brew_anim = BrewingAnimationWidget(
            self._product.volume_default, self._product.icon_style
        )
        self._brew_anim.finished.connect(self._on_animation_done)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._controls_page)
        self._stack.addWidget(self._brew_anim)

        # Main card layout just has the stack
        card_layout = QVBoxLayout(self)
        card_layout.addWidget(self._stack)

    Modified ProductCard.set_brewing(active):
        if active:
            vol = self._snap_volume(self._slider.value())
            self._brew_anim._volume_ml = vol  # update volume for this brew
            self._stack.setCurrentIndex(1)
            self._brew_anim.start()
        else:
            self._brew_anim.stop()
            self._stack.setCurrentIndex(0)
            self._brew_btn.setText("BREW")
            self._brew_btn.setEnabled(True)

    Modified ProductCard._on_animation_done():
        self._stack.setCurrentIndex(0)
        self._brew_btn.setText("BREW")
        self._brew_btn.setEnabled(True)
"""


# ============================================================================
# 2. CONNECTION ANIMATION (P1 — Should Have)
# ============================================================================
"""
2A. SCANNING — Pulsing BLE Radio Waves
---------------------------------------

CLASS: ScanningAnimation(QWidget)
    Renders concentric arc waves emanating from a central BLE icon,
    pulsing outward like radar/sonar.

    __init__(self, parent=None):
        self.setFixedSize(200, 200)
        self._frame = 0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self._waves = [0.0, 0.33, 0.66]  # 3 waves at different phases (0.0-1.0)

    def start(self): self._timer.start()
    def stop(self): self._timer.stop()

    def _tick(self):
        self._frame += 1
        for i in range(len(self._waves)):
            self._waves[i] += 0.012  # speed
            if self._waves[i] > 1.0:
                self._waves[i] -= 1.0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = 100, 100

        # Central dot (BLE icon stand-in)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(GOLD))
        p.drawEllipse(QPointF(cx, cy), 8, 8)

        # Radio waves: arcs at increasing radii
        for wave_phase in self._waves:
            radius = 20 + wave_phase * 75  # 20px to 95px
            alpha = int(200 * (1.0 - wave_phase))  # fade out as they expand
            pen = QPen(QColor(GOLD))
            pen_color = QColor(GOLD)
            pen_color.setAlpha(alpha)
            pen = QPen(pen_color, 2.0, Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            # Draw a ~120-degree arc on each side (bilateral, like BLE icon)
            arc_rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
            p.drawArc(arc_rect, 50 * 16, 80 * 16)    # right side arc
            p.drawArc(arc_rect, 230 * 16, 80 * 16)   # left side arc
        p.end()

INTEGRATION:
    In ConnectionScreen.__init__, create self._scan_anim = ScanningAnimation().
    Place it centered above the device list area.
    In set_scanning(True): self._scan_anim.show(); self._scan_anim.start()
    In set_scanning(False): self._scan_anim.stop(); self._scan_anim.hide()


2B. CONNECTING — Animated Progress Ring
----------------------------------------

CLASS: ConnectingRing(QWidget)
    An indeterminate spinning arc, similar to a loading spinner.

    __init__(self, parent=None):
        self.setFixedSize(60, 60)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    def start(self): self._angle = 0; self._timer.start()
    def stop(self): self._timer.stop()

    def _tick(self):
        self._angle = (self._angle + 5) % 360
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # Background ring
        p.setPen(QPen(QColor(BORDER), 3))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(5, 5, 50, 50)
        # Spinning arc (90 degrees of gold)
        p.setPen(QPen(QColor(GOLD), 3, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(5, 5, 50, 50, self._angle * 16, 90 * 16)
        p.end()

INTEGRATION:
    In ConnectionScreen, add a ConnectingRing next to the status label.
    show_connecting(): show the ring and start it.
    On connect_ok or connect_fail: stop and hide it.


2C. CONNECTED — Breathing Glow on StatusLED
---------------------------------------------

Modify the existing StatusLED class to add a subtle pulsing glow when connected.

    class StatusLED(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._color = QColor(TEXT_DIM)
            self._glow_alpha = 0.0
            self._glow_direction = 1  # 1 = brightening, -1 = dimming
            self._glow_timer = QTimer(self)
            self._glow_timer.setInterval(50)  # 20 fps for subtle effect
            self._glow_timer.timeout.connect(self._tick_glow)
            self.setFixedSize(18, 18)  # slightly larger to accommodate glow

        def set_connected(self):
            self._color = QColor(GREEN)
            self._glow_timer.start()
            self.update()

        def set_disconnected(self):
            self._color = QColor(TEXT_DIM)
            self._glow_timer.stop()
            self._glow_alpha = 0.0
            self.update()

        def _tick_glow(self):
            self._glow_alpha += self._glow_direction * 0.03
            if self._glow_alpha >= 1.0:
                self._glow_alpha = 1.0
                self._glow_direction = -1
            elif self._glow_alpha <= 0.3:
                self._glow_alpha = 0.3
                self._glow_direction = 1
            self.update()

        def paintEvent(self, _):
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            cx, cy = self.width()/2, self.height()/2
            r = 5

            # Outer glow (only when timer is active = connected)
            if self._glow_timer.isActive():
                glow_r = r + 4
                glow_c = QColor(self._color)
                glow_c.setAlpha(int(self._glow_alpha * 80))
                glow_grad = QRadialGradient(cx, cy, glow_r)
                glow_grad.setColorAt(0, glow_c)
                glow_c_outer = QColor(self._color)
                glow_c_outer.setAlpha(0)
                glow_grad.setColorAt(1, glow_c_outer)
                p.setPen(Qt.NoPen)
                p.setBrush(glow_grad)
                p.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

            # Core dot
            p.setPen(Qt.NoPen)
            grad = QRadialGradient(cx, cy, r)
            grad.setColorAt(0, self._color)
            fade = QColor(self._color)
            fade.setAlpha(0)
            grad.setColorAt(1, fade)
            p.setBrush(grad)
            p.drawEllipse(QPointF(cx, cy), r, r)
            p.end()
"""


# ============================================================================
# 3. CARD HOVER EFFECTS (P1 — Should Have)
# ============================================================================
"""
APPROACH:
    Use QPropertyAnimation to animate a custom "_hover_scale" property and
    a "_hover_glow" property. Override enterEvent/leaveEvent on ProductCard.

    PyQt5 does not support CSS transform:scale, so we use a combination of:
    (a) QGraphicsOpacityEffect -> replaced with a custom paintEvent overlay for the glow
    (b) A QGraphicsScale transform is NOT available on QWidget directly.

    PRACTICAL APPROACH (no QGraphicsView needed):
    Instead of actual scaling (complex in QWidgets), use a visual illusion:
      - On hover: increase shadow blur/offset, change border to gold glow, slight upward shift via margin
      - Animate these with QPropertyAnimation on custom properties

    Modified ProductCard:

    def __init__(self, ...):
        ...existing code...
        self._hover_offset = 0     # animated 0 -> 4 pixels upward shift
        self._hover_glow = 0.0     # animated 0.0 -> 1.0 for border glow intensity
        self._shadow = card_shadow()
        self.setGraphicsEffect(self._shadow)

        # Hover offset animation
        self._anim_offset = QPropertyAnimation(self, b"hover_offset")
        self._anim_offset.setDuration(200)
        self._anim_offset.setEasingCurve(QEasingCurve.OutCubic)

        # Hover glow animation
        self._anim_glow = QPropertyAnimation(self, b"hover_glow")
        self._anim_glow.setDuration(200)
        self._anim_glow.setEasingCurve(QEasingCurve.OutCubic)

    # Register custom properties using pyqtProperty:
    from PyQt5.QtCore import pyqtProperty

    def _get_hover_offset(self):
        return self._hover_offset_val

    def _set_hover_offset(self, val):
        self._hover_offset_val = val
        # Update top margin to simulate upward lift
        self.setContentsMargins(0, -int(val), 0, int(val))
        # Update shadow to appear deeper
        self._shadow.setBlurRadius(32 + val * 4)
        self._shadow.setOffset(0, 4 + val)

    hover_offset = pyqtProperty(float, _get_hover_offset, _set_hover_offset)

    def _get_hover_glow(self):
        return self._hover_glow_val

    def _set_hover_glow(self, val):
        self._hover_glow_val = val
        # Interpolate border color from BORDER to GOLD based on val
        alpha = int(val * 255)
        self.setStyleSheet(f'''
            ProductCard {{
                background-color: {BG_CARD_HVR if val > 0.1 else BG_CARD};
                border: 1px solid rgba(200, 166, 98, {alpha});
                border-radius: 18px;
            }}
        ''')

    hover_glow = pyqtProperty(float, _get_hover_glow, _set_hover_glow)

    def enterEvent(self, event):
        self._anim_offset.stop()
        self._anim_offset.setStartValue(self._hover_offset_val)
        self._anim_offset.setEndValue(4.0)
        self._anim_offset.start()

        self._anim_glow.stop()
        self._anim_glow.setStartValue(self._hover_glow_val)
        self._anim_glow.setEndValue(1.0)
        self._anim_glow.start()

    def leaveEvent(self, event):
        self._anim_offset.stop()
        self._anim_offset.setStartValue(self._hover_offset_val)
        self._anim_offset.setEndValue(0.0)
        self._anim_offset.start()

        self._anim_glow.stop()
        self._anim_glow.setStartValue(self._hover_glow_val)
        self._anim_glow.setEndValue(0.0)
        self._anim_glow.start()

ADDITIONAL IMPORT NEEDED:
    from PyQt5.QtCore import pyqtProperty, QEasingCurve
    from PyQt5.QtWidgets import QPropertyAnimation  # actually in QtCore
    from PyQt5.QtCore import QPropertyAnimation

NOTE:
    QPropertyAnimation requires the target property to be a pyqtProperty
    on a QObject subclass. ProductCard inherits QFrame (which is QObject),
    so this works directly.
"""


# ============================================================================
# 4. STATUS BAR IMPROVEMENTS (P1 — Should Have)
# ============================================================================
"""
4A. ANIMATED ALERT TRANSITIONS
-------------------------------
    Alert pills should slide in from the right when they appear and slide
    out to the left when they disappear, rather than popping in/out.

    Modify AlertPill to support opacity+position animation:

    class AlertPill(QFrame):
        def __init__(self, text, severity="info", parent=None):
            super().__init__(parent)
            ...existing styling code...

            # Start invisible, will animate in
            self._opacity_effect = QGraphicsOpacityEffect(self)
            self._opacity_effect.setOpacity(0.0)
            self.setGraphicsEffect(self._opacity_effect)

        def animate_in(self):
            self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
            self._anim.setDuration(300)
            self._anim.setStartValue(0.0)
            self._anim.setEndValue(1.0)
            self._anim.setEasingCurve(QEasingCurve.OutCubic)
            self._anim.start()

        def animate_out(self, on_finished=None):
            self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
            self._anim.setDuration(200)
            self._anim.setStartValue(1.0)
            self._anim.setEndValue(0.0)
            self._anim.setEasingCurve(QEasingCurve.InCubic)
            if on_finished:
                self._anim.finished.connect(on_finished)
            self._anim.start()

    Modified DashboardScreen.update_alerts(alerts):
        # Animate out existing pills, then add new ones
        old_pills = list(self._alert_pills)
        self._alert_pills = []

        def _remove_and_add():
            for pill in old_pills:
                pill.deleteLater()
            # Add new pills
            if not alerts:
                pill = AlertPill("All clear", "success")
                self._alert_layout.insertWidget(2, pill)
                pill.animate_in()
                self._alert_pills.append(pill)
            else:
                for _, name, severity in alerts:
                    pill = AlertPill(name, severity)
                    self._alert_layout.insertWidget(
                        self._alert_layout.count() - 1, pill
                    )
                    pill.animate_in()
                    self._alert_pills.append(pill)

        if old_pills:
            # Animate out the last pill, chain the rest removal
            old_pills[-1].animate_out(on_finished=_remove_and_add)
        else:
            _remove_and_add()


4B. PULSING FOR CRITICAL ALERTS
---------------------------------
    For "error" severity pills, add a pulsing border animation:

    class AlertPill(QFrame):
        def __init__(self, text, severity="info", parent=None):
            ...
            if severity == "error":
                self._pulse_timer = QTimer(self)
                self._pulse_timer.setInterval(50)
                self._pulse_alpha = 255
                self._pulse_dir = -5
                self._pulse_timer.timeout.connect(self._pulse_tick)
                self._pulse_timer.start()

        def _pulse_tick(self):
            self._pulse_alpha += self._pulse_dir
            if self._pulse_alpha <= 100:
                self._pulse_dir = 5
            elif self._pulse_alpha >= 255:
                self._pulse_dir = -5
            fg_color = QColor(RED)
            fg_color.setAlpha(self._pulse_alpha)
            # Update border style with varying alpha
            self.setStyleSheet(f'''
                QFrame {{
                    background-color: #1a0808;
                    border: 1px solid rgba(216, 64, 64, {self._pulse_alpha});
                    border-radius: 12px;
                    padding: 4px 14px;
                }}
            ''')
"""


# ============================================================================
# 5. BREW CONFIRMATION DIALOG (P2 — Nice to Have)
# ============================================================================
"""
5A. COFFEE BEAN RAIN BACKGROUND
---------------------------------
    The BrewConfirmDialog gets a paintEvent that draws small coffee bean
    shapes drifting downward behind the dialog content.

    class BrewConfirmDialog(QDialog):
        def __init__(self, ...):
            ...existing code...
            self._beans = []
            self._init_beans()
            self._bean_timer = QTimer(self)
            self._bean_timer.setInterval(33)
            self._bean_timer.timeout.connect(self._tick_beans)
            self._bean_timer.start()

        def _init_beans(self):
            import random
            for _ in range(15):
                self._beans.append({
                    'x': random.uniform(0, 380),
                    'y': random.uniform(-260, 260),
                    'speed': random.uniform(0.3, 0.8),
                    'rotation': random.uniform(0, 360),
                    'rot_speed': random.uniform(-1, 1),
                    'size': random.uniform(6, 10),
                    'alpha': random.randint(15, 35),
                })

        def _tick_beans(self):
            import random
            for b in self._beans:
                b['y'] += b['speed']
                b['rotation'] += b['rot_speed']
                if b['y'] > 270:
                    b['y'] = -10
                    b['x'] = random.uniform(0, 380)
            self.update()

        def paintEvent(self, event):
            # Draw beans BEFORE the container paints its children
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            for b in self._beans:
                p.save()
                p.translate(b['x'], b['y'])
                p.rotate(b['rotation'])
                # Coffee bean shape: two overlapping ellipses with a center line
                bean_c = QColor(GOLD_DARK)
                bean_c.setAlpha(b['alpha'])
                p.setPen(Qt.NoPen)
                p.setBrush(bean_c)
                s = b['size']
                p.drawEllipse(QPointF(0, 0), s, s * 0.65)
                # Center crease
                line_c = QColor(BG)
                line_c.setAlpha(b['alpha'])
                p.setPen(QPen(line_c, 0.8))
                p.drawLine(QPointF(0, -s * 0.45), QPointF(0, s * 0.45))
                p.restore()
            p.end()
            # QDialog.paintEvent draws child widgets on top
            super().paintEvent(event)


5B. SMOOTH OPEN/CLOSE TRANSITIONS
-----------------------------------
    Animate the dialog's opacity from 0 to 1 on open:

    def showEvent(self, event):
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._open_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._open_anim.setDuration(200)
        self._open_anim.setStartValue(0.0)
        self._open_anim.setEndValue(1.0)
        self._open_anim.start()
        super().showEvent(event)

    To animate close, override reject()/accept() to animate out first:

    def _animated_close(self, result_method):
        self._close_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._close_anim.setDuration(150)
        self._close_anim.setStartValue(1.0)
        self._close_anim.setEndValue(0.0)
        self._close_anim.finished.connect(result_method)
        self._close_anim.start()

    def accept(self):
        self._animated_close(lambda: QDialog.accept(self))

    def reject(self):
        self._animated_close(lambda: QDialog.reject(self))
"""


# ============================================================================
# 6. MISSING UX FEATURES
# ============================================================================

# 6A. KEYBOARD SHORTCUTS (P1 — Should Have)
"""
Add to JuraApp.__init__:

    from PyQt5.QtWidgets import QShortcut
    from PyQt5.QtGui import QKeySequence

    # Product quick-select (only on dashboard)
    self._shortcut_1 = QShortcut(QKeySequence("1"), self)
    self._shortcut_1.activated.connect(lambda: self._quick_brew(0))
    self._shortcut_2 = QShortcut(QKeySequence("2"), self)
    self._shortcut_2.activated.connect(lambda: self._quick_brew(1))
    self._shortcut_3 = QShortcut(QKeySequence("3"), self)
    self._shortcut_3.activated.connect(lambda: self._quick_brew(2))

    # Scan shortcut on connection screen
    self._shortcut_scan = QShortcut(QKeySequence("F5"), self)
    self._shortcut_scan.activated.connect(self._on_scan)

    # Disconnect
    self._shortcut_disconnect = QShortcut(QKeySequence("Ctrl+D"), self)
    self._shortcut_disconnect.activated.connect(self._on_disconnect)

def _quick_brew(self, card_index):
    if self._stack.currentWidget() != self._dashboard:
        return
    if card_index < len(self._dashboard._cards):
        card = self._dashboard._cards[card_index]
        card._on_brew()

Add a subtle hint in the card UI — a small "(1)" / "(2)" / "(3)" label
at the top-right corner of each card:

    In ProductCard.__init__, after creating the name label:
        shortcut_hint = QLabel(f"({card_index + 1})")
        shortcut_hint.setFont(make_font(9))
        shortcut_hint.setStyleSheet(
            f"color: {TEXT_DIM}; background: transparent; border: none;"
        )
        # Position absolutely at top-right
        shortcut_hint.setParent(self)
        shortcut_hint.move(self.width() - 30, 10)

    Pass card_index as an argument to ProductCard.__init__.
"""


# 6B. SOUND FEEDBACK (P2 — Nice to Have)
"""
Use QSound (PyQt5.QtMultimedia) or subprocess to play .wav files.
Since we want zero external dependencies, use the system "bell" or
generate simple tones with QAudioOutput.

SIMPLER APPROACH — use os.system for minimal click sounds:

    import subprocess

    def _play_sound(sound_name):
        # Use system sounds if available, otherwise skip silently
        sounds = {
            "click": "/usr/share/sounds/freedesktop/stereo/button-pressed.oga",
            "brew_start": "/usr/share/sounds/freedesktop/stereo/service-login.oga",
            "brew_done": "/usr/share/sounds/freedesktop/stereo/complete.oga",
            "error": "/usr/share/sounds/freedesktop/stereo/dialog-error.oga",
        }
        path = sounds.get(sound_name)
        if path and os.path.exists(path):
            # Fire and forget — don't block the UI
            subprocess.Popen(
                ["paplay", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

INTEGRATION:
    - BrewConfirmDialog.accept() -> _play_sound("brew_start")
    - BrewingAnimationWidget.stop() -> _play_sound("brew_done")
    - on_brew_error() -> _play_sound("error")
    - Any button click -> _play_sound("click")

    Add a settings toggle to mute sounds:
        self._sounds_enabled = True   # in JuraApp
"""


# 6C. RECENT BREWS HISTORY (P2 — Nice to Have)
"""
Store recent brews in a simple JSON file and display them in a collapsible
section below the product cards.

DATA MODEL:
    import json
    from datetime import datetime

    HISTORY_FILE = os.path.join(APP_DIR, ".brew_history.json")

    @dataclass
    class BrewRecord:
        product_name: str
        strength: int
        volume_ml: int
        temp: str
        timestamp: str  # ISO format

    def save_brew(record: BrewRecord):
        history = load_history()
        history.insert(0, vars(record))
        history = history[:20]  # keep last 20
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)

    def load_history() -> list:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE) as f:
                return json.load(f)
        return []

UI:
    class RecentBrewsPanel(QFrame):
        repeat_brew = pyqtSignal(str, int, int, str)  # name, strength, vol, temp

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setStyleSheet(f'''
                QFrame {{
                    background-color: {BG_ELEVATED};
                    border: 1px solid {BORDER};
                    border-radius: 14px;
                }}
            ''')
            layout = QVBoxLayout(self)
            layout.setContentsMargins(20, 16, 20, 16)

            header = QLabel("RECENT BREWS")
            header.setFont(make_font(9, QFont.DemiBold, spacing=2))
            header.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; border: none;")
            layout.addWidget(header)

            self._list_layout = QVBoxLayout()
            self._list_layout.setSpacing(6)
            layout.addLayout(self._list_layout)

        def refresh(self):
            # Clear and repopulate from history file
            while self._list_layout.count():
                item = self._list_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            history = load_history()
            for entry in history[:5]:  # show last 5
                row = QFrame()
                row.setStyleSheet(f'''
                    QFrame {{
                        background: transparent;
                        border: none;
                        border-bottom: 1px solid {BORDER};
                        padding: 4px 0;
                    }}
                ''')
                row_lay = QHBoxLayout(row)
                row_lay.setContentsMargins(0, 4, 0, 4)

                info = QLabel(
                    f"{entry['product_name']}  •  "
                    f"str {entry['strength']}  •  "
                    f"{entry['volume_ml']}ml  •  "
                    f"{entry['temp']}"
                )
                info.setFont(make_font(11))
                info.setStyleSheet(f"color: {TEXT}; border: none; background: transparent;")
                row_lay.addWidget(info, stretch=1)

                ts = QLabel(entry['timestamp'][:16])  # trim seconds
                ts.setFont(make_font(9))
                ts.setStyleSheet(f"color: {TEXT_DIM}; border: none; background: transparent;")
                row_lay.addWidget(ts)

                repeat_btn = QPushButton("Repeat")
                repeat_btn.setFixedSize(60, 26)
                repeat_btn.setCursor(Qt.PointingHandCursor)
                repeat_btn.setStyleSheet(f'''
                    QPushButton {{
                        background: transparent;
                        color: {GOLD};
                        border: 1px solid {GOLD_DIMMED};
                        border-radius: 6px;
                        font-size: 10px;
                    }}
                    QPushButton:hover {{
                        background: {GOLD};
                        color: {TEXT_DARK};
                    }}
                ''')
                e = entry  # capture
                repeat_btn.clicked.connect(
                    lambda _, e=e: self.repeat_brew.emit(
                        e['product_name'], e['strength'],
                        e['volume_ml'], e['temp']
                    )
                )
                row_lay.addWidget(repeat_btn)
                self._list_layout.addWidget(row)

INTEGRATION:
    Place below the product cards in the dashboard scroll area.
    On brew_started, call save_brew() and panel.refresh().
"""


# 6D. FAVORITE PRESETS (P2 — Nice to Have)
"""
Allow users to save and recall custom strength/volume/temp combos per product.

DATA:
    PRESETS_FILE = os.path.join(APP_DIR, ".brew_presets.json")
    # Format: {"Ristretto": [{"name": "My Bold", "strength": 7, "volume": 30, "temp": 2}, ...], ...}

UI:
    Add a small star/bookmark button to each ProductCard, next to the BREW button.
    Clicking it saves the current settings as a preset (prompt for name via QInputDialog).

    Add a small dropdown/expandable area above the controls showing saved presets
    as clickable chips:

    class PresetChip(QPushButton):
        def __init__(self, name, parent=None):
            super().__init__(name, parent)
            self.setFixedHeight(26)
            self.setCursor(Qt.PointingHandCursor)
            self.setStyleSheet(f'''
                QPushButton {{
                    background: transparent;
                    color: {GOLD_LIGHT};
                    border: 1px solid {GOLD_DIMMED};
                    border-radius: 13px;
                    padding: 0 12px;
                    font-size: 10px;
                }}
                QPushButton:hover {{
                    background: {GOLD_DIMMED};
                    color: {TEXT};
                }}
            ''')

    In ProductCard, add a QHBoxLayout for preset chips between the product name
    and the strength selector. When a chip is clicked, update strength/volume/temp
    to the preset values.
"""


# 6E. DARK/LIGHT THEME TOGGLE (P2 — Nice to Have)
"""
Define a second theme palette:

LIGHT THEME COLORS:
    L_BG           = "#f5f2ed"
    L_BG_ELEVATED  = "#ffffff"
    L_BG_CARD      = "#ffffff"
    L_BG_CARD_HVR  = "#faf8f5"
    L_BORDER       = "#e0dcd5"
    L_GOLD         = "#8b6914"
    L_GOLD_LIGHT   = "#a67d1a"
    L_GOLD_DARK    = "#6b5010"
    L_GOLD_DIMMED  = "#c4a860"
    L_TEXT         = "#1a1a2e"
    L_TEXT_DIM     = "#8888a0"
    L_TEXT_DARK    = "#ffffff"

IMPLEMENTATION:
    Store current theme in a module-level dict or class:

    class Theme:
        _current = "dark"
        _palettes = {
            "dark": { "BG": "#0b0b13", ... },
            "light": { "BG": "#f5f2ed", ... },
        }

        @classmethod
        def get(cls, key):
            return cls._palettes[cls._current][key]

        @classmethod
        def toggle(cls):
            cls._current = "light" if cls._current == "dark" else "dark"

    This requires refactoring all color references from constants to Theme.get("BG").
    Since this is a large refactor, priority is P2.

    Add a toggle button in the dashboard header (a moon/sun icon using QPainter):

    theme_btn = QPushButton()
    theme_btn.setFixedSize(32, 32)
    theme_btn.setToolTip("Toggle theme")
    theme_btn.clicked.connect(self._toggle_theme)

    def _toggle_theme(self):
        Theme.toggle()
        # Re-apply stylesheet
        self.setStyleSheet(build_stylesheet())
        # Force repaint of all custom-painted widgets
        for card in self._dashboard._cards:
            card.update()
"""


# 6F. SYSTEM TRAY INTEGRATION (P2 — Nice to Have)
"""
IMPLEMENTATION:

    from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction

    In JuraApp.__init__:

        # System tray
        self._tray = QSystemTrayIcon(self)
        # Create a simple icon using QPixmap + QPainter (no external file needed)
        tray_pixmap = QPixmap(32, 32)
        tray_pixmap.fill(Qt.transparent)
        tp = QPainter(tray_pixmap)
        tp.setRenderHint(QPainter.Antialiasing)
        tp.setPen(Qt.NoPen)
        tp.setBrush(QColor(GOLD))
        tp.drawEllipse(4, 4, 24, 24)
        # Draw a "J" in the center
        tp.setPen(QPen(QColor(TEXT_DARK), 2))
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        tp.setFont(font)
        tp.drawText(QRectF(4, 4, 24, 24), Qt.AlignCenter, "J")
        tp.end()
        self._tray.setIcon(QIcon(tray_pixmap))

        # Tray menu
        tray_menu = QMenu()
        tray_menu.setStyleSheet(f'''
            QMenu {{
                background-color: {BG_CARD};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {GOLD_DIMMED};
            }}
        ''')

        # Quick-brew actions
        for product in E4_PRODUCTS:
            action = QAction(
                f"Brew {product.name} ({product.volume_default}ml)", self
            )
            action.triggered.connect(
                lambda _, p=product: self._tray_brew(p)
            )
            tray_menu.addAction(action)

        tray_menu.addSeparator()
        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self._show_from_tray)
        tray_menu.addAction(show_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        tray_menu.addAction(quit_action)

        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # single click
            self._show_from_tray()

    def _show_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _tray_brew(self, product):
        if not self._ble._connected:
            self._tray.showMessage(
                "JURA", "Not connected to machine",
                QSystemTrayIcon.Warning, 3000
            )
            return
        self._on_brew(
            product.code, product.strength_default,
            product.volume_default, product.volume_step,
            product.temp_default,
        )
        self._tray.showMessage(
            "JURA", f"Brewing {product.name}...",
            QSystemTrayIcon.Information, 3000
        )

    # Override close to minimize to tray instead
    def closeEvent(self, event):
        if self._tray.isVisible():
            self.hide()
            self._tray.showMessage(
                "JURA", "Running in system tray",
                QSystemTrayIcon.Information, 2000
            )
            event.ignore()
        else:
            self._ble.disconnect_machine()
            self._ble.shutdown()
            event.accept()

    # Add a real quit (Ctrl+Q or from tray menu)
    self._shortcut_quit = QShortcut(QKeySequence("Ctrl+Q"), self)
    self._shortcut_quit.activated.connect(self._real_quit)

    def _real_quit(self):
        self._tray.hide()
        self._ble.disconnect_machine()
        self._ble.shutdown()
        QApplication.quit()

IMPORT NEEDED:
    from PyQt5.QtGui import QPixmap
    from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
"""


# ============================================================================
# 7. RESPONSIVE LAYOUT (P1 — Should Have)
# ============================================================================
"""
Replace the fixed QHBoxLayout for cards with a custom FlowLayout that
reflows cards based on available width.

CLASS: FlowLayout(QLayout)
    A flow/wrap layout that arranges children left-to-right, wrapping to the
    next row when horizontal space is exhausted. This is a well-known PyQt5
    pattern (Qt documentation includes a FlowLayout example).

    class FlowLayout(QLayout):
        def __init__(self, parent=None, margin=0, spacing=-1):
            super().__init__(parent)
            self.setContentsMargins(margin, margin, margin, margin)
            self._items = []
            self._spacing = spacing if spacing >= 0 else 28

        def addItem(self, item):
            self._items.append(item)

        def count(self):
            return len(self._items)

        def itemAt(self, index):
            if 0 <= index < len(self._items):
                return self._items[index]
            return None

        def takeAt(self, index):
            if 0 <= index < len(self._items):
                return self._items.pop(index)
            return None

        def expandingDirections(self):
            return Qt.Orientations(0)

        def hasHeightForWidth(self):
            return True

        def heightForWidth(self, width):
            return self._do_layout(QRect(0, 0, width, 0), test_only=True)

        def setGeometry(self, rect):
            super().setGeometry(rect)
            self._do_layout(rect, test_only=False)

        def sizeHint(self):
            return self.minimumSize()

        def minimumSize(self):
            size = QSize()
            for item in self._items:
                size = size.expandedTo(item.minimumSize())
            m = self.contentsMargins()
            size += QSize(m.left() + m.right(), m.top() + m.bottom())
            return size

        def _do_layout(self, rect, test_only):
            m = self.contentsMargins()
            effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
            x = effective.x()
            y = effective.y()
            row_height = 0

            # Center each row: first pass to find row contents, second to position
            rows = []  # list of (items_in_row, row_width, row_height)
            current_row = []
            current_row_width = 0

            for item in self._items:
                item_size = item.sizeHint()
                next_x = x + current_row_width + (self._spacing if current_row else 0) + item_size.width()
                if current_row and next_x > effective.right() + 1:
                    rows.append((current_row, current_row_width, row_height))
                    current_row = [item]
                    current_row_width = item_size.width()
                    row_height = item_size.height()
                else:
                    if current_row:
                        current_row_width += self._spacing
                    current_row_width += item_size.width()
                    row_height = max(row_height, item_size.height())
                    current_row.append(item)
            if current_row:
                rows.append((current_row, current_row_width, row_height))

            if test_only:
                total_h = sum(rh for _, _, rh in rows)
                total_h += self._spacing * max(0, len(rows) - 1)
                return total_h + m.top() + m.bottom()

            current_y = effective.y()
            for row_items, row_width, rh in rows:
                # Center the row horizontally
                row_x = effective.x() + (effective.width() - row_width) // 2
                for item in row_items:
                    item_size = item.sizeHint()
                    item.setGeometry(QRect(
                        QPoint(row_x, current_y), item_size
                    ))
                    row_x += item_size.width() + self._spacing
                current_y += rh + self._spacing

            return current_y - effective.y()

INTEGRATION:
    In DashboardScreen.__init__, replace:
        self._cards_layout = QHBoxLayout()
    with:
        self._cards_layout = FlowLayout(spacing=28)

    Remove the setAlignment(Qt.AlignCenter) call (FlowLayout handles centering).
    The scroll area's widgetResizable=True already handles height recalculation.

    Remove setFixedWidth(240) from ProductCard and replace with:
        self.setMinimumWidth(220)
        self.setMaximumWidth(260)
        # Let the card find its natural width
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

IMPORT NEEDED:
    from PyQt5.QtCore import QRect, QPoint
    (QRect and QPoint are likely already available; verify.)
"""


# ============================================================================
# PRIORITY SUMMARY
# ============================================================================
"""
P0 (Must Have):
  1. Brewing Animation (BrewingAnimationWidget) — the core premium experience

P1 (Should Have):
  2. Connection Animation (ScanningAnimation, ConnectingRing, StatusLED breathing)
  3. Card Hover Effects (QPropertyAnimation lift + glow)
  4. Status Bar Improvements (animated pill transitions, pulsing critical alerts)
  6A. Keyboard Shortcuts (1/2/3 for products, F5 scan, Ctrl+D disconnect)
  7. Responsive Layout (FlowLayout for card grid)

P2 (Nice to Have):
  5. Brew Confirmation Dialog (bean rain, fade transitions)
  6B. Sound Feedback (system sounds via paplay)
  6C. Recent Brews History (JSON file + panel)
  6D. Favorite Presets (save/load custom combos)
  6E. Dark/Light Theme Toggle (requires Theme class refactor)
  6F. System Tray Integration (minimize to tray, quick-brew menu)
"""


# ============================================================================
# IMPLEMENTATION ORDER (recommended)
# ============================================================================
"""
Phase 1 — Core Experience:
  1. BrewingAnimationWidget + ProductCard QStackedWidget integration
  2. Keyboard shortcuts (quick win, 20 lines of code)
  3. StatusLED breathing glow (small change, immediate visual payoff)

Phase 2 — Polish:
  4. Card hover effects (QPropertyAnimation)
  5. FlowLayout responsive grid
  6. Connection screen animations (ScanningAnimation, ConnectingRing)
  7. Alert pill transitions

Phase 3 — Features:
  8. System tray integration
  9. Recent brews history
  10. Brew confirmation dialog bean rain + fade
  11. Sound feedback
  12. Favorite presets

Phase 4 — Theme:
  13. Theme class refactor + dark/light toggle

Each phase is independently shippable. Phase 1 alone dramatically
improves the perceived quality of the application.
"""


# ============================================================================
# FILES TO MODIFY
# ============================================================================
"""
PRIMARY:
  /home/ovidiu/jura-desktop/jura_app.py
    - Add BrewingAnimationWidget class
    - Add ScanningAnimation class
    - Add ConnectingRing class
    - Modify StatusLED (breathing glow)
    - Modify ProductCard (QStackedWidget, hover animations, preset chips)
    - Modify AlertPill (opacity animation, pulse for errors)
    - Modify BrewConfirmDialog (bean rain, fade transitions)
    - Modify DashboardScreen (FlowLayout, recent brews panel, toast animation)
    - Modify ConnectionScreen (scanning/connecting animations)
    - Modify JuraApp (shortcuts, tray, theme toggle, sound feedback)

NEW (optional, for cleanliness):
  /home/ovidiu/jura-desktop/flow_layout.py     — FlowLayout class
  /home/ovidiu/jura-desktop/brew_animation.py  — BrewingAnimationWidget class
  /home/ovidiu/jura-desktop/brew_history.py    — BrewRecord, save/load, RecentBrewsPanel

  Or keep everything in jura_app.py if you prefer a single-file app.

NO EXTERNAL DEPENDENCIES REQUIRED:
  Everything uses PyQt5 built-ins: QPainter, QTimer, QPropertyAnimation,
  QGraphicsOpacityEffect, QSystemTrayIcon, QSound/subprocess.
"""
