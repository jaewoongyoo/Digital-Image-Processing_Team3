"""Match calibration taps to the 120 BPM demo and store a local offset."""
import json
import math
from statistics import median

BEAT_SECONDS = .5
FIRST_SAMPLE_BEAT = 4
LAST_SAMPLE_BEAT = 39
MIN_SAMPLES = 8
TARGET_SAMPLES = 12


def record_tap(samples, elapsed):
    beat = round(elapsed / BEAT_SECONDS)
    if FIRST_SAMPLE_BEAT <= beat <= LAST_SAMPLE_BEAT and beat not in samples:
        error = elapsed - beat * BEAT_SECONDS
        if abs(error) <= .2:
            samples[beat] = error * 1000


def calculate_offset(samples):
    if len(samples) < MIN_SAMPLES:
        return None
    return round(median(samples.values()), 1)


def load_offset(path):
    try:
        value = float(json.loads(path.read_text(encoding='utf-8'))['audio_offset_ms'])
        return value if math.isfinite(value) else 0.0
    except (OSError, ValueError, TypeError, KeyError):
        return 0.0


def save_offset(path, offset):
    path.write_text(json.dumps({'audio_offset_ms': offset}) + '\n', encoding='utf-8')
