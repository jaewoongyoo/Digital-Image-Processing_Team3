"""Run Hand Beat with Plan A (MediaPipe Dual-Hand & Fist Tracking)."""
import argparse
import sys
from pathlib import Path
import cv2

ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description='Hand Beat - Plan A (MediaPipe)')
    # 키보드 모드 플래그는 백업용으로 남겨두되, 기본 카메라는 0번(웹캠)으로 고정합니다.
    parser.add_argument('--keyboard', action='store_true', help='Use keyboard simulation instead of webcam')
    parser.add_argument('--camera', type=int, default=0, help='Webcam device index (default: 0)')
    parser.add_argument('--chart', type=Path, default=ROOT / 'charts/test_music.json')
    parser.add_argument('--audio-offset-ms', type=float, default=0,
                        help='Positive values delay the chart clock relative to audio play()')
    args = parser.parse_args()

    from game.session import run

    print("=== [Hand Beat] Plan A 모드로 실행합니다 ===")
    return run(args.chart, args.keyboard, args.camera, args.audio_offset_ms,
               ROOT / 'assets/demo.wav')

if __name__ == '__main__':
    sys.exit(main())