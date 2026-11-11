import cv2
import numpy as np
import time
from settings import HIT_Y, RESET_Y


def rounded_rect(frame, left, top, right, bottom, radius, color):
    """Filled rounded rectangle for the lane receptors."""
    cv2.rectangle(frame, (left + radius, top), (right - radius, bottom), color, -1)
    cv2.rectangle(frame, (left, top + radius), (right, bottom - radius), color, -1)
    for x in (left + radius, right - radius):
        for y in (top + radius, bottom - radius):
            cv2.circle(frame, (x, y), radius, color, -1, cv2.LINE_AA)


def draw_note(frame, x, y, is_hold=False):
    """Draw a compact, illuminated version of the silver-rimmed receptor."""
    left, right = x - 58, x + 58
    rim = (45, 205, 95) if is_hold else (205, 220, 222)
    surface = (25, 205, 85) if is_hold else (220, 230, 65)
    highlight = (110, 255, 185) if is_hold else (245, 245, 155)
    rounded_rect(frame, left - 2, y - 8, right + 2, y + 15, 10, (12, 13, 16))
    rounded_rect(frame, left, y - 11, right, y + 11, 10, (105, 110, 114))
    rounded_rect(frame, left + 2, y - 10, right - 2, y + 8, 8, rim)
    rounded_rect(frame, left + 4, y - 9, right - 4, y + 6, 7, (38, 48, 50))
    rounded_rect(frame, left + 6, y - 8, right - 6, y + 4, 6, surface)
    rounded_rect(frame, left + 9, y - 7, right - 9, y + 1, 4, highlight)
    # Dark central inset and bright edge give the cap the reference's depth.
    cv2.rectangle(frame, (x - 18, y - 8), (x + 18, y - 3), (40, 55, 58), -1)
    cv2.line(frame, (left + 14, y - 6), (x - 22, y - 6), (255, 255, 225), 1, cv2.LINE_AA)
    cv2.line(frame, (x + 22, y - 6), (right - 14, y - 6), (255, 255, 225), 1, cv2.LINE_AA)
    cv2.line(frame, (left + 13, y + 8), (right - 13, y + 8), (210, 220, 220), 1, cv2.LINE_AA)


def draw_hold_tail(frame, x, top, bottom):
    """Bright yellow sustain ribbon matching the green hold-note head."""
    bottom = min(bottom, HIT_Y, frame.shape[0] - 1)
    if bottom <= top or bottom < 0:
        return
    left, right = max(0, x - 20), min(frame.shape[1], x + 21)
    visible_top = max(0, top)
    if left >= right or visible_top >= bottom:
        return
    region = frame[visible_top:bottom + 1, left:right]
    # Opaque gold edges and a lemon-yellow core remain visible over the camera.
    distance = np.abs(np.arange(left, right, dtype=np.float32) - x) / 20
    profile = np.clip((1 - distance) * 10, 0, 1)
    alpha = np.broadcast_to(profile[None, :, None], region.shape[:2] + (1,))
    edge = np.array((10, 155, 195), dtype=np.float32)
    core = np.array((70, 255, 255), dtype=np.float32)
    color = edge + (core - edge) * np.maximum(0, 1 - distance)[None, :, None]
    region[:] = (region * (1 - alpha) + color * alpha).astype(np.uint8)
    if 0 <= top < bottom:
        cv2.ellipse(frame, (x, top), (19, min(5, bottom - top)), 0, 0, 180,
                    (30, 245, 245), -1, cv2.LINE_AA)


class PadEffects:
    def __init__(self):
        self.strikes = [-float('inf')] * 4

    def trigger(self, lane, timestamp):
        self.strikes[lane] = timestamp

    def clear(self):
        self.strikes = [-float('inf')] * 4

    def strengths(self, timestamp, held_lanes=()):
        return [max(1.0 if lane in held_lanes else 0.0,
                    max(0.0, 1.0 - (timestamp - strike) / 0.3))
                for lane, strike in enumerate(self.strikes)]


