import unittest
from unittest.mock import Mock, patch

from game.game_manager import GameManager
from game.session import play
from interface.keyboard_input import KeyboardInput, LANE_KEYS


class SessionTests(unittest.TestCase):
    def run_keyboard_hold(self, camera, point, release=False):
        notes = [dict(id=1, type='hold', lane=1, time=0., duration=0.3)]
        game = GameManager(notes)
        controls = [KeyboardInput(begin=True), KeyboardInput(pressed=[1]),
                    KeyboardInput(), KeyboardInput(), KeyboardInput(),
                    KeyboardInput(quit_requested=True)]
        down = {key: key == LANE_KEYS[1] for key in LANE_KEYS}
        up = dict.fromkeys(LANE_KEYS, False)
        with patch('game.session.GameManager', return_value=game), \
             patch('game.session.time.monotonic', side_effect=[0, 0, 3, 3, 3.1, 3.2, 3.31, 3.4]), \
             patch('game.session.keyboard_input.poll', side_effect=controls), \
             patch('game.session.pygame.key.get_pressed', side_effect=[down] + [up if release else down] * 3), \
             patch('game.session.webcam.read', return_value=(None, point)), \
             patch('game.session.draw'), patch('game.session.cv2.imshow'):
            play(notes, Mock(), camera, 0)
        return game

    def test_keyboard_hold_in_camera_and_keyboard_modes(self):
        for camera, point in ((object(), None), (object(), (80, 450)), (None, None)):
            with self.subTest(camera=camera, point=point):
                game = self.run_keyboard_hold(camera, point)
                self.assertEqual(game.success['hold'], 1)
                self.assertEqual(game.counts['MISS'], 0)

    def test_releasing_keyboard_hold_in_camera_mode_misses(self):
        game = self.run_keyboard_hold(object(), None, release=True)
        self.assertEqual(game.counts['MISS'], 1)
        self.assertEqual(game.success['hold'], 0)


if __name__ == '__main__':
    unittest.main()
