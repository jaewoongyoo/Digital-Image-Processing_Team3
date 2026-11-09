"""Keyboard input and window controls for the prototype."""
from dataclasses import dataclass, field

import cv2
import pygame

LANE_KEYS = (pygame.K_d, pygame.K_f, pygame.K_j, pygame.K_k)


@dataclass
class KeyboardInput:
    pressed: list[int] = field(default_factory=list)
    reset: bool = False
    begin: bool = False
    quit_requested: bool = False


def poll():
    if not pygame.display.get_init():
        pygame.display.init()
        pygame.display.set_mode((420, 80))
        pygame.display.set_caption('Keyboard input: focus here - D F J K / SPACE / R / ESC')

    controls = KeyboardInput()
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            controls.quit_requested = True
        if event.type == pygame.KEYDOWN:
            controls.quit_requested |= event.key == pygame.K_ESCAPE
            controls.reset |= event.key == pygame.K_r
            controls.begin |= event.key == pygame.K_SPACE
            if event.key in LANE_KEYS:
                controls.pressed.append(LANE_KEYS.index(event.key))

    cvkey = cv2.waitKey(1) & 0xff
    controls.quit_requested |= cvkey == 27 or cv2.getWindowProperty('Hand Beat', cv2.WND_PROP_VISIBLE) < 1
    controls.reset |= cvkey == ord('r')
    controls.begin |= cvkey == 32
    return controls


def held_lane():
    down = pygame.key.get_pressed()
    return next((i for i, key in enumerate(LANE_KEYS) if down[key]), None)
