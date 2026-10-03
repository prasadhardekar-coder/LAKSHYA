
import socket
import time
import json
import csv
import math
import os
from pathlib import Path

import cv2
import numpy as np

from detection.ai_verifier import AIVerifier
from detection.opencv_fast import OpenCVFastDetector
from tracking.imm_kalman import IMMTracker
from tracking.roi_manager import ROIManager
from tracking.target_validator import TargetValidator
from tracking.reacquisition import ReacquisitionManager
from control.pid_controller import PIDController, angle_from_pixel_error
from geometry.godot_geometry import camera_center
from output.web_dashboard import DashboardServer

# =========================================================
# SETTINGS
# =========================================================

GODOT_IP = "127.0.0.1"
FRAME_PORT = 5006
COMMAND_PORT = 5005

WIDTH = 640
HEIGHT = 480

PAN_GAIN = 0.01
TILT_GAIN = 0.01

MAX_PAN_SPEED = 0.7
MAX_TILT_SPEED = 0.7

DEADBAND = 3

# Recovery measurement settings
SETTLE_ERROR = 3
SETTLE_DURATION = 0.5
DISTURBANCE_THRESHOLD = 10

# If the beacon is lost, stop movement.
COMMAND_TIMEOUT = 0.5

CSV_FILE = "recovery_metrics.csv"
MODEL_PATH = Path(__file__).resolve().parent / "models" / "yolov8n.pt"

OPENCV_DETECTOR = OpenCVFastDetector()
AI_DETECTOR = AIVerifier(weights=MODEL_PATH, confidence=0.35, device="cpu", image_size=640)
IMM_TRACKER = IMMTracker(dt=1.0 / 30.0)
ROI_MANAGER = ROIManager(width=64, height=64)
TARGET_VALIDATOR = TargetValidator(min_confidence=0.2)
REACQUISITION_MANAGER = ReacquisitionManager(max_attempts=3)
PAN_PID = PIDController(kp=0.8, ki=0.0, kd=0.002, max_output=0.7)
TILT_PID = PIDController(kp=0.8, ki=0.0, kd=0.002, max_output=0.7)


# =========================================================
# UDP SOCKETS
# =========================================================

frame_socket = socket.socket(
    socket.AF_INET,
    socket.SOCK_DGRAM
)

frame_socket.bind(("0.0.0.0", FRAME_PORT))
frame_socket.settimeout(1.0)
frame_socket.setsockopt(
    socket.SOL_SOCKET,
    socket.SO_RCVBUF,
    4 * 1024 * 1024
)

command_socket = socket.socket(
    socket.AF_INET,
    socket.SOCK_DGRAM
)


# =========================================================
# METRICS VARIABLES
# =========================================================

frame_buffers = {}

last_beacon_time = 0.0

disturbance_active = False
disturbance_start = 0.0
max_pixel_error = 0.0
settled_start = None

recovery_results = []
DASHBOARD = DashboardServer()
processed_frames = 0
fps_window_start = time.monotonic()
processing_fps = 0.0


# =========================================================
# CSV INITIALIZATION
# =========================================================

csv_exists = os.path.exists(CSV_FILE)

csv_file = open(
    CSV_FILE,
    "a",
    newline="",
    encoding="utf-8"
)

csv_writer = csv.writer(csv_file)

if not csv_exists or os.path.getsize(CSV_FILE) == 0:
    csv_writer.writerow([
        "timestamp",
        "recovery_time_seconds",
        "maximum_pixel_error",
        "final_error_x",
        "final_error_y",
        "settle_error_pixels",
        "settle_duration_seconds"
    ])
    csv_file.flush()


# =========================================================
# SEND COMMAND TO GODOT
# =========================================================

def send_command(pan_velocity, tilt_velocity):
    command = {
        "pan_velocity": float(pan_velocity),
        "tilt_velocity": float(tilt_velocity)
    }

    try:
        command_socket.sendto(
            json.dumps(command).encode("utf-8"),
            (GODOT_IP, COMMAND_PORT)
        )
    except OSError as error:
        print("Command send error:", error)


