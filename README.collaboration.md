# Hand Beat 팀 협업 가이드

팀원이 자동 채보와 싱크 보정을 자신의 기능에 연결하거나, AI에게 관련 코드 수정을 맡길 때 참고하는 문서입니다. 명령은 프로젝트 루트에서 실행합니다.

## 기존 기능 가져다 쓰기

| 작업 | 사용할 진입점 | 구현 참고 |
| --- | --- | --- |
| 음원으로 채보 생성 | `python tools/auto_chart.py <음원> -o <새 채보.json>` | [자동 채보 도구](tools/README.md) |
| 생성한 채보 재생 | `python main.py --chart <채보.json>` | 카메라 없이 테스트할 때 `--keyboard` 추가 |
| UI에서 채보 목록 또는 미리보기 로드 | `game.note_manager.load_chart(path, single_hand=...)` | 웹캠은 `True`, 키보드는 `False` |
| 사용자 싱크 보정 | `python main.py --calibrate` | [싱크 보정 사용법](README.sync.md) |

### 자동 채보와 곡 선택 연결

```powershell
python tools/auto_chart.py "assets/Quatre sur le sol.mp3" -o charts/quatre_team_test.json --difficulty normal
python main.py --keyboard --chart charts/quatre_team_test.json
```

곡 선택 기능에서는 생성된 JSON 경로를 기존 게임 진입점에 전달합니다. 미리보기에 채보 데이터가 필요하면 게임과 같은 로더를 호출합니다.

```python
from game.note_manager import load_chart

chart = load_chart(selected_chart_path, single_hand=not keyboard_mode)
audio_path = chart["audio"]
notes = chart["notes"]
```

- `audio`의 상대 경로 기준은 **채보 파일이 들어 있는 폴더**입니다. 로더가 반환한 음원 경로를 사용합니다.
- `notes`의 `id`는 채보 내에서 고유해야 합니다. `lane`은 왼쪽부터 0~3, `time`은 곡 시작 기준 초, HOLD의 `duration`은 양의 초 단위입니다.
- 키보드 모드는 서로 다른 레인의 노트 겹침을 허용합니다. 웹캠 모드는 전체 레인에서 겹침을 금지합니다. 양쪽에서 쓸 채보는 웹캠 기준으로도 로드해 확인합니다.
- `bpm`, `beat_offset`, `bpm_confidence`는 분석 메타데이터입니다. 구형 채보에는 없을 수 있고 BPM을 결정하기 어려우면 `null`일 수 있으므로, 표시용 UI는 값이 없는 경우도 처리합니다. 플레이 타이밍은 각 노트의 `time`을 사용합니다.

### 싱크 보정 연결

기본 실행은 프로젝트 루트의 `.sync-calibration.json`에서 보정값을 읽습니다. `--audio-offset-ms`를 직접 주면 그 실행에서 저장값보다 우선합니다. `0`을 주면 저장한 보정을 이번 실행에 적용하지 않습니다.

별도 실행 진입점이 필요하면 `game.sync_offset.load_offset(profile_path)`를 사용합니다. 반환값은 **밀리초**이고, 양수는 채보 시계를 늦춥니다. 기존 게임 세션을 호출할 때는 밀리초 그대로 전달합니다. 채보의 `time`을 미리 이동시키면 세션에서 보정이 한 번 더 적용됩니다. `beat_offset`은 곡의 박자 위치 추정값이므로 기기·사용자 보정값과 따로 취급합니다. 사용자별 보정 파일은 커밋에서 제외합니다.

## 수정 범위 정하기

| 요청 | 우선 확인할 파일 | 팀과 먼저 합의할 변경 |
| --- | --- | --- |
| BPM, 타격 검출, 난이도, 레인 배치 | `tools/auto_chart.py`, `tools/beat_timing.py`, `tests/test_auto_chart.py` | 채보 필드·시간 단위 변경, 로더 호환성 변경 |
| 보정 화면, 입력 샘플링, 저장 | `interface/calibration.py`, `game/sync_offset.py`, `main.py` | 오프셋 부호·우선순위 변경, 게임 시계 변경 |
| 곡 선택 UI, 게임 화면, 웹캠 | 해당 기능의 코드와 위 진입점 | 공용 로더, 채보 형식, 판정 시계에 영향을 주는 변경 |

자동 채보를 조정할 때는 기존 비교 채보를 보존하고 새 파일명으로 생성합니다. 노트가 특정 곡이나 구간에서만 어긋나면 음원·채보 경로와 문제 구간을 기록합니다. 여러 곡에서 비슷한 양만큼 밀리면 보정값을 확인합니다. 웹캠에서만 지연이 느껴지면 키보드 테스트와 비교해 카메라 추적 지연을 따로 확인합니다.

## AI에 전달할 작업 요청 예시

```text
현재 로컬 Hand Beat 프로젝트에서 [수정할 기능]을 수정해줘.
README.collaboration.md와 관련 기능 README를 먼저 확인해.

허용 범위는 [파일/폴더]야. 다른 담당 영역이나 공용 계약의 변경이
필요하면, 필요한 변경과 영향을 먼저 알려줘.

입력 음원/채보는 [경로], 재현 방법은 [실행 명령과 문제 구간]이야.
채보는 기존 JSON 스키마와 초 단위를 유지하고, 새 결과는 별도 파일명으로 저장해.
싱크 보정은 저장값과 CLI 덮어쓰기 우선순위, 밀리초 단위를 유지해.

단위 테스트와 관련 실행 경로를 확인한 뒤 변경 파일과 검증 결과를 요약해줘.
자동 채보를 바꿨다면 같은 음원·옵션에서 BPM, 노트 수, 레인 분포,
타격과 노트 시각 차이를 비교해줘.
```

```powershell
python -m unittest discover -s tests -v
```

PR에는 수정 범위, 실행한 명령, 확인한 결과를 적습니다. 채보 변경은 같은 음원·옵션으로 비교하고, 보정 변경은 저장값 사용과 `--audio-offset-ms 0`의 명시적 덮어쓰기를 함께 확인합니다.
