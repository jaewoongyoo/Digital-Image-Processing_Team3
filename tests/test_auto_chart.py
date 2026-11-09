import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from game.note_manager import load_chart
from tools.auto_chart import SAMPLE_RATE, STEP, make_chart, place_lanes
from tools.beat_timing import GRID_CONFIDENCE, Tempo, align_onsets, estimate_tempo


def click_track(times, duration, amplitudes=None):
    samples = np.zeros(round(duration * SAMPLE_RATE), dtype=np.float32)
    t = np.arange(800) / SAMPLE_RATE
    click = np.sin(2 * np.pi * 530 * t) * np.exp(-100 * t)
    if amplitudes is None:
        amplitudes = np.full(len(times), .6)
    for time, amplitude in zip(times, amplitudes):
        start = round(time * SAMPLE_RATE)
        samples[start:start + len(click)] += amplitude * click
    return samples


class AutoChartTests(unittest.TestCase):
    def assert_loadable(self, chart):
        payload = json.dumps({"audio": "../assets/demo.wav", **chart}, allow_nan=False)
        with patch.object(Path, "read_text", return_value=payload):
            return load_chart("charts/test.json")["notes"]

    def test_constant_bpm_audio_and_subdivision_octaves(self):
        chart = make_chart(click_track(np.arange(.2, 12, .5), 12), lead_in=0)
        self.assertAlmostEqual(chart["bpm"], 120, delta=1)
        self.assertGreaterEqual(chart["bpm_confidence"], GRID_CONFIDENCE)

        for bpm in (90, 100, 180):
            with self.subTest(bpm=bpm):
                times = np.arange(.2, 22, 60 / bpm / 2)
                weights = np.resize([1., .2], len(times))
                tempo = estimate_tempo(times, weights, 22., STEP)
                self.assertAlmostEqual(tempo.bpm, bpm, delta=1)

    def test_swing_is_preserved_and_only_near_grid_onsets_move(self):
        beats = np.arange(.2, 20, .5)
        times = np.sort(np.r_[beats, beats + 1 / 3])
        tempo = estimate_tempo(times, np.tile([1., .6], len(beats)), 21., STEP)
        self.assertAlmostEqual(tempo.bpm, 120, delta=1)
        np.testing.assert_allclose(align_onsets(times, tempo)[1::2], times[1::2])

        near_and_far = np.array([.509, .741, .881, 1.041])
        np.testing.assert_allclose(align_onsets(near_and_far, Tempo(120, 0., .9)),
                                   [.5, .75, .875, 1.041])
        np.testing.assert_array_equal(align_onsets(near_and_far, Tempo(120, 0., .2)),
                                      near_and_far)

    def test_tempo_changes_do_not_force_a_global_grid(self):
        times = np.r_[np.arange(.2, 10, .5), np.arange(10.2, 20, 60 / 165)]
        diagnostics = {}
        chart = make_chart(click_track(times, 21), lead_in=0, diagnostics=diagnostics)
        self.assertTrue(chart["notes"])
        self.assertFalse(diagnostics["grid_used"])
        self.assertLess(chart["bpm_confidence"], GRID_CONFIDENCE)
        self.assertLessEqual(diagnostics["timing"]["onset_to_note"]["max_ms"], .5)

    def test_silence_weak_hits_and_irregular_rhythm(self):
        self.assertFalse(make_chart(np.zeros(SAMPLE_RATE), lead_in=0)["notes"])
        times = np.cumsum(np.random.default_rng(3).uniform(.13, .77, 36))
        samples = click_track(times, times[-1] + .5, np.full(len(times), .002))
        diagnostics = {}
        chart = make_chart(samples, lead_in=0, diagnostics=diagnostics)
        self.assertTrue(chart["notes"])
        self.assertFalse(diagnostics["grid_used"])

    def test_difficulty_spacing_activity_and_determinism(self):
        times = np.arange(.2, 24, .125)
        amplitudes = np.where((times > 8) & (times < 16), .08, .7)
        samples = click_track(times, 24, amplitudes)
        outputs = [make_chart(samples, lead_in=0, difficulty=d)
                   for d in ("easy", "normal", "hard")]
        counts = [len(chart["notes"]) for chart in outputs]
        self.assertLess(counts[0], counts[1])
        self.assertLess(counts[1], counts[2])
        self.assertEqual(outputs[1], make_chart(samples, lead_in=0))
        self.assertTrue(all(n["type"] == "tap" for c in outputs for n in c["notes"]))
        normal_times = np.array([n["time"] for n in outputs[1]["notes"]])
        self.assertLess(sum((normal_times >= 8) & (normal_times < 16)),
                        sum((normal_times >= 0) & (normal_times < 8)))
        overridden = self.assert_loadable(make_chart(samples, .45, 0, difficulty="hard"))
        self.assertTrue(np.all(np.diff([n["time"] for n in overridden]) >= .45 - 1e-9))

    def test_hold_is_opt_in_and_does_not_overlap(self):
        samples = click_track([3.3, 4.2], 5.)
        t = np.arange(2 * SAMPLE_RATE) / SAMPLE_RATE
        samples[SAMPLE_RATE:3 * SAMPLE_RATE] = .3 * np.sin(2 * np.pi * 220 * t)
        plain = make_chart(samples, lead_in=0)
        self.assertTrue(all(n["type"] == "tap" for n in plain["notes"]))
        chart = make_chart(samples, lead_in=0, enable_hold=True)
        notes = self.assert_loadable(chart)
        holds = [n for n in notes if n["type"] == "hold"]
        self.assertEqual(len(holds), 1)
        self.assertAlmostEqual(holds[0]["time"], 1., delta=.03)
        self.assertAlmostEqual(holds[0]["duration"], 2., delta=.15)
        for note, following in zip(notes, notes[1:]):
            self.assertLess(note["time"] + note.get("duration", 0), following["time"])

    def test_lane_placement_prefers_timbre_without_dominating(self):
        tones = np.tile([[1., .8, .3, .2]], (40, 1))
        lanes = place_lanes(np.arange(40) * .5, tones, Tempo(120, 0., .9))
        self.assertLessEqual(lanes.count(0), 24)
        self.assertGreaterEqual(lanes.count(0) + lanes.count(1), 36)
        self.assertFalse(any(len(set(lanes[i:i + 4])) == 1 for i in range(len(lanes) - 3)))


if __name__ == "__main__":
    unittest.main()
