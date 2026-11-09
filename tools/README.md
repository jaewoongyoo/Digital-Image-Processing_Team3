# Hand Beat 자동 채보

WAV·MP3 음원에서 타격음 후보를 찾고 Hand Beat에서 읽을 수 있는 TAP 채보를 생성합니다. 프로젝트 루트에서 실행합니다.

```powershell
python -m pip install -r requirements.txt
python tools/auto_chart.py "assets/Quatre sur le sol.mp3" -o charts/quatre_custom.json
python main.py --keyboard --chart charts/quatre_custom.json
```

| 인자 | 동작 |
| --- | --- |
| `audio` | 분석할 음원 파일 경로 |
| `-o`, `--output` | 필수. 생성할 JSON 경로. 기존 파일을 덮어쓰지 않습니다. |
| `--min-gap` | 노트 사이 최소 간격. 기본값은 0.25초이며, 값을 키우면 노트 밀도가 낮아집니다. |
| `--lead-in` | 첫 노트를 배치할 수 있는 곡 시각. 기본값은 1초입니다. |

## 노트 선택 방식

1. 음원을 네 주파수 대역으로 나눠 소리가 급격히 커지는 지점을 찾습니다.
2. 감지 지점의 반복 간격으로 BPM을 추정합니다. 박자 그리드가 뚜렷하면 그리드에 가깝고 주변 박에서도 반복되는 타격음에 우선순위를 줍니다.
3. 최소 간격을 지키면서 후보를 고릅니다. 주파수 대역별 반응과 최근 레인 사용량으로 레인을 배정하며, 같은 레인은 최대 세 번 연속 배치합니다.

JSON의 `audio`는 채보 파일 기준 상대 경로입니다. Windows에서 음원과 채보가 다른 드라이브에 있으면 절대 경로를 저장합니다. `notes`에는 `id`, `type`, `lane`, `time`이 들어갑니다. `time`은 곡 시작부터의 초이며, 레인은 왼쪽부터 0~3입니다.

`bpm`, `beat_offset`, `duration`도 분석 정보로 저장합니다. BPM 추정이 어려워도 타격음 후보가 있으면 채보를 생성하며, 이때 `bpm`과 `beat_offset`은 `null`입니다. 현재는 단일 템포를 가정하고 TAP만 생성합니다. 노트는 감지된 소리 시각을 유지하므로 그리드에 가까운 노트도 강제로 이동하지 않습니다.

재생 환경의 타이밍 차이는 [싱크 보정 README](../README.sync.md)에서 확인할 수 있습니다.
