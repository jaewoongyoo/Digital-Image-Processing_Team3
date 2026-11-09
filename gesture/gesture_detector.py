"""Camera coordinates use a mirrored 640 x 480 frame."""
from settings import HIT_Y, RESET_Y


class GestureDetector:
    def __init__(self, hit_y=HIT_Y, reset_y=RESET_Y, min_speed=180):
        self.hit_y, self.reset_y, self.min_speed = hit_y, reset_y, min_speed
        self.ready = False
        self.previous = None

    def update(self, point, timestamp, locked=False):
        if point is None or locked:
            self.previous = None
            self.ready = False
            return None
        x, y = point
        lane = min(3, max(0, int(x // 160)))
        if y < self.reset_y:
            self.ready = True
        event = None
        if self.previous is not None:
            _, old_y, old_t = self.previous
            dt = timestamp - old_t
            if (self.ready and 0 < dt <= 0.15 and old_y < self.hit_y <= y
                    and (y - old_y) / dt >= self.min_speed):
                self.ready = False
                event = lane
        self.previous = (x, y, timestamp)
        return event
