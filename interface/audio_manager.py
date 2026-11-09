import math
import struct
import wave
from pathlib import Path


def create_demo(path):
    """Generate an original 20-second, 120 BPM click track without downloads."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rate = 22050
    with wave.open(str(path), "wb") as stream:
        stream.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        samples = bytearray()
        for i in range(rate * 20):
            t = i / rate
            phase = t % 0.5
            frequency = 880 if int(t * 2) % 4 == 0 else 660
            value = int(10000 * math.exp(-phase * 60) * math.sin(2 * math.pi * frequency * t))
            samples.extend(struct.pack("<h", value))
        stream.writeframes(samples)


class AudioManager:
    def __init__(self, path):
        import pygame
        self.pygame = pygame
        pygame.mixer.init()
        pygame.mixer.music.load(str(path))

    def play(self):
        self.pygame.mixer.music.play()

    def busy(self):
        return self.pygame.mixer.music.get_busy()

    def stop(self):
        self.pygame.mixer.music.stop()

    def close(self):
        self.stop()
        self.pygame.mixer.quit()
