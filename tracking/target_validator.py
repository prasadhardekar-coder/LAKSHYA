from __future__ import annotations

from typing import Any, Optional


class TargetValidator:
    """Simple validator for candidate detections before they enter the IMM estimator."""

    def __init__(
        self,
        min_confidence: float = 0.2,
        min_width: float = 8.0,
        min_height: float = 8.0,
        max_width: float = 500.0,
        max_height: float = 500.0,
    ) -> None:
        self.min_confidence = min_confidence
        self.min_width = min_width
        self.min_height = min_height
        self.max_width = max_width
        self.max_height = max_height

    def validate(self, detection: Optional[dict], width: int = 640, height: int = 480) -> bool:
        if not detection:
            return False

        x = float(detection.get("x", -1.0))
        y = float(detection.get("y", -1.0))
        w = float(detection.get("width", 0.0))
        h = float(detection.get("height", 0.0))
        conf = float(detection.get("confidence", 0.0))

        if not (0.0 <= x < width and 0.0 <= y < height):
            return False
        if conf < self.min_confidence:
            return False
        if w < self.min_width or h < self.min_height:
            return False
        if w > self.max_width or h > self.max_height:
            return False
        return True