def draw_receptors(frame, active_lane, strengths=None):
    strengths = strengths if strengths is not None else [0.0] * 4
    glow = np.zeros_like(frame)
    for lane, strength in enumerate(strengths):
        if strength <= 0:
            continue
        x = lane * 160 + 80
        color = tuple(int(c * strength) for c in (200, 150, 35))
        cv2.ellipse(glow, (x, HIT_Y), (65, 22), 0, 0, 360, color, -1, cv2.LINE_AA)
        cv2.rectangle(glow, (x - 48, HIT_Y - 65), (x + 48, HIT_Y),
                      tuple(int(c * strength) for c in (45, 30, 5)), -1)
    glow = cv2.GaussianBlur(glow, (0, 0), 9)
    cv2.add(frame, glow, dst=frame)
    for lane in range(4):
        left, right = lane * 160 + 12, (lane + 1) * 160 - 12
        # Layered dark base, silver rim, and inset cyan playing surface.
        rounded_rect(frame, left - 3, HIT_Y - 12, right + 3, HIT_Y + 28, 16, (12, 13, 16))
        rounded_rect(frame, left, HIT_Y - 17, right, HIT_Y + 20, 16, (105, 110, 114))
        rounded_rect(frame, left + 2, HIT_Y - 16, right - 2, HIT_Y + 15, 14, (185, 193, 196))
        rounded_rect(frame, left + 4, HIT_Y - 15, right - 4, HIT_Y + 10, 12, (21, 24, 27))
        rounded_rect(frame, left + 8, HIT_Y - 13, right - 8, HIT_Y + 5, 9, (185, 210, 55))
        strength = max(strengths[lane], 0.65 if active_lane == lane else 0.0)
        color = tuple(int(a + (b - a) * strength)
                      for a, b in zip((36, 39, 42), (245, 235, 130)))
        rounded_rect(frame, left + 9, HIT_Y - 12, right - 9, HIT_Y + 4, 8, color)
        if strength > 0:
            cv2.line(frame, (left + 20, HIT_Y - 8), (right - 20, HIT_Y - 8),
                     tuple(int(c * strength) for c in (255, 255, 235)), 2, cv2.LINE_AA)
        cv2.line(frame, (left + 20, HIT_Y + 14), (right - 20, HIT_Y + 14), (220, 225, 225), 1, cv2.LINE_AA)


def text(frame, label, y, scale=0.65):
    cv2.putText(frame, label, (15, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 2)


def draw(frame, game, now, state, point, fps, effects=None, held_lanes=(), timestamp=None):
    frame = (frame * 0.35).astype('uint8')
    for x in (160, 320, 480):
        cv2.line(frame, (x, 90), (x, 480), (95, 95, 95), 1)
    cv2.line(frame, (0, RESET_Y), (640, RESET_Y), (100, 100, 100), 1)
    if state == 'playing':
        for note in game.notes:
            if note['state'] not in ('pending', 'holding'):
                continue
            x = note['lane'] * 160 + 80
            y = int(HIT_Y - 180 * (note['time'] - now))
            holding = note['state'] == 'holding'
            if holding:
                # The receptor consumes the head while the remaining tail approaches it.
                y = HIT_Y
            if note['type'] == 'hold':
                end_y = int(HIT_Y - 180 * (note['time'] + note['duration'] - now))
                draw_hold_tail(frame, x, end_y, y)
            if not holding and -20 <= y <= 480:
                draw_note(frame, x, y, is_hold=note['type'] == 'hold')
        text(frame, f'{now:.1f}s   {game.feedback}', 115)
    active_lane = game.active['lane'] if game.active is not None else None
    strengths = effects.strengths(time.monotonic() if timestamp is None else timestamp, held_lanes) if effects else None
    draw_receptors(frame, active_lane, strengths)
    if point is not None:
        cv2.circle(frame, point, 12, (0, 255, 0), 3)
    text(frame, f'HAND BEAT   Score {game.score}   Combo {game.combo}', 30)
    text(frame, f'{fps:.0f} FPS | D F J K | ESC quit | R reset', 60, 0.5)
    if state == 'ready':
        text(frame, 'SPACE: start | Green marker: raise then strike', 170, 0.55)
    elif state == 'countdown':
        text(frame, f'Starting in {max(1, int(-now) + 1)}', 170)
    elif state == 'result':
        text(frame, f'RESULT   Max combo: {game.max_combo}', 150)
        text(frame, '  '.join(f'{k}: {v}' for k, v in game.counts.items()), 190, 0.5)
        for index, kind in enumerate(('tap', 'hold')):
            total = sum(n['type'] == kind for n in game.notes)
            text(frame, f'{kind.upper()}: {game.success[kind]}/{total}', 230 + 35 * index)
        text(frame, 'R: restart', 310)
    return frame
