from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np


class AIRecoveryNode:
    """
    YOLO-based fallback detector for the Godot tracking loop.

    This node is intentionally used as a recovery path only:
    OpenCV handles the normal fast path and AI is used when classical
    detection fails or drifts too far from the expected target region.
    """

    def __init__(
        self,
        model_path: str | Path = "models/yolov8n.pt",
        confidence: float = 0.35,
        image_size: int = 640,
        max_attempts: int = 3,
    ) -> None:
        self.model_path = Path(model_path)
        self.confidence = confidence
        self.image_size = image_size
        self.max_attempts = max_attempts
        self.recovery_calls = 0
        self.model = None

    def load(self):
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"YOLO weights not found: {self.model_path}"
            )

        try:
            from ultralytics import YOLO
        except Exception as exc:  # pragma: no cover - depends on installed extras
            raise RuntimeError(
                "ultralytics is not installed. Install with: python -m pip install ultralytics"
            ) from exc

        self.model = YOLO(str(self.model_path))
        return self.model

    @staticmethod
    def _normalize_detection(frame: np.ndarray, box: Sequence[float]) -> Dict[str, float]:
        x1, y1, x2, y2 = [float(v) for v in box]
        h, w = frame.shape[:2]

        if w <= 0 or h <= 0:
            raise ValueError("Frame dimensions must be positive.")

        sx = 640.0 / float(w)
        sy = 480.0 / float(h)

        x1 *= sx
        x2 *= sx
        y1 *= sy
        y2 *= sy

        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0

        return {
            "x": cx,
            "y": cy,
            "width": max(0.0, x2 - x1),
            "height": max(0.0, y2 - y1),
        }

    def select_best_detection(
        self,
        detections: Sequence[Dict[str, Any]],
        target_center: Optional[Tuple[float, float]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not detections:
            return None

        def score(det: Dict[str, Any]) -> float:
            score_value = float(det.get("confidence", 0.0))

            if target_center is not None:
                x = float(det.get("x", 0.0))
                y = float(det.get("y", 0.0))
                dx = abs(x - target_center[0])
                dy = abs(y - target_center[1])
                score_value -= (dx + dy) / 200.0

            width = float(det.get("width", 0.0))
            height = float(det.get("height", 0.0))
            area = width * height
            if area > 0:
                score_value += min(area / 5000.0, 0.15)

            return max(score_value, 0.0)

        return max(detections, key=score)

    def detect(
        self,
        frame: np.ndarray,
        target_center: Optional[Tuple[float, float]] = None,
    ) -> Optional[Dict[str, Any]]:
        if frame is None:
            return None

        if self.recovery_calls >= self.max_attempts:
            return None

        try:
            if self.model is None:
                self.load()

            results = self.model.predict(
                frame,
                conf=self.confidence,
                imgsz=self.image_size,
                verbose=False,
            )
        except FileNotFoundError:
            return None
        except Exception:
            return None

        self.recovery_calls += 1

        if not results:
            return None

        result = results[0]
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return None

        detections = []
        for box in boxes:
            xyxy = getattr(box, "xyxy", None)
            conf = getattr(box, "conf", None)
            cls = getattr(box, "cls", None)

            if xyxy is None or conf is None or len(conf) == 0:
                continue

            if float(conf[0]) < self.confidence:
                continue

            normalized = self._normalize_detection(frame, xyxy[0].tolist())
            normalized["confidence"] = float(conf[0])
            normalized["class_id"] = int(cls[0]) if cls is not None and len(cls) > 0 else -1
            detections.append(normalized)

        if not detections:
            return None

        best = self.select_best_detection(detections, target_center=target_center)
        if best is None:
            return None

        if target_center is not None:
            best["distance_from_target"] = (
                abs(best["x"] - target_center[0])
                + abs(best["y"] - target_center[1])
            )

        return best
