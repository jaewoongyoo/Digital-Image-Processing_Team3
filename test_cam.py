import cv2
import time
from vision.webcam import configure, show_settings, read
from gesture.gesture_detector import GestureDetector

def main():
    cap = cv2.VideoCapture(0)
    try:
        configure(cap)
    except RuntimeError as e:
        print(e)
        return

    show_settings()
    detector = GestureDetector()

    print("=== 손 위치 및 판정선 접촉 테스트 ===")
    print("화면의 선들과 손(빨간 점)이 닿는 위치를 확인하세요.")

    while True:
        try:
            frame, point = read(cap)
        except RuntimeError as e:
            print(e)
            break
            
        current_time = time.time()
        events = detector.update(point, current_time)
        
        # 1. 터미널 출력: 이벤트 발생 시 손의 y좌표 확인
        if events and point:
            for event_type, lane in events:
                if event_type == "TAP":
                    print(f"💥 [TAP 감지] 레인: {lane} | 현재 손 y좌표: {point[1]} (기준: 425 이상)")
                elif event_type == "HOLD":
                    print(f"🔄 [HOLD 유지] 레인: {lane} | 현재 손 y좌표: {point[1]} (기준: 405~479)")

        # 2. 화면 출력: 판정 가이드라인 그리기
        # 파란색: 준비선 (이 위로 올라가야 TAP 준비 완료)
        cv2.line(frame, (0, 345), (640, 345), (255, 0, 0), 2)
        cv2.putText(frame, "Ready Line (y=345)", (10, 340), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

        # 빨간색: 판정선 (이 선을 통과하며 내려쳐야 TAP)
        cv2.line(frame, (0, 425), (640, 425), (0, 0, 255), 2)
        cv2.putText(frame, "Hit Line (y=425)", (10, 420), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        # 초록색 박스: HOLD 허용 영역 (y=405 ~ 479)
        cv2.rectangle(frame, (0, 405), (640, 479), (0, 255, 0), 1)
        cv2.putText(frame, "HOLD Zone", (540, 415), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # 3. 화면 출력: 손(마커) 위치 및 현재 좌표 그리기
        if point:
            x, y = point
            cv2.circle(frame, point, 8, (0, 0, 255), -1)  # 마커 중심점 (빨간 원)
            cv2.putText(frame, f"Hand(y:{y})", (x + 15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        cv2.imshow("Gesture Contact Test", frame)
        
        if cv2.waitKey(1) & 0xFF == 27:  # ESC
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()