"""Tempo estimation and conservative timing alignment for automatic charts."""
from dataclasses import dataclass

import numpy as np

GRID_CONFIDENCE = .55


@dataclass
class Tempo:
    bpm: float | None = None
    offset: float | None = None
    confidence: float = 0.
    candidates: tuple = ()


def estimate_tempo(times, strength, duration, step):
    if len(times) < 6 or times[-1] - times[0] < 2.5:
        return Tempo()

    # Count weak attacks too, but retain accents when resolving tempo octaves.
    weights = np.clip(np.sqrt(strength / np.median(strength)), .4, 2.)
    pulse = np.zeros(round(duration / step) + 1)
    np.maximum.at(pulse, np.rint(times / step).astype(int), weights)
    pulse = np.convolve(pulse, [.2, .6, 1., .6, .2], mode='same')
    pulse -= pulse.mean()
    size = 1 << (2 * len(pulse) - 1).bit_length()
    spectrum = np.fft.rfft(pulse, n=size)
    correlation = np.fft.irfft(abs(spectrum) ** 2, n=size)
    correlation = correlation[:round(60 / (55 * step)) + 2] / max(correlation[0], 1e-12)
    low, high = round(60 / (210 * step)), len(correlation) - 2
    peaks = [i for i in range(low, high + 1)
             if correlation[i] >= max(.07, correlation[i - 1], correlation[i + 1])]
    seeds = sorted(peaks, key=lambda i: -correlation[i])[:6]
    if not seeds:
        return Tempo()

    # Also test the half/double interpretation of each strong periodicity.
    lags = []
    for seed in seeds:
        left, center, right = correlation[seed - 1:seed + 2]
        curvature = left - 2 * center + right
        refined = seed + (.5 * (left - right) / curvature if curvature < 0 else 0)
        for lag in (refined, refined / 2, refined * 2):
            if low <= lag <= high and all(abs(lag - other) > .65 for other in lags):
                lags.append(lag)

    # Bound the phase search for long tracks while sampling the entire song.
    indices = np.linspace(0, len(times) - 1, min(2048, len(times)), dtype=int)
    sample_times, sample_weights = times[indices], weights[indices]
    results = []
    for lag in lags:
        ac = float(np.max(correlation[max(low, round(lag) - 1):min(high, round(lag) + 1) + 1]))
        results.append(score_candidate(lag * step, ac, sample_times, sample_weights))
    results.sort(key=lambda item: -item['score'])
    best = results[0]
    alternatives = [item for item in results[1:]
                    if abs(item['bpm'] / best['bpm'] - 1) > .035]
    margin = best['score'] - alternatives[0]['score'] if alternatives else .15
    evidence = .45 * best['repeat'] + .40 * best['alignment'] + .15 * best['beat_coverage']
    confidence = np.clip((evidence - .20) / .52, 0., 1.) * (.78 + .22 * min(margin / .10, 1.))
    # Phase coherence must persist across the song for a single grid to be useful.
    local_alignment = [
        float(np.average(np.exp(-.5 * (grid_delta(t, 60 / best['bpm'], best['offset']) / .018) ** 2),
                         weights=w))
        for t, w in zip(np.array_split(sample_times, 4), np.array_split(sample_weights, 4))
    ]
    if (best['coherence'] < .32 or sum(value < .38 for value in local_alignment) >= 2
            or has_tempo_change(sample_times, best, alternatives)):
        confidence = min(confidence, .49)
    if confidence < .25:
        return Tempo(confidence=float(confidence), candidates=tuple(results))
    return Tempo(best['bpm'], best['offset'], float(confidence), tuple(results))


