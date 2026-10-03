
extends Node3D

@export_group("Host Platform Movement")
@export var movement_enabled: bool = false
@export_enum("X", "Y", "Z") var movement_axis: int = 0
@export_range(0.0, 10.0, 0.1) var amplitude: float = 1.0
@export_range(0.0, 2.0, 0.01) var frequency: float = 0.2

var initial_position: Vector3
var elapsed_time: float = 0.0


func _ready() -> void:
	initial_position = position


func _process(delta: float) -> void:
	if not movement_enabled:
		position = initial_position
		return

	elapsed_time += delta

	var offset := amplitude * sin(
		TAU * frequency * elapsed_time
	)

	var movement := Vector3.ZERO

	match movement_axis:
		0:
			movement.x = offset
		1:
			movement.y = offset
		2:
			movement.z = offset

	position = initial_position + movement
