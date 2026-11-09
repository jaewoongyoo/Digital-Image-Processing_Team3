import cv2
from settings import HIT_Y, RESET_Y


def text(frame, label, y, scale=0.65):
    cv2.putText(frame, label, (15, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 2)


def draw(frame, game, now, state, point, fps):
    frame = (frame * 0.35).astype('uint8')
    for x in (160, 320, 480):
        cv2.line(frame, (x, 90), (x, 480), (95, 95, 95), 1)
    cv2.line(frame, (0, HIT_Y), (640, HIT_Y), (0, 220, 255), 3)
    cv2.line(frame, (0, RESET_Y), (640, RESET_Y), (100, 100, 100), 1)
    if state == 'playing':
        for note in game.notes:
            if note['state'] not in ('pending', 'holding'):
                continue
            x = note['lane'] * 160 + 80
            y = int(HIT_Y - 180 * (note['time'] - now))
            if note['type'] == 'hold':
                end_y = int(HIT_Y - 180 * (note['time'] + note['duration'] - now))
                cv2.line(frame, (x, max(-1000, end_y)), (x, min(HIT_Y, y)), (180, 100, 230), 24)
            if -20 <= y <= 480:
                cv2.rectangle(frame, (x - 55, y - 8), (x + 55, y + 8), (255, 220, 60), -1)
        text(frame, f'{now:.1f}s   {game.feedback}', 115)
    if point is not None:
        cv2.circle(frame, point, 12, (0, 255, 0), 3)
    text(frame, f'HAND BEAT   Score {game.score}   Combo {game.combo}', 30)
    text(frame, f'{fps:.0f} FPS | D F J K | ESC quit | R reset', 60, 0.5)
    if state == 'ready':
        text(frame, 'SPACE: start | Green marker: raise then strike', 170, 0.55)
    elif state == 'countdown':
        text(frame, f'Starting in {max(1, int(-now) + 1)}', 170)
    elif state == 'result':
        text(frame, f'RESULT   Max combo: {game.max_combo}', 150)
        text(frame, '  '.join(f'{k}: {v}' for k, v in game.counts.items()), 190, 0.5)
        for index, kind in enumerate(('tap', 'hold')):
            total = sum(n['type'] == kind for n in game.notes)
            text(frame, f'{kind.upper()}: {game.success[kind]}/{total}', 230 + 35 * index)
        text(frame, 'R: restart', 310)
    return frame
