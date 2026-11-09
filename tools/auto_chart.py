"""Generate a Hand Beat TAP chart from an audio file."""
import argparse
import json
import os
from pathlib import Path

import numpy as np

SAMPLE_RATE = 22050
HOP = 220
FRAME = 1024
STEP = HOP / SAMPLE_RATE
BAND_EDGES = (30, 160, 600, 2500, 11025)


def load_audio(path):
    # SDL decodes the track without playing it or opening a physical device.
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame

    try:
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, allowedchanges=0)
        samples = pygame.sndarray.array(pygame.mixer.Sound(str(path)))
    except pygame.error as exc:
        raise ValueError(f"Could not decode {path.name}: {exc}") from exc
    finally:
        pygame.mixer.quit()
    return samples.mean(axis=1, dtype=np.float32) / 32768


def spectral_flux(samples):
    """Return positive spectral changes for four frequency bands."""
    padded = np.pad(samples, FRAME // 2)
    frames = np.lib.stride_tricks.sliding_window_view(padded, FRAME)[::HOP]
    window = np.hanning(FRAME)
    frequencies = np.fft.rfftfreq(FRAME, 1 / SAMPLE_RATE)
    bands = [(frequencies >= low) & (frequencies < high)
             for low, high in zip(BAND_EDGES, BAND_EDGES[1:])]
    flux = np.empty((len(frames), 4))
    previous = np.zeros((1, len(frequencies)))
    for start in range(0, len(frames), 512):
        spectrum = np.log1p(np.abs(np.fft.rfft(frames[start:start + 512] * window)))
        rises = np.maximum(0, np.diff(spectrum, axis=0, prepend=previous))
        for lane, bins in enumerate(bands):
            flux[start:start + len(rises), lane] = rises[:, bins].mean(axis=1)
        previous = spectrum[-1:]
    return flux


def detect_onsets(strength):
    if len(strength) < 3:
        return np.array([], dtype=int)
    radius = 10
    local_mean = np.convolve(np.pad(strength, radius, mode="edge"),
                             np.ones(2 * radius + 1) / (2 * radius + 1), mode="valid")
    middle = strength[1:-1]
    peaks = ((middle > strength[:-2]) & (middle >= strength[2:])
             & (middle > np.maximum(1.5 * local_mean[1:-1], .06 * strength.max())))
    return np.flatnonzero(peaks) + 1


def estimate_beat(strength, onsets):
    """Estimate a constant tempo and the first beat phase in seconds."""
    min_lag, max_lag = round(60 / (200 * STEP)), round(60 / (60 * STEP))
    if len(onsets) < 4 or len(strength) <= 2 * max_lag:
        return None, None
    pulse = np.zeros_like(strength)
    # Alternating loud and soft beats should still count at the same tempo.
    pulse[onsets] = 1
    pulse = np.convolve(pulse, [.25, .5, .25], mode="same")
    energy = np.sum(pulse ** 2)
    lags = np.arange(min_lag, max_lag + 1)
    scores = np.array([np.sum(pulse[lag:] * pulse[:-lag]) / energy for lag in lags])
    candidates = np.flatnonzero((scores >= np.r_[-1, scores[:-1]])
                                & (scores >= np.r_[scores[1:], -1])
                                & (scores >= max(.12, .85 * scores.max())))
    if not len(candidates):
        return None, None

    peak = candidates[0]
    lag = float(lags[peak])
    if 0 < peak < len(scores) - 1:
        left, center, right = scores[peak - 1:peak + 2]
        curvature = left - 2 * center + right
        if curvature < 0:
            lag += .5 * (left - right) / curvature
    period = lag * STEP
    phase = np.sum(strength[onsets] * np.exp(2j * np.pi * onsets * STEP / period))
    offset = (np.angle(phase) / (2 * np.pi) * period) % period
    if offset > period - STEP:
        offset = 0.0
    return 60 / period, float(offset)


def rank_onsets(times, weights, bpm, offset):
    if bpm is None:
        return weights, bpm, offset

    # Refine the coarse autocorrelation estimate against the 16th-note grid.
    tempos = bpm * np.linspace(.994, 1.006, 121)
    phases = np.exp(2j * np.pi * times * tempos[:, None] / 15) @ weights
    best = int(np.argmax(np.abs(phases)))
    if abs(phases[best]) < .25 * weights.sum():
        return weights, bpm, offset

    bpm = float(tempos[best])
    period = 60 / bpm
    subdivision = period / 4
    phase = np.angle(phases[best]) * subdivision / (2 * np.pi)
    offset = float((phase + round((offset - phase) / subdivision) * subdivision) % period)
    error = (times - offset + subdivision / 2) % subdivision - subdivision / 2
    alignment = np.exp(-.5 * (error / .022) ** 2)

    # Reward attacks recurring at the same rhythmic position in nearby beats.
    repeat = np.zeros_like(times)
    for beats in (-4, -1, 1, 4):
        target = times + beats * period
        right = np.searchsorted(times, target)
        before = times[np.maximum(0, right - 1)]
        after = times[np.minimum(len(times) - 1, right)]
        distance = np.minimum(abs(target - before), abs(target - after))
        repeat += distance <= .025
    return weights * (.55 + .30 * alignment + .15 * repeat / 4), bpm, offset


def make_chart(samples, min_gap, lead_in):
    flux = spectral_flux(samples)
    strength = flux.mean(axis=1)
    onsets = detect_onsets(strength)
    bpm, offset = estimate_beat(strength, onsets)
    if not len(onsets):
        return {"bpm": None, "beat_offset": None,
                "duration": round(len(samples) / SAMPLE_RATE, 3), "notes": []}
    times = onsets * STEP
    priority, bpm, offset = rank_onsets(times, np.sqrt(strength[onsets]), bpm, offset)
    ranked = onsets[np.argsort(-priority, kind="stable")]
    available = np.ones(len(strength), dtype=bool)
    selected = []
    radius = int(np.ceil(min(min_gap / STEP, len(strength)))) - 1
    for index in ranked:
        if index * STEP >= lead_in and available[index]:
            selected.append(index)
            available[max(0, index - radius):index + radius + 1] = False

    attacks = flux[onsets - 1] + flux[onsets] + flux[onsets + 1]
    band_scale = np.maximum(np.percentile(attacks, 90, axis=0), 1e-9)
    notes = []
    previous_lane, run_length = None, 0
    for note_id, index in enumerate(sorted(selected), 1):
        tone = attacks[np.searchsorted(onsets, index)] / band_scale
        recent = np.bincount([note["lane"] for note in notes[-16:]], minlength=4)
        scores = tone / max(tone.max(), 1e-9) - .07 * recent
        if previous_lane is not None:
            scores[previous_lane] -= .12 * run_length
            if run_length >= 3:
                scores[previous_lane] = -np.inf
        lane = int(np.argmax(scores))
        run_length = run_length + 1 if lane == previous_lane else 1
        previous_lane = lane
        notes.append({"id": note_id, "type": "tap", "lane": lane,
                      "time": round(float(index * STEP), 3)})
    return {"bpm": round(bpm, 3) if bpm is not None else None,
            "beat_offset": round(offset, 3) if offset is not None else None,
            "duration": round(len(samples) / SAMPLE_RATE, 3), "notes": notes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path, help="Input audio file, such as WAV or MP3")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output JSON chart")
    parser.add_argument("--min-gap", type=float, default=.25, help="Minimum note spacing in seconds")
    parser.add_argument("--lead-in", type=float, default=1., help="Seconds before the first eligible note")
    args = parser.parse_args()
    if not np.isfinite(args.min_gap) or args.min_gap <= 0:
        parser.error("--min-gap must be finite and positive")
    if not np.isfinite(args.lead_in) or args.lead_in < 0:
        parser.error("--lead-in must be finite and non-negative")

    audio, output = args.audio.resolve(), args.output.resolve()
    if not audio.is_file():
        parser.error(f"Audio file not found: {audio}")
    if output.suffix.lower() != ".json" or audio == output:
        parser.error("Output must be a separate .json file")
    try:
        chart = make_chart(load_audio(audio), args.min_gap, args.lead_in)
        if not chart["notes"]:
            parser.error("No playable onsets found. Try a shorter --lead-in or a clearer track.")
        try:
            audio_path = Path(os.path.relpath(audio, output.parent)).as_posix()
        except ValueError:  # Windows paths on different drives.
            audio_path = audio.as_posix()
        chart = {"title": audio.stem, "audio": audio_path, **chart}
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as stream:
            json.dump(chart, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    bpm = chart["bpm"] if chart["bpm"] is not None else "unknown"
    print(f"{len(chart['notes'])} TAP notes | BPM: {bpm} | {output}")


if __name__ == "__main__":
    main()
