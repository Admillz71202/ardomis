"""oled_face.py — Expressive OLED face for Ardomis.

Hardware target : SSD1306-compatible 128×64 OLED, I2C (port=1, address=0x3C).
Install on Pi   : pip install luma.oled pillow

If luma.oled is not installed (Windows dev box, headless Pi) every call is a
silent no-op via _NullFace.  The render thread is never started in that case.

Expression map (driven by EmotionState):
  sleeping  — presence mode, not speaking  → closed eyes + ZZZ animation
  happy     — mood > 68                    → happy curved eyes + big smile
  excited   — excitement > 74 or mood > 82 → wide eyes + grin
  angry     — irritation > 58             → angled brows + grimace
  worried   — mood < 28 or patience low   → tilted brows + frown + sweat drop
  sneaky    — high sass + playfulness      → squinting left eye + smirk
  bored     — boredom > 72                → half-closed eyes + flat mouth + dots
  sad       — mood < 38                   → droopy eyes + frown
  neutral   — everything else             → open eyes + slight smile

Speaking    — mouth animates through open/close cycle regardless of expression.
Eye-roll    — triggered when a presence chime goes unanswered; pupils roll up
              then to the side, eyes close back to sleep.
"""

from __future__ import annotations

import threading
import time

# ── Hardware imports — optional ──────────────────────────────────────────────
try:
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306
    from PIL import Image, ImageDraw
    _LUMA_OK = True
except ImportError:
    _LUMA_OK = False

# ── Display geometry (pixels) ─────────────────────────────────────────────────
W, H = 128, 64

L_EYE    = (36, 27)    # left eye center
R_EYE    = (92, 27)    # right eye center
EYE_R    = 9           # outer eye radius
PUPIL_R  = 4           # filled pupil radius
BW_Y     = 14          # eyebrow Y

MOUTH_CX = 64
MOUTH_CY = 48
MOUTH_HW = 14          # mouth half-width

FPS       = 15
_FRAME_DT = 1.0 / FPS

# Mouth vertical opening per speak-frame (px). 0 = closed, peaks at frame 4.
_SPEAK_H = [0, 3, 6, 10, 13, 10, 6, 2]

_ER_FRAMES = 28        # total eye-roll animation frames


# ─────────────────────────────────────────────────────────────────────────────
# Expression selection
# ─────────────────────────────────────────────────────────────────────────────

def _expression(mode: str, speaking: bool, state) -> str:
    """Map FSM mode + emotion state → expression name."""
    if mode == "presence" and not speaking:
        return "sleeping"
    if state is None:
        return "neutral"

    # Reactive emotions — highest priority
    if state.irritation > 58 or (state.annoyance > 70 and state.irritation > 30):
        return "angry"
    if state.mood < 28 or (state.patience < 25 and state.annoyance > 65):
        return "worried"

    # High-energy positive
    if state.excitement > 74 or (state.mood > 82 and state.energy > 68):
        return "excited"

    # Sass + playfulness → sneaky
    if state.sass > 75 and state.playfulness > 68:
        return "sneaky"

    # Idle emotions
    if state.boredom > 72:
        return "bored"
    if state.mood < 38:
        return "sad"
    if state.mood > 68:
        return "happy"

    return "neutral"


# ─────────────────────────────────────────────────────────────────────────────
# Eye drawing
# ─────────────────────────────────────────────────────────────────────────────

def _open_eye(draw, cx, cy):
    """Standard open eye: outer ring + filled pupil."""
    draw.ellipse([cx - EYE_R, cy - EYE_R, cx + EYE_R, cy + EYE_R],
                 outline=255, width=2)
    draw.ellipse([cx - PUPIL_R, cy - PUPIL_R, cx + PUPIL_R, cy + PUPIL_R],
                 fill=255)


