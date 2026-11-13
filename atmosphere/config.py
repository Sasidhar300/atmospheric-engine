from dataclasses import dataclass
from pathlib import Path
import math

import yaml


@dataclass(frozen=True)
class Scene:
    data: dict
    width: int
    height: int
    fps: int
    duration: float

    @property
    def seed(self):
        return self.data.get("seed", 431)

    @property
    def frames(self):
        return round(self.duration * self.fps)


def load(path, duration=None, preview=False):
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError("Scene must be a mapping")
    resolution = (1280, 720) if preview else data.get("resolution", [1920, 1080])
    if not isinstance(resolution, (tuple, list)) or len(resolution) != 2:
        raise ValueError("Resolution must contain width and height")
    width, height = resolution
    fps = data.get("fps", 30)
    duration = float(data.get("duration", 90) if duration is None else duration)
    if any(type(size) is not int or size < 64 or size % 2 for size in (width, height)):
        raise ValueError("Resolution must use positive even integer dimensions of at least 64")
    if type(fps) is not int or fps < 1 or 48000 % fps:
        raise ValueError("FPS must be an integer divisor of 48000")
    if not math.isfinite(duration) or duration < 1 or not math.isclose(duration * fps, round(duration * fps), abs_tol=1e-8):
        raise ValueError("Duration must be at least one second and frame-aligned")
    for name in ("windows", "occlusion"):
        for polygon in data.get(name, []):
            if len(polygon) < 3 or any(len(point) != 2 or not all(0 <= x <= 1 for x in point) for point in polygon):
                raise ValueError(f"Invalid normalized polygon in {name}")
    if type(data.get("seed", 431)) is not int or data.get("seed", 431) < 0:
        raise ValueError("Seed must be a nonnegative integer")
    return Scene(data, width, height, fps, duration)
