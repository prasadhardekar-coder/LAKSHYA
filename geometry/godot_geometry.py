from __future__ import annotations

import math


def pixel_error_to_angle(pixel_error: float, image_width: int = 640, hfov_rad: float = 1.2) -> float:
    if image_width <= 0:
        return 0.0
    px_per_rad = image_width / (2.0 * math.tan(hfov_rad / 2.0))
    return pixel_error / px_per_rad if px_per_rad > 0 else 0.0


def camera_center(image_width: int = 640, image_height: int = 480) -> tuple[float, float]:
    return float(image_width / 2.0), float(image_height / 2.0)
