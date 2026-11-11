"""Camera coordinates use a mirrored 640 x 480 frame."""


# class GestureDetector:
#     def __init__(self, hit_y=340, reset_y=260, min_speed=180):
#         self.hit_y, self.reset_y, self.min_speed = hit_y, reset_y, min_speed
#         self.ready = False
#         self.previous = None

#     def update(self, point, timestamp, locked=False):
#         if point is None or locked:
#             self.previous = None
#             self.ready = False
#             return None
#         x, y = point
#         lane = min(3, max(0, int(x // 160)))
#         if y < self.reset_y:
#             self.ready = True
#         event = None
#         if self.previous is not None:
#             _, old_y, old_t = self.previous
#             dt = timestamp - old_t
#             if (self.ready and 0 < dt <= 0.15 and old_y < self.hit_y <= y
#                     and (y - old_y) / dt >= self.min_speed):
#                 self.ready = False
#                 event = lane
#         self.previous = (x, y, timestamp)
#         return event

"""Camera coordinates use a mirrored 640 x 480 frame."""

class GestureDetector:
    # README 기준 좌표로 기본값 업데이트: 준비선 345, 판정선 425, HOLD 영역 405~479
    def __init__(self, hit_y=425, reset_y=345, hold_min=405, hold_max=479, min_speed=180):
        self.hit_y = hit_y
        self.reset_y = reset_y
        self.hold_min = hold_min
        self.hold_max = hold_max
        self.min_speed = min_speed
        
        self.ready = False
        self.previous = None
        
        # HOLD 유지를 위한 추가 상태 변수
        self.current_hold_lane = None
        self.missing_start_time = None
        self.max_missing_duration = 0.2  # 최대 0.2초 검출 누락 허용 (README 요구사항)

    def update(self, point, timestamp, locked=False):
        events = []  # 반환할 이벤트 리스트 (예: [("TAP", 1), ("HOLD", 1)])

        # 1. 마커를 놓쳤을 때 (프레임 누락 방어)
        if point is None or locked:
            if self.current_hold_lane is not None:
                if self.missing_start_time is None:
                    self.missing_start_time = timestamp
                
                # 누락 시간이 0.2초를 초과하면 HOLD 실패 처리 및 초기화
                if (timestamp - self.missing_start_time) > self.max_missing_duration:
                    events.append(("HOLD_MISS", self.current_hold_lane))
                    self._reset_state()
            else:
                self._reset_state()
                
            return events if events else None

        x, y = point
        lane = min(3, max(0, int(x // 160)))

        # 2. 마커를 정상적으로 다시 찾았으므로 누락 타이머 초기화
        if self.current_hold_lane == lane:
            self.missing_start_time = None

        # 3. 손을 준비선(reset_y) 위로 올림 -> TAP 준비 및 기존 HOLD 종료
        if y < self.reset_y:
            self.ready = True
            if self.current_hold_lane is not None:
                self.current_hold_lane = None
                self.missing_start_time = None

        # 4. 기존 팀의 속도 기반 TAP 판정 + HOLD 판정
        if self.previous is not None:
            _, old_y, old_t = self.previous
            dt = timestamp - old_t

            # [TAP 판정] 속도가 min_speed 이상이고 판정선을 돌파했을 때
            if (self.ready and 0 < dt <= 0.15 and old_y < self.hit_y <= y
                    and (y - old_y) / dt >= self.min_speed):
                self.ready = False
                self.current_hold_lane = lane  # TAP 성공 시 자동으로 HOLD 유지 상태로 진입
                events.append(("TAP", lane))

            # [HOLD 판정] 현재 레인에서 손이 HOLD 영역에 머무르고 있을 때
            elif self.current_hold_lane == lane and self.hold_min <= y <= self.hold_max:
                events.append(("HOLD", lane))

        self.previous = (x, y, timestamp)
        return events if events else None

    def _reset_state(self):
        """인식 완전 실패 시 상태를 초기화하는 헬퍼 메서드"""
        self.previous = None
        self.ready = False
        self.current_hold_lane = None
        self.missing_start_time = None