def has_tempo_change(times, best, alternatives):
    def repetition(chunk, period):
        targets = chunk + period
        targets = targets[targets <= chunk[-1]]
        if not len(targets):
            return 0.
        right = np.searchsorted(chunk, targets)
        error = np.minimum(abs(targets - chunk[right]), abs(targets - chunk[right - 1]))
        return float(np.mean(error <= .025))

    halves = np.array_split(times, 2)
    support = np.array([repetition(chunk, 60 / best['bpm']) for chunk in halves])
    for alternative in alternatives:
        ratio = alternative['bpm'] / best['bpm']
        if min(abs(ratio - .5), abs(ratio - 2)) < .05:
            continue
        difference = support - [repetition(chunk, 60 / alternative['bpm']) for chunk in halves]
        if min(difference) < -.25 and max(difference) > .25:
            return True
    return False


def score_candidate(period, repeat, times, weights):
    """Combine repetition, beat coverage and phase at three subdivisions."""
    trials = period * np.linspace(.988, 1.012, 49)
    harmonic = 2j * np.pi * times
    phases = [np.sum(np.exp(harmonic * (division / trials[:, None])) * weights, axis=1)
              / weights.sum() for division in (1, 2, 4)]
    coherence = .48 * abs(phases[0]) + .30 * abs(phases[1]) + .22 * abs(phases[2])
    index = int(np.argmax(coherence))
    period = float(trials[index])
    # Fit the clearest subdivision, keeping the beat phase close to the accent.
    level = int(np.argmax([abs(p[index]) * penalty
                           for p, penalty in zip(phases, (1., .92, .85))]))
    unit = period / (2 ** level)
    phase = np.angle(phases[level][index]) * unit / (2 * np.pi)
    accent = np.angle(phases[0][index]) * period / (2 * np.pi)
    offset = float((phase + round((accent - phase) / unit) * unit) % period)
    triplets = np.average(np.exp(harmonic * 3 / period), weights=weights)
    swing = 0.
    if abs(triplets) > .65:
        triplet = period / 3
        base = np.angle(triplets) * triplet / (2 * np.pi)
        shares = [float(weights[abs(grid_delta(times, period, base + i * triplet, 1)) < .024].sum()
                        / weights.sum()) for i in range(3)]
        main = int(np.argmax(shares))
        offbeat = max(shares[(main + 1) % 3], shares[(main + 2) % 3])
        if shares[main] > .45 and offbeat > .18 and min(shares) < .12:
            offset = float((base + main * triplet) % period)
            swing = .24 * min(1., offbeat / .32)
    beats = np.rint((times - offset) / period)
    beat_error = abs(times - (offset + beats * period))
    on_beat = beat_error < .045
    beat_coverage = min(1., len(np.unique(beats[on_beat])) / (float(np.ptp(times)) / period + 1))
    beat_weight = float(weights[on_beat].sum() / weights.sum())
    grid_error = abs(grid_delta(times, period, offset))
    alignment = float(np.average(np.exp(-.5 * (grid_error / .018) ** 2), weights=weights))
    # Missing alternating beats penalize double time. A strong accent on every
    # beat and strong lag support favor the faster interpretation over half time.
    score = (.37 * repeat + .22 * alignment + .14 * beat_coverage
             + .14 * beat_weight + .13 * coherence[index] + swing * beat_coverage)
    return dict(bpm=60 / period, offset=offset, score=float(score), repeat=max(0., repeat),
                alignment=alignment, beat_coverage=beat_coverage,
                coherence=float(max(abs(p[index]) for p in phases)))


def grid_delta(times, period, offset, division=4):
    unit = period / division
    return (times - offset + unit / 2) % unit - unit / 2


def align_onsets(times, tempo):
    if tempo.bpm is None or tempo.confidence < GRID_CONFIDENCE:
        return times.copy()
    period = 60 / tempo.bpm
    result = times.copy()
    remaining = np.ones(len(times), dtype=bool)
    # Prefer coarser grids only when close enough. Most off-grid attacks remain intact.
    for division, tolerance in ((1, .016), (2, .014), (4, .010)):
        error = grid_delta(times, period, tempo.offset, division)
        mask = remaining & (abs(error) <= min(tolerance, period / division * .16))
        result[mask] -= error[mask]
        remaining[mask] = False
    return result
