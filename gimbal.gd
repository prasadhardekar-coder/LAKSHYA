extends Node3D

# =========================================================
# GIMBAL CONTROL
# =========================================================

@export_group("Gimbal Settings")

@export var target: Node3D

@export var pan_speed: float = 2.0
@export var tilt_speed: float = 2.0

@export_enum(
	"AUTO_TARGET",
	"LOCAL_DETECTOR",
	"PYTHON_UDP"
)
var control_mode: String = "LOCAL_DETECTOR"


@onready var pan: Node3D = $pan
@onready var tilt: Node3D = $pan/tilt


func _ready() -> void:

	# Find the beacon if no target is assigned.
	if target == null:
		var scene := get_tree().current_scene

		if scene != null:
			target = scene.get_node_or_null(
				"target platformA/beacon"
			)


func _process(delta: float) -> void:

	# Python controls the gimbal through UDP.
	if control_mode == "PYTHON_UDP":
		return

	# The local detector handles tracking in this mode.
	if control_mode == "LOCAL_DETECTOR":
		return

	# Automatic beacon tracking.
	if control_mode != "AUTO_TARGET":
		return

	if not is_instance_valid(target):
		return

	var target_local: Vector3 = to_local(
		target.global_position
	)

	# PAN
	var pan_angle: float = atan2(
		-target_local.x,
		-target_local.z
	)

	pan.rotation.y = rotate_toward(
		pan.rotation.y,
		pan_angle,
		pan_speed * delta
	)

	# TILT
	var target_pan_local: Vector3 = pan.to_local(
		target.global_position
	)

	var tilt_angle: float = atan2(
		target_pan_local.y,
		-target_pan_local.z
	)

	tilt.rotation.x = rotate_toward(
		tilt.rotation.x,
		tilt_angle,
		tilt_speed * delta
	)
