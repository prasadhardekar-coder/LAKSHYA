import json
from urllib.request import urlopen

from output.web_dashboard import DashboardServer


def test_dashboard_serves_live_state_and_frame():
    dashboard = DashboardServer(port=0)
    url = dashboard.start()
    dashboard.publish(
        {
            "tracking_state": "TRACKING",
            "detector": "OpenCV",
            "error_x_px": 2.5,
            "error_y_px": -1.0,
        },
        b"jpeg-frame",
    )

    try:
        with urlopen(f"{url}api/state") as response:
            state = json.loads(response.read())
        with urlopen(f"{url}api/frame.jpg") as response:
            frame = response.read()
            content_type = response.headers["Content-Type"]

        assert state["tracking_state"] == "TRACKING"
        assert state["detector"] == "OpenCV"
        assert state["controller_connected"] is True
        assert state["godot_connected"] is True
        assert frame == b"jpeg-frame"
        assert content_type == "image/jpeg"
    finally:
        dashboard.close()
