"""Capture webcam frames and show the HSV calibration preview."""
import cv2
import numpy as np

from vision.hand_tracker import track


def configure(camera):
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not camera.isOpened():
        raise RuntimeError('Cannot open webcam. Try --keyboard or --camera 1.')


def show_settings():
    cv2.namedWindow('HSV settings')
    for name, value, limit in [('H low', 35, 179), ('H high', 85, 179),
                               ('S low', 80, 255), ('S high', 255, 255),
                               ('V low', 60, 255), ('V high', 255, 255)]:
        cv2.createTrackbar(name, 'HSV settings', value, limit, lambda _: None)


def read(camera):
    ok, frame = camera.read()
    if not ok:
        raise RuntimeError('Webcam disconnected or frame unavailable.')
    frame = cv2.resize(cv2.flip(frame, 1), (640, 480))
    lower = [cv2.getTrackbarPos(f'{c} low', 'HSV settings') for c in 'HSV']
    upper = [cv2.getTrackbarPos(f'{c} high', 'HSV settings') for c in 'HSV']
    point, raw, mask = track(frame, lower, upper)
    cv2.imshow('HSV settings', np.hstack((raw, mask)))
    return frame, point
