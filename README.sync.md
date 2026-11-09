# Hand Beat 싱크 보정

120 BPM 데모 클릭을 듣고 키보드를 누른 시각과 예상 박자 사이의 차이를 측정합니다. 측정값을 저장하면 게임이 이후 실행에서 채보 시계에 적용합니다.

## 보정하기

프로젝트 루트에서 실행합니다.

```powershell
python main.py --calibrate
```

1. 보정 창에서 `Space`를 눌러 데모를 시작합니다.
2. 처음 네 박을 들은 뒤 클릭마다 `Space`를 누릅니다. 같은 박에 여러 번 눌러도 첫 유효 입력만 기록합니다.
3. 결과에서 `Enter`로 저장합니다. `R`은 다시 측정, `Esc`는 저장 없이 닫기입니다.

가장 가까운 예상 박자에서 ±200ms 안에 들어온 입력을 최대 12개 모아 시차의 중앙값을 계산합니다. 데모가 끝날 때 유효 입력이 8개 미만이면 다시 측정해야 합니다.

## 저장값과 수동 지정

보정값은 프로젝트 루트의 `.sync-calibration.json`에 밀리초 단위로 저장됩니다. `+65ms`는 채보 시계를 65ms 늦추고, 음수는 채보 시계를 앞당깁니다. 음원과 채보 파일의 내용은 그대로입니다.

```powershell
# 저장값으로 플레이
python main.py --keyboard --chart charts/quatre_sur_le_sol.json

# 이번 실행에서만 +65ms 적용
python main.py --keyboard --chart charts/quatre_sur_le_sol.json --audio-offset-ms 65

# 이번 실행에서만 보정 없이 플레이
python main.py --keyboard --audio-offset-ms 0
```

이 값은 실제로 클릭을 듣고 키를 누르는 과정 전체의 차이를 반영합니다. 웹캠 모드에도 저장값이 적용되지만, 측정 과정에는 웹캠 추적 지연이 포함되지 않습니다. 곡이 진행되면서 싱크가 점점 벌어지는 경우에는 일정한 오프셋 하나로 보정하기 어렵습니다.
