from gesture.judgement import judge


class GameManager:
    def __init__(self, notes):
        self.notes = [dict(n, state="pending") for n in notes]
        self.score = self.combo = self.max_combo = 0
        self.counts = {"PERFECT": 0, "GOOD": 0, "MISS": 0}
        self.success = {"tap": 0, "hold": 0}
        self.active = None
        self.last_valid = None
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
        if self.active is not None:
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
            self.active, self.last_valid = note, now
            self.feedback = "HOLDING"
        else:
            self.result(note, grade)

    def update(self, now, held_lane):
        if self.active is not None:
            note = self.active
            end = note["time"] + note["duration"]
            # Evaluate only the interval through the scheduled end.
            check_time = min(now, end)
            if held_lane == note["lane"]:
                # A long frame gap cannot establish continuous tracking.
                valid = check_time - self.last_valid <= 0.2 + 1e-9
                self.last_valid = check_time
            else:
                valid = check_time - self.last_valid <= 0.2 + 1e-9
            if not valid:
                self.result(note, "MISS")
                self.active = None
            elif now >= end:
                self.result(note, note["grade"])
                self.active = None
        for note in self.notes:
            if note["state"] == "pending" and now - note["time"] > 0.2 + 1e-9:
                self.result(note, "MISS")

    @property
    def finished(self):
        return all(n["state"] in ("complete", "miss") for n in self.notes)
