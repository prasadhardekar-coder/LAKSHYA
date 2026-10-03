from __future__ import annotations

from output.godot_bridge import GodotBridge


def test_bridge_fields() -> None:
    bridge = GodotBridge()
    assert bridge.python_ip == "127.0.0.1"
    assert bridge.frame_port == 5006
    assert bridge.command_port == 5005
    bridge.close()
