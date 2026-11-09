"""Run with --keyboard to develop without a webcam."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description='Hand Beat prototype')
    parser.add_argument('--keyboard', action='store_true')
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--chart', type=Path, default=ROOT / 'charts/test_music.json')
    parser.add_argument('--audio-offset-ms', type=float,
                        help='Override calibration. Positive values delay the chart clock.')
    parser.add_argument('--calibrate', action='store_true',
                        help='Tap along to the demo and save a sync offset')
    args = parser.parse_args()

    from game.sync_offset import load_offset

    demo = ROOT / 'assets/demo.wav'
    profile = ROOT / '.sync-calibration.json'
    if args.calibrate:
        from interface.calibration import run_calibration

        return run_calibration(demo, profile)

    offset = args.audio_offset_ms
    if offset is None:
        offset = load_offset(profile)
    from game.session import run

    return run(args.chart, args.keyboard, args.camera, offset, demo)


if __name__ == '__main__':
    raise SystemExit(main())
