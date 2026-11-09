"""Generate a Hand Beat chart from an audio file."""
import argparse
import json
import os
from time import perf_counter
from pathlib import Path

import numpy as np

if __package__:
    from .beat_timing import GRID_CONFIDENCE, align_onsets, estimate_tempo, grid_delta
else:
    from beat_timing import GRID_CONFIDENCE, align_onsets, estimate_tempo, grid_delta

SAMPLE_RATE = 22050
HOP = 220
FRAME = 1024
STEP = HOP / SAMPLE_RATE
BAND_EDGES = (30, 160, 600, 2500, 11025)
# Minimum gap, target notes/second, and candidate strength floor.
DIFFICULTIES = {
    "easy": (.36, 1.25, .16),
    "normal": (.25, 2.35, .095),
    "hard": (.135, 3.8, .065),
}
SECTION_SECONDS = 4



def load_audio(path):
    # SDL decodes the track without playing it or opening a physical device.
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame

    try:
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, allowedchanges=0)
        sound = pygame.mixer.Sound(str(path))
        samples = pygame.sndarray.samples(sound).mean(axis=1, dtype=np.float32)
        samples /= 32768
    except pygame.error as exc:
        raise ValueError(f"Could not decode {path.name}: {exc}") from exc
    finally:
        pygame.mixer.quit()
    return samples


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


def moving_average(values, radius):
    padded = np.pad(values, (radius, radius), mode="edge")
    total = np.r_[0., np.cumsum(padded, dtype=float)]
    width = 2 * radius + 1
    return (total[width:] - total[:-width]) / width


