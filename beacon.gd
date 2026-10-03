extends MeshInstance3D

@export_enum("STRAIGHT", "CIRCULAR", "FIGURE_8", "RANDOM")
var trajectory_mode: String = "STRAIGHT"

@export var amplitude: float = 8.0
@export var speed: float = 1.0

var start_position: Vector3
var elapsed: float = 0.0
var random_target: Vector3
var rng := RandomNumberGenerator.new()


func _ready() -> void:
	start_position = position
	random_target = start_position
	rng.randomize()


func _process(delta: float) -> void:
	elapsed += delta
	var t = elapsed * speed

	match trajectory_mode:
		"STRAIGHT":
			position.x = start_position.x + sin(t) * amplitude
			position.z = start_position.z

		"CIRCULAR":
			position.x = start_position.x + sin(t) * amplitude
			position.z = start_position.z + (cos(t) - 1.0) * amplitude

		"FIGURE_8":
			position.x = start_position.x + sin(t) * amplitude
			position.z = start_position.z + sin(2.0 * t) * amplitude

		"RANDOM":
			if position.distance_to(random_target) < 0.2:
				random_target = start_position + Vector3(
					rng.randf_range(-amplitude, amplitude),
					rng.randf_range(-amplitude * 0.5, amplitude * 0.5),
					rng.randf_range(-amplitude, amplitude)
				)

			position = position.move_toward(
				random_target,
				speed * delta
			)
