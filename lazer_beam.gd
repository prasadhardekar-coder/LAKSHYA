extends MeshInstance3D

@export var target_path: NodePath = NodePath("../../beacon")
@export var beam_offset: float = 0.5
@export var beam_radius: float = 0.6



func _process(_delta: float) -> void:
	var target = get_node_or_null(target_path)

	if target == null:
		return

	# Drone and beacon positions
	var drone = get_parent()
	var start: Vector3 = drone.global_position
	var end: Vector3 = target.global_position

	var direction: Vector3 = end - start
	var distance: float = direction.length()

	if distance <= 0.01:
		return

	direction = direction.normalized()

	# Move the beam's start slightly forward
	var beam_start: Vector3 = start + direction * beam_offset
	var beam_length: float = (end - beam_start).length()

	if beam_length <= 0.01:
		return

	# Position the beam at the midpoint FIRST
	global_position = beam_start + (end - beam_start) * 0.5

	# Now aim it toward the beacon
	look_at(end, Vector3.UP)
	rotate_object_local(Vector3.RIGHT, -PI / 2.0)

	# Match the cylinder's height to the beam length
	var cylinder_height: float = 2.0

	if mesh is CylinderMesh:
		cylinder_height = (mesh as CylinderMesh).height

	if cylinder_height <= 0.0:
		return

	scale = Vector3(
		beam_radius,
		beam_length / cylinder_height,
		beam_radius
	)
