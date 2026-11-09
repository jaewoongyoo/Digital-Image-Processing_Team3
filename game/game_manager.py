from gesture.judgement import judge


class GameManager:
    def __init__(self, notes, *, single_hand=False):
        self.notes = [dict(n, state="pending") for n in notes]
        self.score = self.combo = self.max_combo = 0
        self.counts = {"PERFECT": 0, "GOOD": 0, "MISS": 0}
        self.success = {"tap": 0, "hold": 0}
        self.single_hand = single_hand
        self.active = {}
        self.feedback = "READY"

    def result(self, note, grade):
        note["state"] = "miss" if grade == "MISS" else "complete"
        self.counts[grade] += 1
        self.feedback = grade
        if grade == "MISS":
            self.combo = 0
        else:
            self.score += (300 if grade == "PERFECT" else 100) + (300 if note["type"] == "hold" else 0)
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
            self.success[note["type"]] += 1

    def hit(self, lane, now):
        if lane in self.active or (self.single_hand and self.active):
            return
        candidates = [n for n in self.notes if n["state"] == "pending"
                      and n["lane"] == lane and abs(n["time"] - now) <= 0.2 + 1e-9]
        if not candidates:
            return
        note = min(candidates, key=lambda n: abs(n["time"] - now))
        grade = judge(now - note["time"])
        if note["type"] == "hold":
            note["state"] = "holding"
            note["grade"] = grade
            self.active[lane] = (note, now)
            self.feedback = "HOLDING"
        else:
            self.result(note, grade)

    def update(self, now, held_lanes):
        for lane, (note, last_valid) in list(self.active.items()):
            end = note["time"] + note["duration"]
            # Evaluate only the interval through the scheduled end.
            check_time = min(now, end)
            # A long frame gap cannot establish continuous tracking.
            if check_time - last_valid > 0.2 + 1e-9:
                self.result(note, "MISS")
                del self.active[lane]
            elif now >= end:
                self.result(note, note["grade"])
                del self.active[lane]
            elif lane in held_lanes:
                self.active[lane] = (note, check_time)
        for note in self.notes:
            if note["state"] == "pending" and now - note["time"] > 0.2 + 1e-9:
                self.result(note, "MISS")

    @property
    def finished(self):
        return all(n["state"] in ("complete", "miss") for n in self.notes)