# =========================================================
# DETECT CYAN BEACON
# =========================================================

def detect_beacon(frame):
    detection = OPENCV_DETECTOR.detect(frame)
    if detection is None:
        return None
    return detection["x"], detection["y"]


def detect_beacon_ai(frame, target_center=None):
    """Optional YOLO fallback used only when the primary CV tracker loses lock."""
    try:
        result = AI_DETECTOR.detect(frame, target_center=target_center)
    except Exception as exc:
        print(f"[AI fallback] unavailable: {exc}")
        return None

    if result is None:
        return None

    if not TARGET_VALIDATOR.validate(result, width=WIDTH, height=HEIGHT):
        return None

    result = dict(result)
    result["x"] = int(round(result["x"]))
    result["y"] = int(round(result["y"]))
    print(
        f"[AI fallback] detected beacon at ({result['x']}, {result['y']}) "
        f"confidence={result.get('confidence', 0.0):.2f}"
    )
    return result


# =========================================================
# RECOVERY METRICS
# =========================================================

def update_recovery_metrics(error_x, error_y):
    global disturbance_active
    global disturbance_start
    global max_pixel_error
    global settled_start

    now = time.monotonic()

    # Maximum axis error, measured in pixels.
    pixel_error = max(
        abs(error_x),
        abs(error_y)
    )

    # Detect a disturbance when tracking is not
    # already recovering.
    if not disturbance_active:

        if pixel_error > DISTURBANCE_THRESHOLD:
            disturbance_active = True
            disturbance_start = now
            max_pixel_error = pixel_error
            settled_start = None

            print("\n========== DISTURBANCE DETECTED ==========")
            print(f"Initial error X: {error_x} px")
            print(f"Initial error Y: {error_y} px")
            print(f"Initial maximum axis error: {pixel_error} px")
            print("==========================================")

    if not disturbance_active:
        return

    max_pixel_error = max(
        max_pixel_error,
        pixel_error
    )

    # Require both axes to remain inside the
    # settling region.
    inside_settle_region = (
        abs(error_x) <= SETTLE_ERROR
        and abs(error_y) <= SETTLE_ERROR
    )

    if inside_settle_region:

        if settled_start is None:
            settled_start = now

        stable_time = now - settled_start

        if stable_time >= SETTLE_DURATION:

            recovery_time = now - disturbance_start

            timestamp = time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            print("\n========== RECOVERY COMPLETE ==========")
            print(f"Recovery time: {recovery_time:.3f} seconds")
            print(f"Maximum axis error: {max_pixel_error:.0f} px")
            print(f"Final error X: {error_x} px")
            print(f"Final error Y: {error_y} px")
            print(f"Settling requirement: ±{SETTLE_ERROR} px")
            print(f"Stable duration: {SETTLE_DURATION:.2f} seconds")
            print("========================================\n")

            csv_writer.writerow([
                timestamp,
                f"{recovery_time:.3f}",
                f"{max_pixel_error:.0f}",
                error_x,
                error_y,
                SETTLE_ERROR,
                f"{SETTLE_DURATION:.2f}"
            ])

            csv_file.flush()

            recovery_results.append({
                "recovery_time": recovery_time,
                "max_error": max_pixel_error
            })

            disturbance_active = False
            settled_start = None
            max_pixel_error = 0.0

    else:
        # The beacon left the settling region.
        settled_start = None


# =========================================================
# START MESSAGE
# =========================================================

DASHBOARD_URL = DASHBOARD.start()

print("==========================================")
print(" PYTHON BEACON TRACKING CONTROLLER")
print("==========================================")
print(f"Receiving Godot frames on port {FRAME_PORT}")
print(f"Sending gimbal commands on port {COMMAND_PORT}")
print(f"Recovery results: {CSV_FILE}")
print(f"Live dashboard: {DASHBOARD_URL}")
print("Press T in the Godot game window to test recovery.")
print("Press Q in the camera window to stop.")
print("==========================================")


