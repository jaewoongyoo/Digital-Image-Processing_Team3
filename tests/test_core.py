import json
from pathlib import Path
import unittest
from unittest.mock import patch
from gesture.gesture_detector import GestureDetector
from gesture.judgement import judge
from game.game_manager import GameManager
from game.note_manager import load_chart


class CoreTests(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(judge(-0.1), 'PERFECT')
        self.assertEqual(judge(0.2), 'GOOD')
        self.assertEqual(judge(0.201), 'MISS')

    def test_strike_rearm_and_tracking_loss(self):
        detector = GestureDetector()
        self.assertIsNone(detector.update((80, 240), 0))
        self.assertEqual(detector.update((80, 350), 0.1), 0)
        self.assertIsNone(detector.update((80, 360), 0.2))
        detector.update(None, 0.3)
        self.assertIsNone(detector.update((80, 350), 0.4))

    def test_hold_and_single_judgement(self):
        game = GameManager([dict(id=1, type='hold', lane=1, time=1., duration=1.)])
        game.hit(1, 1.)
        for i in range(1, 11):
            game.update(1 + i / 10, {1})
        game.hit(1, 2.)
        self.assertEqual(game.score, 600)
        self.assertEqual(game.counts['PERFECT'], 1)

    def test_hold_loss_and_missed_note(self):
        game = GameManager([dict(id=1, type='hold', lane=1, time=1., duration=1.),
                            dict(id=2, type='tap', lane=0, time=3.)])
        game.hit(1, 1.)
        game.update(1.1, set())
        self.assertIn(1, game.active)
        game.update(1.21, set())
        game.update(3.21, set())
        self.assertEqual(game.counts['MISS'], 2)
        self.assertEqual(game.combo, 0)

    def test_simultaneous_holds_and_tap_are_independent(self):
        game = GameManager([dict(id=1, type='hold', lane=1, time=1., duration=.4),
                            dict(id=2, type='hold', lane=2, time=1., duration=.4),
                            dict(id=3, type='tap', lane=0, time=1.2)])
        game.hit(1, 1.)
        game.hit(2, 1.)
        game.update(1.1, {1, 2})
        game.update(1.2, {2})
        game.hit(0, 1.2)
        game.update(1.31, {2})
        game.update(1.4, {2})
        self.assertEqual([note['state'] for note in game.notes],
                         ['miss', 'complete', 'complete'])
        self.assertEqual(game.score, 900)

    def test_chart_overlap_depends_on_input_mode_and_lane(self):
        notes = [dict(id=1, type='hold', lane=1, time=1., duration=1.),
                 dict(id=2, type='tap', lane=2, time=1.)]
        with patch.object(Path, 'read_text') as read_text:
            path = Path('chart.json')
            read_text.return_value = json.dumps(dict(audio='song.wav', notes=notes))
            self.assertEqual(len(load_chart(path, single_hand=False)['notes']), 2)
            with self.assertRaisesRegex(ValueError, 'Single-hand chart'):
                load_chart(path)
            notes[1]['lane'] = 1
            read_text.return_value = json.dumps(dict(audio='song.wav', notes=notes))
            with self.assertRaisesRegex(ValueError, 'Lane 1'):
                load_chart(path, single_hand=False)


if __name__ == '__main__':
    unittest.main()
