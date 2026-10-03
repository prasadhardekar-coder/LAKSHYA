extends CharacterBody3D

func _ready() -> void:
	# Keep the drone at its position in the scene.
	set_physics_process(false)
