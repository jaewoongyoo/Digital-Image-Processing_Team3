"""Capture webcam frames using MediaPipe Hand Tracking (Plan A)."""
import cv2
import mediapipe as mp

class HandShapeTracker:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,  # 양손 플레이
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.mp_draw = mp.solutions.drawing_utils

    def get_hand_state(self, hand_landmarks):
        tips = [8, 12, 16, 20]
        mcps = [5, 9, 13, 17]
        folded_count = 0
        for tip, mcp in zip(tips, mcps):
            if hand_landmarks.landmark[tip].y > hand_landmarks.landmark[mcp].y:
                folded_count += 1
        return "FIST" if folded_count >= 3 else "OPEN"

    def process(self, frame):
        frame = cv2.resize(cv2.flip(frame, 1), (640, 480))
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)
        
        hands_data = []
        if results.multi_hand_landmarks and results.multi_handedness:
            for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                self.mp_draw.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                
                hand_label = handedness.classification[0].label
                h, w, _ = frame.shape
                cx = int(hand_landmarks.landmark[9].x * w)
                cy = int(hand_landmarks.landmark[9].y * h)
                
                hands_data.append({
                    "label": hand_label,
                    "center": (cx, cy),
                    "shape": self.get_hand_state(hand_landmarks)
                })
        return frame, hands_data

# 전역 트래커
tracker = None

def configure(camera):
    global tracker
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not camera.isOpened():
        raise RuntimeError('Cannot open webcam.')
        
    if tracker is None:
        tracker = HandShapeTracker()

def show_settings():
    # Plan A에서는 HSV 트랙바 창을 아예 띄우지 않습니다. (완전 공백)
    pass

def read(camera):
    global tracker
    ok, frame = camera.read()
    if not ok:
        raise RuntimeError('Webcam disconnected or frame unavailable.')
        
    processed_frame, hands_data = tracker.process(frame)
    return processed_frame, hands_data