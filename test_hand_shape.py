import cv2
import mediapipe as mp
import math

class HandShapeTracker:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.mp_draw = mp.solutions.drawing_utils

    def get_hand_state(self, hand_landmarks):
        """중심점 이동 없이, 손가락 마디의 접힘(각도)을 이용해 완벽하게 FIST 판정"""
        import math
        
        # 각 손가락의 [MCP(뿌리 관절), PIP(중간 관절), TIP(끝마디)] 인덱스
        finger_joints = [
            [5, 6, 8],    # 검지
            [9, 10, 12],  # 중지
            [13, 14, 16], # 약지
            [17, 18, 20]  # 새끼
        ]
        
        folded_count = 0
        
        for mcp, pip, tip in finger_joints:
            # 1. MCP에서 PIP까지의 벡터와 PIP에서 TIP까지의 벡터 계산
            p_mcp = hand_landmarks.landmark[mcp]
            p_pip = hand_landmarks.landmark[pip]
            p_tip = hand_landmarks.landmark[tip]
            
            # 벡터 방향을 이용해 손가락이 안쪽으로 꺾여 접혔는지 확인
            # 주먹을 쥐면 손가락 끝(tip)이 뿌리(mcp) 쪽으로 오면서 y나 x 좌표의 꺾임 패턴이 바뀝니다.
            # 간단하고 확실하게는 tip의 y가 pip보다 아래에 있거나(화면상), 
            # 손가락 마디들 간의 거리 비율을 이용할 수 있습니다.
            
            # 직관적인 관절 거리 비율 방식: (TIP과 MCP의 거리)가 (PIP와 MCP의 거리)보다 짧아지면 접힌 것!
            dist_tip_mcp = math.sqrt((p_tip.x - p_mcp.x)**2 + (p_tip.y - p_mcp.y)**2)
            dist_pip_mcp = math.sqrt((p_pip.x - p_mcp.x)**2 + (p_pip.y - p_mcp.y)**2)
            
            # 손가락을 펴면 tip-mcp 거리가 멀고, 주먹을 쥐면 tip이 안쪽으로 말려 들어가서 거리가 가까워집니다.
            if dist_tip_mcp < dist_pip_mcp * 1.2:
                folded_count += 1
                
        # 4개의 손가락 중 3개 이상이 말려 들어가 있으면 FIST 인정
        return "FIST" if folded_count >= 3 else "OPEN"

    def process(self, frame, prev_y_dict):
        frame = cv2.resize(cv2.flip(frame, 1), (640, 480))
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)
        
        hands_data = []
        current_labels = []
        
        if results.multi_hand_landmarks and results.multi_handedness:
            for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                self.mp_draw.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                
                hand_label = handedness.classification[0].label
                current_labels.append(hand_label)
                
                h, w, _ = frame.shape
                cx = int(hand_landmarks.landmark[9].x * w)
                cy = int(hand_landmarks.landmark[9].y * h)
                shape = self.get_hand_state(hand_landmarks)
                
                # 손 내리기(dy) 판정
                prev_y = prev_y_dict.get(label_key := hand_label, cy)
                dy = cy - prev_y  
                
                action = "NONE"
                
                # FIST 우선 순위 적용
                if shape == "FIST":
                    action = "HOLD (FIST)"
                elif dy > 8:  
                    action = "HIT!"
                
                prev_y_dict[label_key] = cy
                
                hands_data.append({
                    "label": hand_label,
                    "center": (cx, cy),
                    "shape": shape,
                    "action": action
                })
                
        for lbl in ["Left", "Right"]:
            if lbl not in current_labels:
                prev_y_dict[lbl] = 240
                
        return frame, hands_data

def main():
    cap = cv2.VideoCapture(0)
    tracker = HandShapeTracker()
    prev_y_dict = {"Left": 240, "Right": 240}

    print("=== 널널하게 완화된 주먹 모션 테스트 구동 중 (ESC로 종료) ===")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        processed_frame, hands_data = tracker.process(frame, prev_y_dict)
        
        for hand in hands_data:
            cx, cy = hand["center"]
            shape = hand["shape"]
            label = hand["label"]
            action = hand["action"]
            
            color = (0, 255, 0) if action == "HIT!" else ((0, 0, 255) if "HOLD" in action else (255, 255, 255))
            
            cv2.circle(processed_frame, (cx, cy), 12, color, -1)
            cv2.putText(processed_frame, f"{label}: {action}", (cx - 50, cy - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                        
        cv2.imshow("Hand Beat - Motion Test", processed_frame)
        
        if cv2.waitKey(1) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()