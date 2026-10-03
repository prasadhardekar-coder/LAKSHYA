from __future__ import annotations

from typing import Optional

import cv2
import numpy as np


class OpenCVFastDetector:
    """Primary fast detector for the cyan beacon in a 640x480 frame."""

    def __init__(
        self,
        hsv_lower: tuple[int, int, int] = (75, 100, 100),
        hsv_upper: tuple[int, int, int] = (105, 255, 255),
        min_area: float = 3.0,
    ) -> None:
        self.hsv_lower = np.array(hsv_lower, dtype=np.uint8)
        self.hsv_upper = np.array(hsv_upper, dtype=np.uint8)
        self.min_area = min_area

    def detect(self, frame: np.ndarray) -> Optional[dict]:
        if frame is None or frame.size == 0:
            return None

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)

        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        if area < self.min_area:
            return None

        moments = cv2.moments(largest)
        if moments["m00"] == 0:
            return None

        x = int(moments["m10"] / moments["m00"])
        y = int(moments["m01"] / moments["m00"])

        x, y, w, h = cv2.boundingRect(largest)
        return {
            "x": float(x + w / 2.0),
            "y": float(y + h / 2.0),
            "width": float(w),
            "height": float(h),
            "confidence": 1.0,
            "class_id": 0,
        }
