from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np


class AIVerifier:
    """YOLO-based fallback detector for beacon reacquisition."""

    def __init__(
        self,
        weights: str | Path = "models/yolov8n.pt",
        confidence: float = 0.35,
        device: str = "cpu",
        image_size: int = 640,
    ) -> None:
        self.weights = Path(weights)
        self.confidence = confidence
        self.device = device
        self.image_size = image_size
        self.model = None

    def load(self):
        try:
            from ultralytics import YOLO
        except Exception as exc:  # pragma: no cover - depends on optional runtime
            raise RuntimeError(
                "ultralytics is not installed. Install with: python -m pip install ultralytics"
            ) from exc

        model_path = str(self.weights)
        if not self.weights.exists() and self.weights.name:
            model_path = self.weights.name

        self.model = YOLO(model_path)
        return self.model

    def detect(self, frame: np.ndarray, target_center: Optional[tuple[float, float]] = None):
        if frame is None:
            return None

        if self.model is None:
            try:
                self.load()
            except Exception:
                return None

        try:
            results = self.model.predict(
                frame,
                conf=self.confidence,
                imgsz=self.image_size,
                device=self.device,
                verbose=False,
            )
        except Exception:
            return None

        if not results:
            return None

        result = results[0]
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return None

        detections = []
        h, w = frame.shape[:2]

        for box in boxes:
            xyxy = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls = int(box.cls[0])

            if conf < self.confidence:
                continue

            x1, y1, x2, y2 = xyxy
            sx = 640.0 / float(w)
            sy = 480.0 / float(h)
            x1 *= sx
            x2 *= sx
            y1 *= sy
            y2 *= sy
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            det = {
                "x": cx,
                "y": cy,
                "width": max(0.0, x2 - x1),
                "height": max(0.0, y2 - y1),
                "confidence": conf,
                "class_id": cls,
            }
            detections.append(det)

        if not detections:
            return None

        if target_center is not None:
            def score(item: dict) -> float:
                score_value = float(item["confidence"])
                x = float(item["x"])
                y = float(item["y"])
                dx = abs(x - target_center[0])
                dy = abs(y - target_center[1])
                score_value -= (dx + dy) / 200.0
                return score_value

            best = max(detections, key=score)
            return best

        return max(detections, key=lambda item: float(item["confidence"]))
