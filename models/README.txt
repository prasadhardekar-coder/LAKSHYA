This directory is reserved for the YOLO weights used by the AI fallback detector.

Expected file:
  yolov8n.pt

If the model is not present, the Python controller will continue running using the
OpenCV beacon detector only and will skip the AI recovery path gracefully.