# =========================================================
# MAIN LOOP
# =========================================================

try:
    while True:

        try:
            packet, address = frame_socket.recvfrom(65535)

        except socket.timeout:
            # Stop the gimbal if frames stop arriving.
            send_command(0.0, 0.0)
            continue

        # -------------------------------------------------
        # Parse frame packet header.
        # -------------------------------------------------

        header, separator, payload = packet.partition(b"\n")

        if not separator:
            continue

        try:
            parts = header.decode("ascii").split("|")

            if len(parts) != 4 or parts[0] != "FRAME":
                continue

            frame_id = int(parts[1])
            chunk_index = int(parts[2])
            total_chunks = int(parts[3])

        except (ValueError, UnicodeDecodeError):
            continue

        if (
            total_chunks <= 0
            or chunk_index < 0
            or chunk_index >= total_chunks
        ):
            continue

        # -------------------------------------------------
        # Store the received frame chunk.
        # -------------------------------------------------

        if frame_id not in frame_buffers:
            frame_buffers[frame_id] = {
                "total": total_chunks,
                "chunks": {}
            }

        entry = frame_buffers[frame_id]

        if entry["total"] != total_chunks:
            del frame_buffers[frame_id]
            continue

        entry["chunks"][chunk_index] = payload

        # Discard old incomplete frames.
        if len(frame_buffers) > 20:
            oldest_ids = sorted(
                frame_buffers.keys()
            )[:-10]

            for old_id in oldest_ids:
                frame_buffers.pop(old_id, None)

        # Wait until all chunks arrive.
        if len(entry["chunks"]) != total_chunks:
            continue

        # -------------------------------------------------
        # Reassemble the JPEG.
        # -------------------------------------------------

        try:
            jpeg_data = b"".join(
                entry["chunks"][i]
                for i in range(total_chunks)
            )
        except KeyError:
            del frame_buffers[frame_id]
            continue

        del frame_buffers[frame_id]

        encoded = np.frombuffer(
            jpeg_data,
            dtype=np.uint8
        )

        frame = cv2.imdecode(
            encoded,
            cv2.IMREAD_COLOR
        )

        if frame is None:
            continue

        frame = cv2.resize(
            frame,
            (WIDTH, HEIGHT)
        )

        processed_frames += 1
        fps_now = time.monotonic()
        fps_elapsed = fps_now - fps_window_start
        if fps_elapsed >= 1.0:
            processing_fps = processed_frames / fps_elapsed
            processed_frames = 0
            fps_window_start = fps_now

        center_x, center_y = camera_center(WIDTH, HEIGHT)

        beacon = detect_beacon(frame)
        ai_used = False
        ai_detection = None

        if beacon is None:
            ai_detection = detect_beacon_ai(
                frame,
                target_center=(center_x, center_y),
            )
            if ai_detection is not None:
                beacon = (ai_detection["x"], ai_detection["y"])
                ai_used = True

        telemetry = {
            "tracking_state": "LOST",
            "detector": None,
            "confidence": None,
            "error_x_px": None,
            "error_y_px": None,
            "angular_error_deg": None,
            "centroid_x": None,
            "centroid_y": None,
            "pan_command_dps": 0.0,
            "tilt_command_dps": 0.0,
        }

        # Draw camera center.
        cv2.drawMarker(
            frame,
            (int(center_x), int(center_y)),
            (0, 255, 0),
            cv2.MARKER_CROSS,
            24,
            2
        )

        # -------------------------------------------------
        # BEACON DETECTED
        # -------------------------------------------------

        if beacon is not None:

            last_beacon_time = time.monotonic()

            beacon_x, beacon_y = beacon

            measurement = (float(beacon_x), float(beacon_y))
            filtered_state = IMM_TRACKER.update(measurement)
            estimated_x, estimated_y = filtered_state[0], filtered_state[1]
            error_x = estimated_x - center_x
            error_y = estimated_y - center_y

            # Record disturbance recovery.
            update_recovery_metrics(
                error_x,
                error_y
            )

            # Apply deadband.
            control_x = (
                0
                if abs(error_x) < DEADBAND
                else error_x
            )

            control_y = (
                0
                if abs(error_y) < DEADBAND
                else error_y
            )

            pan_angle_error = angle_from_pixel_error(control_x, WIDTH)
            tilt_angle_error = angle_from_pixel_error(control_y, HEIGHT)
            pan_velocity = PAN_PID.update(-pan_angle_error, 1.0 / 30.0)
            tilt_velocity = TILT_PID.update(-tilt_angle_error, 1.0 / 30.0)

            pan_velocity = max(-MAX_PAN_SPEED, min(MAX_PAN_SPEED, pan_velocity))
            tilt_velocity = max(-MAX_TILT_SPEED, min(MAX_TILT_SPEED, tilt_velocity))

            telemetry = {
                "tracking_state": "TRACKING",
                "detector": "AI fallback" if ai_used else "OpenCV",
                "confidence": ai_detection.get("confidence") if ai_used else 1.0,
                "error_x_px": error_x,
                "error_y_px": error_y,
                "angular_error_deg": math.degrees(
                    math.hypot(pan_angle_error, tilt_angle_error)
                ),
                "centroid_x": beacon_x,
                "centroid_y": beacon_y,
                "pan_command_dps": math.degrees(pan_velocity),
                "tilt_command_dps": math.degrees(tilt_velocity),
            }

            send_command(
                pan_velocity,
                tilt_velocity
            )

            # Draw detected beacon.
            cv2.circle(
                frame,
                (int(beacon_x), int(beacon_y)),
                12,
                (0, 0, 255),
                2
            )

            cv2.putText(
                frame,
                f"Beacon: ({beacon_x}, {beacon_y})",
                (15, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                f"Error X: {error_x} px",
                (15, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                f"Error Y: {error_y} px",
                (15, 90),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                f"Pan: {pan_velocity:.3f}",
                (15, 120),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                f"Tilt: {tilt_velocity:.3f}",
                (15, 150),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2
            )

            source_label = "AI fallback" if ai_used else "OpenCV"
            cv2.putText(
                frame,
                f"Source: {source_label}",
                (15, 180),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2
            )

            print(
                f"Beacon: ({beacon_x}, {beacon_y}) | "
                f"Error X: {error_x} px | "
                f"Error Y: {error_y} px | "
                f"Pan: {pan_velocity:.3f} | "
                f"Tilt: {tilt_velocity:.3f} | "
                f"Source: {source_label}"
            )

        # -------------------------------------------------
        # BEACON NOT DETECTED
        # -------------------------------------------------

        else:

            send_command(0.0, 0.0)

            cv2.putText(
                frame,
                "BEACON NOT DETECTED",
                (15, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

        # -------------------------------------------------
        # DISPLAY CAMERA FEED
        # -------------------------------------------------

        telemetry.update({
            "fps": processing_fps,
            "updated_at": time.time(),
            "recoveries": list(recovery_results),
        })
        frame_ok, dashboard_frame = cv2.imencode(".jpg", frame)
        if frame_ok:
            DASHBOARD.publish(telemetry, dashboard_frame.tobytes())

        cv2.imshow(
            "Godot Camera Feed - Python Beacon Tracking",
            frame
        )

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break


except KeyboardInterrupt:
    print("\nStopping Python controller...")


finally:
    # Stop gimbal on exit.
    try:
        send_command(0.0, 0.0)
    except OSError:
        pass

    frame_socket.close()
    command_socket.close()
    csv_file.close()
    DASHBOARD.close()
    cv2.destroyAllWindows()

    print("Python controller stopped.")
    print(f"Recovery metrics saved to: {CSV_FILE}")