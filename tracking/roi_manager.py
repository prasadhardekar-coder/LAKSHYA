from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class ROIState:
    center_x: float
    center_y: float
    width: int = 64
    height: int = 64
    active: bool = True


class ROIManager:
    """Maintains a local search region around the currently tracked target."""

    def __init__(self, width: int = 64, height: int = 64, padding: int = 32) -> None:
        self.width = width
        self.height = height
        self.padding = padding
        self.state = ROIState(center_x=320.0, center_y=240.0, width=width, height=height)

    def seed(self, center: tuple[float, float]) -> ROIState:
        self.state.center_x = float(center[0])
        self.state.center_y = float(center[1])
        self.state.active = True
        return self.state

    def crop(self, frame: np.ndarray, center: tuple[float, float] | None = None) -> np.ndarray:
        if frame is None or frame.size == 0:
            return frame

        target_center = self.state if center is None else center
        cx = float(target_center[0]) if isinstance(target_center, tuple) else float(target_center.center_x)
        cy = float(target_center[1]) if isinstance(target_center, tuple) else float(target_center.center_y)

        h, w = frame.shape[:2]
        x1 = int(max(0, cx - self.width / 2.0))
        y1 = int(max(0, cy - self.height / 2.0))
        x2 = int(min(w, cx + self.width / 2.0))
        y2 = int(min(h, cy + self.height / 2.0))

        if x2 <= x1 or y2 <= y1:
            return frame

        return frame[y1:y2, x1:x2]

    def reset(self) -> None:
        self.state.active = False