def _eye(draw, cx: int, cy: int, expr: str, side: str) -> None:
    r, pr = EYE_R, PUPIL_R

    if expr == "sleeping":
        draw.line([(cx - r, cy), (cx + r, cy)], fill=255, width=2)

    elif expr == "bored":
        # Upper arc only — droopy lid look
        draw.arc([cx - r, cy - r // 2, cx + r, cy + r + 4],
                 200, 340, fill=255, width=2)
        draw.ellipse([cx - pr // 2, cy, cx + pr // 2, cy + pr], fill=255)

    elif expr == "happy":
        # Upward "^" arc
        draw.arc([cx - r, cy - r, cx + r, cy + r], 200, 340, fill=255, width=2)

    elif expr == "sad":
        # Downward arc
        draw.arc([cx - r, cy - r, cx + r, cy + r], 20, 160, fill=255, width=2)

    elif expr == "excited":
        # Larger ring + bigger pupil
        draw.ellipse([cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1],
                     outline=255, width=2)
        draw.ellipse([cx - pr - 1, cy - pr - 1, cx + pr + 1, cy + pr + 1],
                     fill=255)

    elif expr == "worried":
        _open_eye(draw, cx, cy)
        # Inner end of brow angled DOWN → worried "V" shape
        if side == "left":
            draw.line([(cx - r + 1, BW_Y + 4), (cx + r // 2, BW_Y)],
                      fill=255, width=2)
        else:
            draw.line([(cx - r // 2, BW_Y), (cx + r - 1, BW_Y + 4)],
                      fill=255, width=2)

    elif expr == "angry":
        _open_eye(draw, cx, cy)
        # Inner end of brow angled UP (toward nose) → "angry V" shape
        if side == "left":
            draw.line([(cx - r, BW_Y + 4), (cx + r, BW_Y - 2)],
                      fill=255, width=3)
        else:
            draw.line([(cx - r, BW_Y - 2), (cx + r, BW_Y + 4)],
                      fill=255, width=3)

    elif expr == "sneaky":
        if side == "left":
            # Squinting: lower half-arc
            draw.arc([cx - r, cy - r // 2, cx + r, cy + r + 2],
                     190, 350, fill=255, width=2)
        else:
            _open_eye(draw, cx, cy)

    else:
        # neutral / default
        _open_eye(draw, cx, cy)


# ─────────────────────────────────────────────────────────────────────────────
# Mouth drawing
# ─────────────────────────────────────────────────────────────────────────────

def _mouth(draw, expr: str, speak_frame: int, speaking: bool) -> None:
    cx, cy, hw = MOUTH_CX, MOUTH_CY, MOUTH_HW

    if speaking:
        oh = _SPEAK_H[speak_frame % len(_SPEAK_H)]
        if oh == 0:
            draw.line([(cx - hw, cy), (cx + hw, cy)], fill=255, width=2)
        else:
            # Oval mouth, top arc + bottom arc
            bbox = [cx - hw, cy - oh, cx + hw, cy + oh]
            draw.arc(bbox, 180, 0,   fill=255, width=2)
            draw.arc(bbox, 0,   180, fill=255, width=2)
        return

    if expr == "sleeping":
        draw.line([(cx - 8, cy), (cx + 8, cy)], fill=255, width=1)

    elif expr in ("happy", "excited"):
        draw.arc([cx - hw, cy - 10, cx + hw, cy + 6],  20, 160, fill=255, width=3)

    elif expr in ("sad", "worried"):
        draw.arc([cx - hw, cy - 4,  cx + hw, cy + 10], 200, 340, fill=255, width=2)

    elif expr == "angry":
        draw.arc([cx - hw + 2, cy - 3, cx + hw - 2, cy + 7], 210, 330, fill=255, width=2)

    elif expr == "sneaky":
        # Smirk: right side raised
        draw.line([(cx - hw // 2, cy + 3), (cx + hw // 2, cy - 3)], fill=255, width=2)

    elif expr == "bored":
        draw.line([(cx - hw // 2, cy), (cx + hw // 2, cy)], fill=255, width=2)

    else:
        # neutral slight smile
        draw.arc([cx - hw // 2, cy - 5, cx + hw // 2, cy + 4], 20, 160, fill=255, width=2)


# ─────────────────────────────────────────────────────────────────────────────
# Overlay elements
# ─────────────────────────────────────────────────────────────────────────────

def _zzz(draw, phase: float) -> None:
    """Three floating Z's, upper-right corner. phase 0.0→1.0 drives upward drift."""
    for size, ox, oy in ((5, 0, 0), (7, 8, -7), (10, 18, -16)):
        y_off = int(-phase * 7)
        x = 100 + ox
        y = 10 + oy + y_off
        draw.line([(x, y),          (x + size, y)         ], fill=255, width=1)
        draw.line([(x + size, y),   (x, y + size)         ], fill=255, width=1)
        draw.line([(x, y + size),   (x + size, y + size)  ], fill=255, width=1)


def _sweat(draw) -> None:
    """Stress sweat drop next to left eye."""
    x, y = 18, 20
    draw.ellipse([x - 2, y + 2, x + 2, y + 6], fill=255)
    draw.polygon([(x, y), (x - 2, y + 3), (x + 2, y + 3)], fill=255)


def _ellipsis(draw) -> None:
    """Three dots below face for bored/thinking."""
    for i in range(3):
        x = 54 + i * 8
        draw.ellipse([x, 57, x + 3, 60], fill=255)


# ─────────────────────────────────────────────────────────────────────────────
# Eye-roll animation
# ─────────────────────────────────────────────────────────────────────────────

def _eyeroll_frame(draw, step: int) -> None:
    """
    Frame-by-frame eye-roll.
      step  0–10  : pupils drift upward
      step 11–20  : pupils drift to upper-right
      step 21–27  : eyes close (shrink to line)
    """
    for cx, cy in (L_EYE, R_EYE):
        r, pr = EYE_R, PUPIL_R
        max_d = r - pr - 1      # max pupil travel distance

        if step <= 20:
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=255, width=2)

            if step <= 10:
                t  = step / 10.0
                px = cx
                py = int(cy - t * max_d)
            else:
                t  = (step - 10) / 10.0
                px = int(cx + t * max_d)
                py = cy - max_d

            draw.ellipse([px - pr, py - pr, px + pr, py + pr], fill=255)

        else:
            # Eyelids closing
            t  = (step - 21) / 6.0
            rr = max(0, int(r * (1.0 - t)))
            if rr > 0:
                draw.line([(cx - rr, cy), (cx + rr, cy)], fill=255, width=2)


# ─────────────────────────────────────────────────────────────────────────────
# FaceController
# ─────────────────────────────────────────────────────────────────────────────

class FaceController:
    """
    Thread-safe OLED face driver.

    Public API (all thread-safe):
        start()                — start the background render thread
        stop()                 — request graceful shutdown
        set_mode(str)          — "presence" | "chat"
        set_speaking(bool)     — animate mouth while True
        update_emotion(state)  — call every main-loop tick with current EmotionState
        play_eyeroll()         — queue an eye-roll (only fires in presence/sleeping)
    """

    def __init__(self, i2c_port: int = 1, i2c_address: int = 0x3C) -> None:
        self._mode        = "presence"
        self._speaking    = False
        self._state       = None
        self._eyeroll     = False
        self._speak_frame = 0
        self._zzz_phase   = 0.0

        self._lock    = threading.Lock()
        self._running = False
        self._thread  = None
        self._device  = None

        if _LUMA_OK:
            try:
                serial       = i2c(port=i2c_port, address=i2c_address)
                self._device = ssd1306(serial)
            except Exception as exc:
                print(f"[oled_face] Display not found ({exc}). Face animations disabled.")

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._running = True
        self._thread  = threading.Thread(
            target=self._loop, daemon=True, name="oled-face"
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def set_mode(self, mode: str) -> None:
        with self._lock:
            self._mode = mode

    def set_speaking(self, speaking: bool) -> None:
        with self._lock:
            self._speaking = speaking
            if speaking:
                self._speak_frame = 0

    def update_emotion(self, state) -> None:
        with self._lock:
            self._state = state

    def play_eyeroll(self) -> None:
        """Trigger eye-roll. Only queued when in presence (sleeping) mode."""
        with self._lock:
            if self._mode == "presence" and not self._speaking:
                self._eyeroll = True

    # ── Internal render loop ──────────────────────────────────────────────────

    def _loop(self) -> None:
        er_step = -1  # -1 = not animating

        while self._running:
            t0 = time.monotonic()

            # Snapshot state under lock
            with self._lock:
                mode     = self._mode
                speaking = self._speaking
                state    = self._state
                sf       = self._speak_frame
                zp       = self._zzz_phase
                do_er    = self._eyeroll
                if do_er:
                    self._eyeroll = False
                    er_step = 0

            expr = _expression(mode, speaking, state)

            # Build frame
            img  = Image.new("1", (W, H), 0)
            draw = ImageDraw.Draw(img)

            if er_step >= 0:
                # ── Eye-roll overrides everything ─────────────────────────
                _eyeroll_frame(draw, er_step)
                er_step += 1
                if er_step >= _ER_FRAMES:
                    er_step = -1

            elif expr == "sleeping":
                # ── Sleeping face ─────────────────────────────────────────
                for cx, cy in (L_EYE, R_EYE):
                    draw.line([(cx - EYE_R, cy), (cx + EYE_R, cy)],
                              fill=255, width=2)
                draw.line(
                    [(MOUTH_CX - 8, MOUTH_CY), (MOUTH_CX + 8, MOUTH_CY)],
                    fill=255, width=1
                )
                _zzz(draw, zp)

            else:
                # ── Awake face ────────────────────────────────────────────
                _eye(draw, L_EYE[0], L_EYE[1], expr, "left")
                _eye(draw, R_EYE[0], R_EYE[1], expr, "right")
                _mouth(draw, expr, sf, speaking)
                if expr == "worried":
                    _sweat(draw)
                if expr == "bored":
                    _ellipsis(draw)

            # Push to display
            if self._device is not None:
                self._device.display(img)

            # Advance animation counters
            with self._lock:
                if speaking:
                    self._speak_frame = (sf + 1) % len(_SPEAK_H)
                if expr == "sleeping":
                    self._zzz_phase = (zp + 0.05) % 1.0

            # Frame-rate cap
            elapsed = time.monotonic() - t0
            time.sleep(max(0.0, _FRAME_DT - elapsed))


# ─────────────────────────────────────────────────────────────────────────────
# NullFace — silent stand-in when hardware / library is unavailable
# ─────────────────────────────────────────────────────────────────────────────

class _NullFace:
    def start(self)                  -> None: pass
    def stop(self)                   -> None: pass
    def set_mode(self, mode: str)    -> None: pass
    def set_speaking(self, v: bool)  -> None: pass
    def update_emotion(self, state)  -> None: pass
    def play_eyeroll(self)           -> None: pass


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

def make_face(i2c_port: int = 1, i2c_address: int = 0x3C):
    """Return a FaceController (real) or _NullFace (headless / missing lib)."""
    if not _LUMA_OK:
        return _NullFace()
    return FaceController(i2c_port=i2c_port, i2c_address=i2c_address)
