"""Listen to the demo and measure the offset of keyboard taps."""
import sys
import time

import pygame

from game.sync_offset import (
    MIN_SAMPLES, TARGET_SAMPLES, calculate_offset, record_tap, save_offset,
)
from interface.audio_manager import AudioManager, create_demo


def run_calibration(demo_path, profile):
    audio = None
    try:
        if not demo_path.exists():
            create_demo(demo_path)
        audio = AudioManager(demo_path)
        pygame.display.init()
        pygame.font.init()
        screen = pygame.display.set_mode((640, 210))
        pygame.display.set_caption('Hand Beat | Sync calibration')
        font = pygame.font.Font(None, 30)
        clock = pygame.time.Clock()
        samples = {}
        state, start = 'ready', 0.0
        offset = None
        while True:
            events = pygame.event.get()
            stamp = time.monotonic()
            for event in events:
                if event.type == pygame.QUIT or (
                    event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                ):
                    return 0
                if event.type != pygame.KEYDOWN:
                    continue
                if event.key == pygame.K_r:
                    audio.stop()
                    samples.clear()
                    state, offset = 'ready', None
                elif event.key == pygame.K_SPACE and state == 'ready':
                    audio.play()
                    start, state = time.monotonic(), 'playing'
                elif event.key == pygame.K_SPACE and state == 'playing':
                    record_tap(samples, stamp - start)
                elif event.key == pygame.K_RETURN and offset is not None:
                    save_offset(profile, offset)
                    print(f'Saved sync offset: {offset:+.1f} ms')
                    return 0

            if state == 'playing' and (len(samples) >= TARGET_SAMPLES or not audio.busy()):
                audio.stop()
                offset = calculate_offset(samples)
                state = 'result'

            if state == 'ready':
                status = 'Press SPACE to start the 120 BPM demo.'
            elif state == 'playing':
                status = f'Taps accepted: {len(samples)}/{TARGET_SAMPLES}'
            elif offset is None:
                status = f'Need at least {MIN_SAMPLES} taps. Press R to retry.'
            else:
                status = f'Offset {offset:+.1f} ms. Press ENTER to save.'
            screen.fill((17, 24, 39))
            lines = ('Sync calibration', 'Tap SPACE to the clicks after the first four beats.',
                     status, 'R: reset   ESC: exit')
            for index, line in enumerate(lines):
                screen.blit(font.render(line, True, (232, 240, 255)), (24, 24 + 42 * index))
            pygame.display.flip()
            clock.tick(120)
    except (OSError, pygame.error) as exc:
        print(f'Calibration error: {exc}', file=sys.stderr)
        return 1
    finally:
        if audio is not None:
            audio.close()
        pygame.quit()
