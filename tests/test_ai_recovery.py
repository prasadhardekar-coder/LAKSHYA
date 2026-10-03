import numpy as np

from detection.ai_recovery import AIRecoveryNode


def test_select_best_detection_prefers_high_confidence_and_near_center():
    node = AIRecoveryNode(model_path="dummy.pt", confidence=0.3)

    detections = [
        {"x": 100.0, "y": 100.0, "confidence": 0.10, "width": 20.0, "height": 20.0, "class_id": 0},
        {"x": 320.0, "y": 240.0, "confidence": 0.92, "width": 30.0, "height": 30.0, "class_id": 0},
        {"x": 80.0, "y": 80.0, "confidence": 0.88, "width": 10.0, "height": 10.0, "class_id": 0},
    ]

    best = node.select_best_detection(detections, target_center=(320, 240))

    assert best is not None
    assert best["x"] == 320.0
    assert best["y"] == 240.0
    assert best["confidence"] == 0.92


def test_detect_returns_none_when_model_missing():
    node = AIRecoveryNode(model_path="missing_model.pt", confidence=0.35)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    assert node.detect(frame) is None