def find_attacks(flux, samples):
    """Find adaptive peaks by band, then merge detections of the same attack."""
    scale = np.maximum(.30 * flux.max(axis=0), np.percentile(flux, 98, axis=0))
    bands = flux / np.maximum(scale, 1e-9)
    weights = np.array([1., 1., .86, .48])
    strength = (bands * weights).max(axis=1)
    candidates = np.zeros(len(flux), dtype=bool)
    for lane, band in enumerate(bands.T):
        threshold = np.maximum(.075 / weights[lane], 1.65 * moving_average(band, 20))
        candidates[1:-1] |= ((band[1:-1] > band[:-2]) & (band[1:-1] >= band[2:])
                             & (band[1:-1] > threshold[1:-1]))
    indices = np.flatnonzero(candidates)
    if not len(indices):
        return indices.astype(float), strength[indices], bands[indices]
    # Merge detections within about 30 ms of the strongest peak.
    accepted = np.ones(len(flux), dtype=bool)
    peaks = []
    for index in indices[np.argsort(-strength[indices], kind="stable")]:
        if accepted[index]:
            peaks.append(index)
            accepted[max(0, index - 3):index + 4] = False
    indices = np.array(sorted(peaks))
    # Reject peaks dominated by the release of a sustained sound.
    frames = samples[:len(samples) // HOP * HOP].reshape(-1, HOP)
    energy = np.einsum("ij,ij->i", frames, frames)
    envelope = moving_average(energy, 1)
    earlier = envelope[np.maximum(0, indices - 3)]
    later = envelope[np.minimum(len(envelope) - 1, indices + 1)]
    indices = indices[later >= .35 * earlier]
    left, center, right = strength[indices - 1], strength[indices], strength[indices + 1]
    curvature = left - 2 * center + right
    shift = np.divide(.5 * (left - right), curvature,
                      out=np.zeros_like(center), where=curvature < -1e-9)
    times = (indices + np.clip(shift, -.5, .5)) * STEP
    return times, center, (bands[indices - 1] + bands[indices] + bands[indices + 1]) / 3


def section_activity(samples, times):
    """Combine smoothed RMS and attack rate over multi-second sections."""
    width = SAMPLE_RATE * SECTION_SECONDS
    starts = np.arange(0, len(samples), width)
    energy = np.array([np.linalg.norm(samples[i:i + width]) / np.sqrt(min(width, len(samples) - i))
                       for i in starts])
    sections = np.minimum((times / SECTION_SECONDS).astype(int), len(starts) - 1)
    counts = np.bincount(sections, minlength=len(starts))
    duration = np.minimum(width, len(samples) - starts) / SAMPLE_RATE
    rates = counts / duration
    energy = moving_average(energy, 1)
    rates = moving_average(rates, 1)
    relative = .65 * energy / max(np.percentile(energy, 75), 1e-9)
    relative += .35 * rates / max(np.percentile(rates, 75), 1e-9)
    return np.clip(relative, 0., 1.4), duration


def rank_attacks(times, strength, tempo, difficulty):
    priority = np.sqrt(strength)
    if tempo.confidence < GRID_CONFIDENCE:
        return priority
    period = 60 / tempo.bpm
    repeat = np.zeros_like(times)
    for beats in (-4, -1, 1, 4):
        target = times + beats * period
        right = np.searchsorted(times, target)
        before = times[np.maximum(0, right - 1)]
        after = times[np.minimum(len(times) - 1, right)]
        repeat += np.minimum(abs(target - before), abs(target - after)) <= .025
    division = {"easy": 1, "normal": 2, "hard": 4}[difficulty]
    error = grid_delta(times, period, tempo.offset, division)
    return priority * (.75 + .15 * np.exp(-.5 * (error / .023) ** 2) + .10 * repeat / 4)


def select_attacks(times, aligned, strength, priority, activity, durations,
                   min_gap, lead_in, difficulty):
    _, rate, floor = DIFFICULTIES[difficulty]
    sections = np.minimum((aligned / SECTION_SECONDS).astype(int), len(activity) - 1)
    budget = np.ceil(rate * durations * (.22 + .78 * activity)).astype(int)
    budget = np.minimum(budget, np.ceil(rate * durations * 1.25).astype(int))
    total = max(1, round(rate * durations.sum()))
    # Millisecond output is also what the loader uses. Enforce spacing after rounding.
    marks = np.rint(aligned * 1000).astype(int)
    gap = max(1, int(np.ceil(min(min_gap, durations.sum() + 1) * 1000 - 1e-9)))
    occupied = np.zeros(round(durations.sum() * 1000) + 1, dtype=bool)
    picked = []
    for index in np.argsort(-priority, kind="stable"):
        mark, section = marks[index], sections[index]
        if (times[index] < lead_in or mark < lead_in * 1000 or mark >= len(occupied)
                or budget[section] <= 0 or occupied[mark]
                or strength[index] < floor * (1.35 - .35 * activity[section])):
            continue
        picked.append(index)
        budget[section] -= 1
        occupied[max(0, mark - gap + 1):mark + gap] = True
        if len(picked) == total:
            break
    return sorted(picked, key=lambda i: marks[i])


def place_lanes(times, tones, tempo):
    """Prefer consistent timbres and rhythmic positions, with a run-length cap."""
    lanes = []
    motifs = {}
    counts = np.zeros(4)
    run = 0
    for time, tone in zip(times, tones):
        primary, secondary = np.argsort(-tone, kind="stable")[:2]
        if tone[secondary] < .55 * tone[primary]:
            secondary = primary
        phase = -1
        if tempo.confidence >= GRID_CONFIDENCE:
            slot = (time - tempo.offset) * tempo.bpm / 15
            if abs(slot - round(slot)) <= .25:
                phase = round(slot) % 4
        motif = (primary, secondary, phase)
        scores = tone / max(tone.max(), 1e-9)
        if motif in motifs:
            scores[motifs[motif]] += .22
        scores -= .45 * np.maximum(0, counts / max(1, len(lanes)) - .40)
        if len(lanes) >= 12:
            scores[counts / len(lanes) >= .58] = -np.inf
        if lanes:
            scores[lanes[-1]] -= .045 * run
            if run >= 3:
                scores[lanes[-1]] = -np.inf
        lane = int(np.argmax(scores))
        motifs.setdefault(motif, lane)
        run = run + 1 if lanes and lane == lanes[-1] else 1
        lanes.append(lane)
        counts[lane] += 1
    return lanes


def add_holds(notes, samples, flux):
    """Promote isolated, stable sustains while reserving a gap before the next TAP."""
    hop = round(.05 * SAMPLE_RATE)
    count = len(samples) // hop
    frames = samples[:count * hop].reshape(-1, hop)
    rms = np.sqrt(np.einsum("ij,ij->i", frames, frames) / hop)
    for index, note in enumerate(notes):
        start = note["time"]
        next_time = notes[index + 1]["time"] if index + 1 < len(notes) else len(samples) / SAMPLE_RATE
        limit = min(start + 2.5, next_time - .10)
        if limit - start < .70:
            continue
        first = int(np.ceil((start + .12) * SAMPLE_RATE / hop))
        end = min(count, int(limit * SAMPLE_RATE / hop))
        reference = np.median(rms[first:first + 4])
        if reference < max(.008, .18 * rms.max()):
            continue
        stable = abs(rms[first:end] / reference - 1) <= .28
        if not stable.all():
            end = first + int(np.flatnonzero(~stable)[0])
        finish = end * hop / SAMPLE_RATE
        if finish - start < .70:
            continue
        attack_frame = round(start / STEP)
        # The release itself can create broadband flux. Check the interior.
        sustain = flux[round((start + .16) / STEP):round((finish - .045) / STEP)].max(axis=1)
        attack = flux[max(0, attack_frame - 2):attack_frame + 3].max()
        if attack > 0 and np.percentile(sustain, 90) < .30 * attack and sustain.max() < .65 * attack:
            note.update(type="hold", duration=round(finish - start, 3))


def timing_stats(source, output, tempo):
    def summary(errors):
        if not len(errors):
            return None
        ms = abs(errors) * 1000
        return dict(mean_ms=round(float(ms.mean()), 2), median_ms=round(float(np.median(ms)), 2),
                    p95_ms=round(float(np.percentile(ms, 95)), 2), max_ms=round(float(ms.max()), 2))

    result = {"onset_to_note": summary(output - source), "grid_before": None, "grid_after": None}
    if tempo.bpm is not None:
        period = 60 / tempo.bpm
        result["grid_before"] = summary(grid_delta(source, period, tempo.offset))
        result["grid_after"] = summary(grid_delta(output, period, tempo.offset))
    return result


def make_chart(samples, min_gap=None, lead_in=1., *, difficulty="normal",
               enable_hold=False, diagnostics=None):
    if min_gap is None:
        min_gap = DIFFICULTIES[difficulty][0]
    duration = len(samples) / SAMPLE_RATE
    flux = spectral_flux(samples)
    times, strength, tones = find_attacks(flux, samples)
    tempo = estimate_tempo(times, strength, duration, STEP)
    aligned = np.clip(align_onsets(times, tempo), 0., duration)
    selected = []
    if len(times):
        activity, durations = section_activity(samples, times)
        priority = rank_attacks(times, strength, tempo, difficulty)
        selected = select_attacks(times, aligned, strength, priority, activity, durations,
                                  min_gap, lead_in, difficulty)
    lanes = place_lanes(aligned[selected], tones[selected], tempo)
    output = np.round(aligned[selected], 3)
    notes = [dict(id=i, type="tap", lane=lane, time=float(time))
             for i, (lane, time) in enumerate(zip(lanes, output), 1)]
    if enable_hold and notes:
        add_holds(notes, samples, flux)
    if diagnostics is not None:
        waveform_hop = round(.05 * SAMPLE_RATE)
        starts = np.arange(0, len(samples), waveform_hop)
        diagnostics.update(
            onset_count=len(times), grid_used=tempo.confidence >= GRID_CONFIDENCE,
            tempo_candidates=list(tempo.candidates[:8]),
            timing=timing_stats(times[selected], output, tempo),
            waveform=dict(bin_seconds=waveform_hop / SAMPLE_RATE,
                          min=np.minimum.reduceat(samples, starts).astype(float).round(4).tolist(),
                          max=np.maximum.reduceat(samples, starts).astype(float).round(4).tolist()),
            notes=[dict(note_id=note["id"], onset=float(source), **{
                key: value for key, value in note.items() if key != "id"})
                for note, source in zip(notes, times[selected])],
        )
    return {"bpm": round(tempo.bpm, 3) if tempo.bpm is not None else None,
            "beat_offset": round(tempo.offset, 3) if tempo.offset is not None else None,
            "bpm_confidence": round(tempo.confidence, 3),
            "duration": round(duration, 3), "notes": notes}


def relative_path(target, parent):
    try:
        return Path(os.path.relpath(target, parent)).as_posix()
    except ValueError:  # Windows paths on different drives.
        return target.as_posix()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path, help="Input audio file, such as WAV or MP3")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output JSON chart")
    parser.add_argument("--difficulty", choices=DIFFICULTIES, default="normal")
    parser.add_argument("--min-gap", type=float, help="Override minimum note spacing in seconds")
    parser.add_argument("--lead-in", type=float, default=1., help="Seconds before the first eligible note")
    parser.add_argument("--enable-hold", action="store_true", help="Promote stable sustains to HOLD notes")
    parser.add_argument("--diagnostics", type=Path, help="Write a separate timing diagnostics JSON")
    args = parser.parse_args()
    if args.min_gap is not None and (not np.isfinite(args.min_gap) or args.min_gap <= 0):
        parser.error("--min-gap must be finite and positive")
    if not np.isfinite(args.lead_in) or args.lead_in < 0:
        parser.error("--lead-in must be finite and non-negative")

    audio, output = args.audio.resolve(), args.output.resolve()
    if not audio.is_file():
        parser.error(f"Audio file not found: {audio}")
    if output.suffix.lower() != ".json" or audio == output:
        parser.error("Output must be a separate .json file")
    diagnostic_path = args.diagnostics.resolve() if args.diagnostics else None
    if diagnostic_path is not None and (
        diagnostic_path in (audio, output) or diagnostic_path.suffix.lower() != ".json"
    ):
        parser.error("Diagnostics must be a separate .json file")
    for path in (output, diagnostic_path):
        if path is not None and path.exists():
            parser.error(f"Output already exists: {path}")
    try:
        start = perf_counter()
        diagnostics = {} if diagnostic_path else None
        chart = make_chart(load_audio(audio), args.min_gap, args.lead_in,
                           difficulty=args.difficulty, enable_hold=args.enable_hold,
                           diagnostics=diagnostics)
        elapsed = perf_counter() - start
        if not chart["notes"]:
            parser.error("No playable onsets found. Try a shorter --lead-in or a clearer track.")
        chart = {"title": audio.stem, "audio": relative_path(audio, output.parent), **chart}
        if diagnostics is not None:
            diagnostics.update(audio=relative_path(audio, diagnostic_path.parent),
                               chart=relative_path(output, diagnostic_path.parent),
                               difficulty=args.difficulty, elapsed_seconds=round(elapsed, 3),
                               bpm=chart["bpm"], beat_offset=chart["beat_offset"],
                               bpm_confidence=chart["bpm_confidence"])
        for path, payload in ((output, chart), (diagnostic_path, diagnostics)):
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("x", encoding="utf-8") as stream:
                    json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
                    stream.write("\n")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    bpm = chart["bpm"] if chart["bpm"] is not None else "unknown"
    holds = sum(note["type"] == "hold" for note in chart["notes"])
    print(f"{len(chart['notes']) - holds} TAP / {holds} HOLD | "
          f"BPM: {bpm} ({chart['bpm_confidence']:.2f}) | {elapsed:.2f}s | {output}")


if __name__ == "__main__":
    main()
