# Hand Beat

- [자동 채보 도구 README](tools/README.md)
- [싱크 보정 README](README.sync.md)

OpenCV로 웹캠의 색상 마커를 추적해 플레이하는 비접촉식 4레인 리듬게임입니다. 손을 내려치는 **TAP**과 같은 위치를 유지하는 **HOLD**를 지원하며, 현재는 기본 기능을 구현한 프로토타입 단계입니다.

## 주요 기능

- HSV 색상 분할, Gaussian Blur, 모폴로지, 윤곽선 기반 마커 추적
- TAP/HOLD 판정과 PERFECT·GOOD·MISS, 점수·콤보 표시
- JSON 채보와 로컬 음원 재생, 오디오 타이밍 보정 옵션
- 카운트다운, 결과 화면, 재시작 및 키보드 테스트 모드
- 첫 실행 시 생성되는 20초 길이의 120 BPM 테스트 음원

## 요구사항 및 권장 환경

- **Python 3.12 권장**: Python 3.14 환경에서 pygame 설치 실패가 발생했으므로 팀 개발 환경은 3.12로 맞춥니다.
- Windows PowerShell 기준으로 아래 설치 명령을 안내합니다.
- 패키지: NumPy, opencv-python, pygame (`requirements.txt` 참고)
- 화면 출력이 가능한 데스크톱 환경과 오디오 출력 장치가 필요합니다.
- 웹캠 모드는 웹캠과 단색 마커(초록색 스티커 또는 장갑)가 필요합니다. 키보드 모드는 웹캠 없이 실행할 수 있습니다.

## 설치 및 실행

Python 3.12를 설치한 뒤 프로젝트 루트에서 실행합니다.

```powershell
# 가상환경 생성 및 활성화
py -3.12 -m venv .venv312
.\.venv312\Scripts\Activate.ps1

# 패키지 설치
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 키보드로 먼저 테스트
python main.py --keyboard

# 웹캠으로 플레이
python main.py
```

`py -3.12`에서 런타임을 찾지 못하면 Python 3.12를 먼저 설치해야 합니다. VS Code의 Python 인터프리터는 `.venv312\Scripts\python.exe`로 선택합니다.

PowerShell에서 가상환경 활성화가 차단되면 현재 터미널에 한해 아래 명령을 실행한 뒤 다시 활성화합니다.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 조작 방법

| 입력 | 동작 |
| --- | --- |
| `SPACE` | 3초 카운트다운 후 시작 |
| `D` / `F` / `J` / `K` | 왼쪽부터 4개 레인 타격 |
| 키를 계속 누르기 | 키보드 모드에서 HOLD 유지 |
| `R` | 초기화 후 시작 대기 |
| `ESC` | 종료 |

키보드 플레이 시 별도의 **Keyboard input** 창을 클릭해 포커스를 둡니다. 게임 화면에서도 시작·초기화·종료 키를 사용할 수 있습니다.

웹캠 플레이 시 좌우 반전된 화면에서 마커를 준비선 위로 올렸다가 판정선 아래로 내려칩니다. HOLD는 시작 타격 후 같은 레인의 홀드 영역에 마커를 유지합니다. 손바닥 모양이 아닌 **마커의 위치**를 인식합니다.

## 사용 권장사항

- 카메라는 사용자 정면에 두고, 조명이 일정하고 마커와 비슷한 색이 없는 배경에서 사용합니다.
- 기본 검출 색상은 초록색입니다. `HSV settings` 창에서 환경에 맞게 범위를 조절합니다. 왼쪽은 HSV 마스크, 오른쪽은 모폴로지 적용 결과입니다.
- 처리 좌표는 640×480 기준입니다. 준비선은 y=260, 판정선은 y=340이며 HOLD 영역은 해당 레인의 y=320~479입니다.
- HOLD 중 검출 누락·영역 이탈은 최대 약 0.2초까지 허용합니다. 한 손 플레이를 기준으로 채보를 작성합니다.
- 실제 웹캠 인식률, FPS, 오디오 지연은 장치별 확인이 필요합니다. 장시간 오디오 드리프트 자동 보정은 아직 구현하지 않았습니다.

```powershell
# 다른 카메라 사용
python main.py --camera 1

# 차트 시계를 음원 재생 호출보다 100ms 늦춤
python main.py --audio-offset-ms 100

# 120 BPM 데모를 듣고 SPACE로 입력 싱크 보정
python main.py --calibrate

# 다른 채보 사용
python main.py --chart charts/my_song.json
```

싱크 보정 창에서 `SPACE`로 데모를 시작하고, 처음 네 박을 들은 뒤 클릭마다 `SPACE`를 누릅니다. 결과에서 `Enter`를 누르면 로컬 보정값을 저장하고 이후 실행에 자동 적용합니다. `R`은 다시 측정, `Esc`는 취소입니다. `--audio-offset-ms 0`처럼 값을 직접 지정하면 해당 실행에서 저장값을 덮어씁니다. 이 값은 키보드로 측정하며 웹캠 추적 지연은 별도로 측정해야 합니다.

## 음원 및 채보

기본 채보는 `charts/test_music.json`이며, 테스트 음원 `assets/demo.wav`는 첫 실행 시 자동 생성됩니다. 다른 MP3/WAV 파일을 사용하려면 채보의 `audio`와 `notes`를 수정합니다. 음원 경로는 **채보 파일이 있는 폴더 기준**입니다.

```json
{
  "title": "My Song",
  "audio": "../assets/my_song.wav",
  "notes": [
    {"id": 1, "type": "tap", "lane": 0, "time": 2.0},
    {"id": 2, "type": "hold", "lane": 1, "time": 4.0, "duration": 2.0}
  ]
}
```

`lane`은 왼쪽부터 0~3, `time`은 음악 시작 기준 타격 시각(초), `duration`은 HOLD 길이(초)입니다. ID는 중복되지 않아야 합니다. 키보드 모드에서는 서로 다른 레인의 동시 TAP·HOLD를 지원합니다. 웹캠 모드는 한 손 플레이를 기준으로 모든 레인의 노트가 서로 겹치지 않아야 합니다. 외부 음원은 사용·공유 가능한 라이선스를 확인합니다.

## 프로젝트 구조

```text
main.py         전체 실행 및 모듈 연결
vision/         영상처리와 마커 추적
gesture/       TAP 검출과 타이밍 판정
game/          채보 로드, 노트 상태, 점수·콤보
interface/     음원 재생과 화면 출력
charts/        JSON 채보
tests/         핵심 로직 테스트
```

## 테스트 및 협업

```powershell
python -m unittest discover -s tests -v
```

테스트는 판정 경계, TAP 중복 방지, 추적 누락, HOLD 성공·실패와 자동 MISS를 확인합니다. 웹캠과 오디오의 실제 동작은 별도로 확인해야 합니다.

기능별 브랜치에서 작업하고, 변경사항을 확인한 뒤 `main`에 병합합니다. 가상환경 폴더와 자동 생성 음원은 `.gitignore`에 따라 커밋하지 않습니다.
