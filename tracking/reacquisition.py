from __future__ import annotations

from typing import Optional, Tuple

import numpy as np


class ReacquisitionManager:
    """Coordinate AI recovery with a short bounded retry window."""

    def __init__(self, max_attempts: int = 3) -> None:
        self.max_attempts = max_attempts
        self.attempts = 0

    def reset(self) -> None:
        self.attempts = 0

    def try_reacquire(
        self,
        frame: np.ndarray,
        ai_detector,
        predicted_center: Optional[Tuple[float, float]] = None,
    ) -> Optional[dict]:
        if self.attempts >= self.max_attempts:
            return None

        result = ai_detector.detect(frame, target_center=predicted_center)
        self.attempts += 1

        if result is None:
            return None

        return result
