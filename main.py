"""Run with --keyboard to develop without a webcam."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description='Hand Beat prototype')
    parser.add_argument('--keyboard', action='store_true')
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--chart', type=Path, default=ROOT / 'charts/test_music.json')
    parser.add_argument('--audio-offset-ms', type=float, default=0,
                        help='Positive values delay the chart clock relative to audio play()')
    args = parser.parse_args()

    from game.session import run

    return run(args.chart, args.keyboard, args.camera, args.audio_offset_ms,
               ROOT / 'assets/demo.wav')


if __name__ == '__main__':
    raise SystemExit(main())
