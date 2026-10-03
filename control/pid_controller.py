from __future__ import annotations

import math


class PIDController:
    """Simple PID controller used for pan/tilt rate commands."""

    def __init__(self, kp: float, ki: float, kd: float, max_output: float) -> None:
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.max_output = max_output
        self.integral = 0.0
        self.previous_error = 0.0

    def update(self, error: float, dt: float) -> float:
        self.integral += error * dt
        derivative = 0.0 if dt <= 0.0 else (error - self.previous_error) / dt
        output = self.kp * error + self.ki * self.integral + self.kd * derivative
        self.previous_error = error
        return max(-self.max_output, min(self.max_output, output))

    def reset(self) -> None:
        self.integral = 0.0
        self.previous_error = 0.0


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def angle_from_pixel_error(pixel_error: float, image_width: int = 640, hfov_rad: float = 1.2) -> float:
    if image_width <= 0:
        return 0.0
    px_per_rad = image_width / (2.0 * math.tan(hfov_rad / 2.0))
    return pixel_error / px_per_rad if px_per_rad > 0 else 0.0
