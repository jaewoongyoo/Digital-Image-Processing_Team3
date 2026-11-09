"""Run a Hand Beat session and manage its resources."""
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pygame

from game.game_manager import GameManager
from game.note_manager import load_chart
from gesture.gesture_detector import GestureDetector
from interface import keyboard_input
from interface.audio_manager import AudioManager, create_demo
from interface.game_ui import draw
from vision import webcam


def run(chart_path, keyboard, camera_index, audio_offset_ms, demo_path):
    camera = audio = None
    try:
        chart = load_chart(chart_path)
        if Path(chart['audio']).resolve() == demo_path.resolve() and not demo_path.exists():
            create_demo(demo_path)
        audio = AudioManager(chart['audio'])
        if not keyboard:
            camera = cv2.VideoCapture(camera_index)
            webcam.configure(camera)
        cv2.namedWindow('Hand Beat')
        if camera is not None:
            webcam.show_settings()
        play(chart['notes'], audio, camera, audio_offset_ms / 1000)
    except (OSError, ValueError, KeyError, RuntimeError, cv2.error, pygame.error) as exc:
        print(f'Hand Beat error: {exc}', file=sys.stderr)
        return 1
    finally:
        if camera is not None:
            camera.release()
        if audio is not None:
            audio.close()
        pygame.quit()
        cv2.destroyAllWindows()
    return 0


def play(notes, audio, camera, audio_offset):
    game, detector = GameManager(notes), GestureDetector()
    state, start, previous = 'ready', 0.0, time.monotonic()
    while True:
        stamp = time.monotonic()
        fps = 1 / max(stamp - previous, 1e-6)
        previous = stamp
        if camera is None:
            frame, point = np.zeros((480, 640, 3), dtype=np.uint8), None
        else:
            frame, point = webcam.read(camera)

        controls = keyboard_input.poll()
        if controls.quit_requested:
            break
        if controls.reset:
            audio.stop()
            game, detector = GameManager(notes), GestureDetector()
            state = 'ready'
        if controls.begin and state == 'ready':
            start, state = stamp + 3, 'countdown'
        if state == 'countdown' and stamp >= start:
            audio.play()
            start = time.monotonic()
            stamp = start
            state = 'playing'

        now = stamp - start - audio_offset
        if state == 'playing':
            held = None
            if camera is None:
                held = keyboard_input.held_lane()
            elif point is not None and 320 <= point[1] < 480:
                held = min(3, point[0] // 160)
            lane = detector.update(point, stamp, game.active is not None)
            for hit_lane in controls.pressed:
                game.hit(hit_lane, now)
            if lane is not None:
                game.hit(lane, now)
            game.update(now, held)
            if game.finished and not audio.busy():
                state = 'result'
        cv2.imshow('Hand Beat', draw(frame, game, now, state, point, fps))
