"""Run a Hand Beat session and manage its resources."""
import sys
import time
from pathlib import Path
import traceback

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
        print(">>> [시스템] 차트 및 오디오 로딩 중...")
        chart = load_chart(chart_path)
        if Path(chart['audio']).resolve() == demo_path.resolve() and not demo_path.exists():
            create_demo(demo_path)
        audio = AudioManager(chart['audio'])
        
        if not keyboard:
            print(">>> [시스템] 미디어파이프 카메라 연동 중...")
            camera = cv2.VideoCapture(camera_index)
            webcam.configure(camera)
            
        cv2.namedWindow('Hand Beat')
        if camera is not None:
            webcam.show_settings()
            
        print(">>> [시스템] 게임 화면 진입 성공! 화면이 켜지면 키보드를 눌러 시작하세요!")
        play(chart['notes'], audio, camera, audio_offset_ms / 1000)
        
    except Exception as exc:
        print(f'\n🚨 [런처 치명적 에러] {exc}\n')
        traceback.print_exc()  # 에러 절대 숨기지 않음
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
    try:
        game, detector = GameManager(notes), GestureDetector()
        state, start, previous = 'ready', 0.0, time.monotonic()
        prev_shapes = {"Left": "OPEN", "Right": "OPEN"}
        
        while True:
            stamp = time.monotonic()
            fps = 1 / max(stamp - previous, 1e-6)
            previous = stamp
            
            if camera is None:
                frame, hands_data = np.zeros((480, 640, 3), dtype=np.uint8), []
            else:
                frame, hands_data = webcam.read(camera)

            # 🛡️ [안전장치] 만약 hands_data가 None으로 들어와도 에러 안 나게 빈 리스트로 방어!
            if hands_data is None:
                hands_data = []

            controls = keyboard_input.poll()
            if controls.quit_requested:
                break
            if controls.reset:
                audio.stop()
                game, detector = GameManager(notes), GestureDetector()
                state = 'ready'
                prev_shapes = {"Left": "OPEN", "Right": "OPEN"}
                
            # [시작 키] 스페이스바 등을 누르면 Ready에서 카운트다운으로 넘어감
            if controls.begin and state == 'ready':
                print(">>> [시스템] 카운트다운 시작!")
                start, state = stamp + 3, 'countdown'
                
            if state == 'countdown' and stamp >= start:
                audio.play()
                start = time.monotonic()
                stamp = start
                state = 'playing'

            now = stamp - start - audio_offset
            
            # UI 크로스헤어 충돌 방지용 변수
            ui_point = None 
            
            if state in ('playing', 'ready'):
                held = None
                
                # 키보드 모드일 때
                if camera is None:
                    held = keyboard_input.held_lane()
                    lane = detector.update(None, stamp, game.active is not None)
                    if lane is not None and state == 'playing':
                        game.hit(lane, now)
                
                # 미디어파이프 카메라 모드일 때
                else:
                    current_labels = []
                    for hand in hands_data:
                        cx, cy = hand["center"]
                        shape = hand["shape"]
                        label = hand["label"]
                        current_labels.append(label)
                        
                        # 인식된 첫 번째 손의 중심점을 UI 타겟(십자선)으로 할당
                        if ui_point is None:
                            ui_point = (cx, cy)
                        
                        lane = min(3, max(0, cx // 160))
                        
                        # 판정 존 (y=350 ~ 480)
                        if 350 <= cy <= 480:
                            if shape == "FIST":
                                held = lane # 홀드 노트용 유지
                                
                                # 💡 [핵심] 방금 전까지 보(OPEN)였다가 '방금 주먹(FIST)을 쥔 순간'에만 딱 1번 타격!
                                if state == 'playing' and prev_shapes.get(label, "OPEN") == "OPEN":
                                    print(f"🎯 [HIT!] 레인 {lane} 타격 성공! (시간: {now:.2f})")
                                    game.hit(lane, now)
                                    
                        # 이번 프레임의 손 모양을 기억해 둠
                        prev_shapes[label] = shape
                        
                    # 화면 밖으로 나간 손은 OPEN 상태로 리셋
                    for lbl in ["Left", "Right"]:
                        if lbl not in current_labels:
                            prev_shapes[lbl] = "OPEN"
                
                for hit_lane in controls.pressed:
                    if state == 'playing':
                        game.hit(hit_lane, now)
                        
                if state == 'playing':
                    game.update(now, held)
                    
                if game.finished and not audio.busy():
                    state = 'result'
                    
            # 대기(Ready) 상태일 때 화면에 시작 안내 문구 강제 출력!
            if state == 'ready':
                cv2.putText(frame, "PRESS SPACE TO START!", (100, 240), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 4)

            # ui_point를 안전하게 넘겨서 화면 출력
            drawn_frame = draw(frame, game, now, state, ui_point, fps)
            cv2.imshow('Hand Beat', drawn_frame)
            
    except Exception as e:
        print(f'\n🚨 [게임 루프 치명적 에러] {e}\n')
        traceback.print_exc()