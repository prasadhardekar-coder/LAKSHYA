# System Architecture

The diagram describes the current closed-loop simulation path. UDP port `5006` carries camera frames from Godot to Python; UDP port `5005` carries pan/tilt velocity commands back to Godot.

```mermaid
flowchart TB
    subgraph Godot[Godot simulation]
        Scene[Main 3D scene]
        Camera[Virtual camera]
        Gimbal[Pan/tilt gimbal]
        Scene --> Camera
        Gimbal --> Camera
    end

    subgraph Python[Python controller]
        Receiver[UDP frame receiver]
        CV[OpenCV cyan detector]
        Fallback[YOLO fallback]
        Estimator[Position and motion estimator]
        Control[Pan/tilt PID controller]
        Server[Local dashboard server]
        Metrics[Recovery metrics CSV]
        Receiver --> CV
        CV -->|Detection missing| Fallback
        CV --> Estimator
        Fallback --> Estimator
        Estimator --> Control
        Control --> Metrics
    end

    Camera -->|JPEG frames, port 5006| Receiver
    Control -->|JSON velocity commands, port 5005| Gimbal
    Receiver --> Server
```

The live controller is implemented in `python_controller.py`. The project report documents which helpers are active and which are currently unused.