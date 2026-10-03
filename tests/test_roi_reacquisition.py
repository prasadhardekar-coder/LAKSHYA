import numpy as np

from tracking.reacquisition import ReacquisitionManager
from tracking.roi_manager import ROIManager
from tracking.target_validator import TargetValidator


def test_roi_manager_seeds_center_and_crops_region():
    manager = ROIManager(width=64, height=64)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    state = manager.seed((320.0, 240.0))
    crop = manager.crop(frame, (320.0, 240.0))

    assert state.center_x == 320.0
    assert crop.shape[:2] == (64, 64)


def test_validator_rejects_bad_detection():
    validator = TargetValidator(min_confidence=0.5)
    assert validator.validate({"x": 10, "y": 20, "width": 30, "height": 40, "confidence": 0.9})
    assert not validator.validate({"x": 10, "y": 20, "width": 5, "height": 5, "confidence": 0.9})


def test_reacquisition_manager_tracks_attempt_cap():
    manager = ReacquisitionManager(max_attempts=2)
    manager.reset()
    assert manager.max_attempts == 2
