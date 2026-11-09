import json
import math
from pathlib import Path


def load_chart(path, *, single_hand=True):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    notes = data["notes"]
    ids = set()
    occupied_until = {}
    for note in sorted(notes, key=lambda n: n["time"]):
        if note["id"] in ids:
            raise ValueError("Duplicate note ID")
        ids.add(note["id"])
        if note["type"] not in ("tap", "hold") or type(note["lane"]) is not int or note["lane"] not in range(4):
            raise ValueError("Invalid note type or lane")
        if not math.isfinite(note["time"]) or note["time"] < 0:
            raise ValueError("Invalid note time")
        slot = 0 if single_hand else note["lane"]
        if note["time"] <= occupied_until.get(slot, -1.0):
            scope = "Single-hand chart" if single_hand else f"Lane {slot}"
            raise ValueError(f"{scope} contains overlapping notes")
        duration = note.get("duration", 0)
        if note["type"] == "hold" and (not math.isfinite(duration) or duration <= 0):
            raise ValueError("HOLD requires positive duration")
        occupied_until[slot] = note["time"] + (duration if note["type"] == "hold" else 0)
        note["state"] = "pending"
    data["notes"] = sorted(notes, key=lambda n: n["time"])
    audio = Path(data["audio"])
    data["audio"] = str(audio if audio.is_absolute() else path.parent / audio)
    return data
