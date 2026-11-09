"""Run with --keyboard to develop without a webcam."""
import argparse
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description='Hand Beat prototype')
    parser.add_argument('--keyboard', action='store_true')
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--chart', type=Path, default=ROOT / 'charts/test_music.json')
    parser.add_argument('--audio-offset-ms', type=float, default=0,
                        help='Positive values delay the chart clock relative to audio play()')
    args = parser.parse_args()
    import cv2
    import numpy as np
    import pygame
    from game.note_manager import load_chart
    from game.game_manager import GameManager
    from gesture.gesture_detector import GestureDetector
    from vision.hand_tracker import track
    from interface.audio_manager import AudioManager, create_demo
    from interface.game_ui import draw

    camera = audio = None
    try:
        chart = load_chart(args.chart)
        demo = ROOT / 'assets/demo.wav'
        if Path(chart['audio']).resolve() == demo.resolve() and not demo.exists():
            create_demo(demo)
        audio = AudioManager(chart['audio'])
        if not args.keyboard:
            camera = cv2.VideoCapture(args.camera)
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            if not camera.isOpened():
                raise RuntimeError('Cannot open webcam. Try --keyboard or --camera 1.')
        cv2.namedWindow('Hand Beat')
        if camera is not None:
            cv2.namedWindow('HSV settings')
            for name, value, limit in [('H low', 35, 179), ('H high', 85, 179),
                                       ('S low', 80, 255), ('S high', 255, 255),
                                       ('V low', 60, 255), ('V high', 255, 255)]:
                cv2.createTrackbar(name, 'HSV settings', value, limit, lambda _: None)
        game, detector = GameManager(chart['notes']), GestureDetector()
        state, start, previous = 'ready', 0.0, time.monotonic()
        keys = (pygame.K_d, pygame.K_f, pygame.K_j, pygame.K_k)
        while True:
            stamp = time.monotonic()
            fps = 1 / max(stamp - previous, 1e-6)
            previous = stamp
            point = None
            if camera is not None:
                ok, frame = camera.read()
                if not ok:
                    raise RuntimeError('Webcam disconnected or frame unavailable.')
                frame = cv2.resize(cv2.flip(frame, 1), (640, 480))
                lower = [cv2.getTrackbarPos(f'{c} low', 'HSV settings') for c in 'HSV']
                upper = [cv2.getTrackbarPos(f'{c} high', 'HSV settings') for c in 'HSV']
                point, raw, mask = track(frame, lower, upper)
                cv2.imshow('HSV settings', np.hstack((raw, mask)))
            else:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
            # pygame owns a small keyboard window so KEYUP reliably ends HOLD.
            if not pygame.display.get_init():
                pygame.display.init()
                pygame.display.set_mode((420, 80))
                pygame.display.set_caption('Keyboard input: focus here - D F J K / SPACE / R / ESC')
            pressed = []
            reset = begin = quit_requested = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    quit_requested = True
                if event.type == pygame.KEYDOWN:
                    quit_requested |= event.key == pygame.K_ESCAPE
                    reset |= event.key == pygame.K_r
                    begin |= event.key == pygame.K_SPACE
                    if event.key in keys:
                        pressed.append(keys.index(event.key))
            cvkey = cv2.waitKey(1) & 0xff
            if quit_requested or cvkey == 27 or cv2.getWindowProperty('Hand Beat', cv2.WND_PROP_VISIBLE) < 1:
                break
            if reset or cvkey == ord('r'):
                pygame.mixer.music.stop()
                game, detector = GameManager(chart['notes']), GestureDetector()
                state = 'ready'
            if (begin or cvkey == 32) and state == 'ready':
                start, state = stamp + 3, 'countdown'
            now = stamp - start
            if state == 'countdown' and now >= 0:
                audio.play()
                start = time.monotonic()
                stamp = start
                state = 'playing'
            now = stamp - start - args.audio_offset_ms / 1000
            if state == 'playing':
                held = None
                if camera is None:
                    down = pygame.key.get_pressed()
                    held = next((i for i, key in enumerate(keys) if down[key]), None)
                elif point is not None and 320 <= point[1] < 480:
                    held = min(3, point[0] // 160)
                lane = detector.update(point, stamp, game.active is not None)
                for hit_lane in pressed + ([] if lane is None else [lane]):
                    game.hit(hit_lane, now)
                game.update(now, held)
                if game.finished and not audio.busy():
                    state = 'result'
            cv2.imshow('Hand Beat', draw(frame, game, now, state, point, fps))
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


if __name__ == '__main__':
    raise SystemExit(main())
