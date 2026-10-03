from __future__ import annotations

import json
import socket
from typing import Optional

import numpy as np


class GodotBridge:
    """Single network layer for the Godot <-> Python loop."""

    def __init__(
        self,
        python_ip: str = "127.0.0.1",
        frame_port: int = 5006,
        command_port: int = 5005,
        buffer_size: int = 65535,
    ) -> None:
        self.python_ip = python_ip
        self.frame_port = frame_port
        self.command_port = command_port
        self.buffer_size = buffer_size

        self.frame_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.frame_socket.bind(("0.0.0.0", frame_port))
        self.frame_socket.settimeout(1.0)
        self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send_command(self, pan_velocity: float, tilt_velocity: float) -> None:
        payload = {
            "pan_velocity": float(pan_velocity),
            "tilt_velocity": float(tilt_velocity),
        }
        try:
            self.command_socket.sendto(
                json.dumps(payload).encode("utf-8"),
                (self.python_ip, self.command_port),
            )
        except OSError:
            pass

    def receive_frame(self):
        try:
            packet, _ = self.frame_socket.recvfrom(self.buffer_size)
        except socket.timeout:
            return None

        header, separator, payload = packet.partition(b"\n")
        if not separator:
            return None

        try:
            parts = header.decode("ascii").split("|")
            if len(parts) != 4 or parts[0] != "FRAME":
                return None
            frame_id = int(parts[1])
            chunk_index = int(parts[2])
            total_chunks = int(parts[3])
        except (ValueError, UnicodeDecodeError):
            return None

        return {
            "frame_id": frame_id,
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "payload": payload,
        }

    def close(self) -> None:
        try:
            self.frame_socket.close()
        except OSError:
            pass
        try:
            self.command_socket.close()
        except OSError:
            pass
