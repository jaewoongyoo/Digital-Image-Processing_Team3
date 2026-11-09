import unittest
from gesture.gesture_detector import GestureDetector
from gesture.judgement import judge
from game.game_manager import GameManager


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
            game.update(1 + i / 10, 1)
        game.hit(1, 2.)
        self.assertEqual(game.score, 600)
        self.assertEqual(game.counts['PERFECT'], 1)

    def test_hold_loss_and_missed_note(self):
        game = GameManager([dict(id=1, type='hold', lane=1, time=1., duration=1.),
                            dict(id=2, type='tap', lane=0, time=3.)])
        game.hit(1, 1.)
        game.update(1.1, None)
        self.assertIsNotNone(game.active)
        game.update(1.21, None)
        game.update(3.21, None)
        self.assertEqual(game.counts['MISS'], 2)
        self.assertEqual(game.combo, 0)


if __name__ == '__main__':
    unittest.main()
