from __future__ import annotations

import numpy as np


class IMMTracker:
    """Simple IMM filter for position and velocity tracking.

    This is intentionally lightweight: it provides the position estimate used by the
    control loop without introducing a second independent tracker stack.
    """

    def __init__(self, dt: float = 1.0 / 30.0) -> None:
        self.dt = dt
        self.state = np.zeros(4, dtype=np.float64)
        self.P = np.eye(4, dtype=np.float64) * 25.0
        self.cv_weight = 0.7
        self.ct_weight = 0.3

    def _cv_transition(self) -> np.ndarray:
        return np.array(
            [
                [1.0, 0.0, self.dt, 0.0],
                [0.0, 1.0, 0.0, self.dt],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )

    def _ct_transition(self) -> np.ndarray:
        return np.array(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )

    def _measurement_matrix(self) -> np.ndarray:
        return np.array(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
            ],
            dtype=np.float64,
        )

    def predict(self) -> np.ndarray:
        cv_model = self._cv_transition()
        ct_model = self._ct_transition()

        cv_pred = cv_model @ self.state
        ct_pred = ct_model @ self.state

        self.state = self.cv_weight * cv_pred + self.ct_weight * ct_pred
        self.P = self.cv_weight * self.P + self.ct_weight * self.P
        return self.state.copy()

    def update(self, measurement: tuple[float, float] | None) -> np.ndarray:
        if measurement is None:
            return self.predict()

        meas = np.array([measurement[0], measurement[1]], dtype=np.float64)
        H = self._measurement_matrix()
        innovation = meas - H @ self.state
        S = H @ self.P @ H.T + np.eye(2) * 5.0
        K = self.P @ H.T @ np.linalg.inv(S)
        self.state = self.state + K @ innovation
        self.P = (np.eye(4) - K @ H) @ self.P

        return self.state.copy()

    def position(self) -> tuple[float, float]:
        return float(self.state[0]), float(self.state[1])

    def velocity(self) -> tuple[float, float]:
        return float(self.state[2]), float(self.state[3])
