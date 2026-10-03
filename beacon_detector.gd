extends Node

# =========================================================
# SETTINGS
# =========================================================

@export_group("Tracking Settings")

# NEW: Set to false when Python controls the gimbal.
@export var enable_local_gimbal_control: bool = false

@export var scan_interval: float = 0.2

@export var correction_gain: float = 0.08
@export var max_step: float = deg_to_rad(2.0)
@export var deadband: float = 3.0

@export var disturbance_angle: float = deg_to_rad(5.0)
@export var metrics_interval: float = 5.0


# =========================================================
# FRAME DISPLACEMENT MEASUREMENT
# =========================================================

@export_group("Frame Displacement Measurement")

@export var measure_frame_displacement: bool = true

@export var displacement_log_interval: float = 1.0

const MAX_PIXEL_DISPLACEMENT: float = 20.0

var previous_beacon_position: Vector2 = Vector2.ZERO
var has_previous_beacon_position: bool = false

var displacement_timer: float = 0.0
var displacement_frame_count: int = 0
var displacement_total: float = 0.0
var displacement_max: float = 0.0
var displacement_over_limit: int = 0


# =========================================================
# NODE REFERENCES
# =========================================================

@onready var camera: Camera3D = get_parent()

@onready var tilt: Node3D = get_parent().get_parent()

@onready var pan: Node3D = (
	get_parent().get_parent().get_parent()
)


# =========================================================
# TRACKING VARIABLES
# =========================================================

var scan_timer: float = 0.0
var metrics_timer: float = 0.0

var detection_attempts: int = 0
var detection_successes: int = 0

var total_pixel_error: float = 0.0
var max_pixel_error: float = 0.0


# =========================================================
# INITIALIZATION
# =========================================================

func _ready() -> void:
	print("DETECTOR INSTANCE: ", get_path())
	print("DETECTOR INSTANCE ID: ", get_instance_id())

	print("")
	print("====================================")
	print(" BEACON TRACKING SYSTEM INITIALIZED ")
	print("====================================")

	print("Scan interval: ", scan_interval)
	print("Correction gain: ", correction_gain)

	print(
		"Maximum step: ",
		rad_to_deg(max_step),
		" degrees"
	)

	print("Deadband: ", deadband, " pixels")

	print(
		"Frame displacement measurement: ",
		measure_frame_displacement
	)

	print(
		"Displacement limit: ",
		MAX_PIXEL_DISPLACEMENT,
		" px/frame"
	)

	print(
		"Local gimbal control enabled: ",
		enable_local_gimbal_control
	)

	if enable_local_gimbal_control:
		print("Gimbal control: LOCAL GODOT DETECTOR")
	else:
		print("Gimbal control: EXTERNAL CONTROLLER (PYTHON)")

	print("Press T to apply a pan disturbance.")
	print("====================================")


# =========================================================
# MAIN LOOP
# =========================================================

func _process(delta: float) -> void:

	# Update timers
	scan_timer += delta
	metrics_timer += delta

	if measure_frame_displacement:
		displacement_timer += delta

	# Capture the viewport once per rendered frame
	var image: Image = (
		get_viewport().get_texture().get_image()
	)

	if image == null or image.is_empty():
		return

	var image_width: int = image.get_width()
	var image_height: int = image.get_height()

	# Detect the beacon in this frame
	var beacon_position: Variant = (
		_detect_beacon_centroid(image)
	)

	# -----------------------------------------------------
	# FRAME DISPLACEMENT MEASUREMENT
	# -----------------------------------------------------

	if measure_frame_displacement:
		_update_frame_displacement(
			beacon_position
		)

	# -----------------------------------------------------
	# LOCAL TRACKING CONTROLLER
	# -----------------------------------------------------
	# Runs only when enable_local_gimbal_control is true.
	# When false, Python can control the gimbal instead.
	# -----------------------------------------------------

	if enable_local_gimbal_control:
		if scan_timer >= scan_interval:
			scan_timer = 0.0

			scan_and_track(
				beacon_position,
				image_width,
				image_height
			)

	# -----------------------------------------------------
	# PERIODIC TRACKING METRICS
	# -----------------------------------------------------

	if metrics_timer >= metrics_interval:
		_print_metrics()
		_reset_metrics()


# =========================================================
# INPUT
# =========================================================
# Press T to apply a +5 degree pan disturbance.
# =========================================================

func _input(event: InputEvent) -> void:

	if event is InputEventKey:
		if event.pressed and not event.echo:

			if event.keycode == KEY_T:
				pan.rotation.y += disturbance_angle

				print("")
				print("====================================")
				print("DISTURBANCE APPLIED")

				print(
					"Pan rotated by: ",
					rad_to_deg(disturbance_angle),
					" degrees"
				)

				print("====================================")


# =========================================================
# BEACON DETECTION
# =========================================================
# Returns:
#   Vector2 = detected beacon centroid
#   null    = beacon not detected
# =========================================================

func _detect_beacon_centroid(
	image: Image
) -> Variant:

	var image_width: int = image.get_width()
	var image_height: int = image.get_height()

	var sum_x: float = 0.0
	var sum_y: float = 0.0
	var pixel_count: int = 0

	for y in range(image_height):
		for x in range(image_width):

			var color: Color = image.get_pixel(x, y)

			if (
				color.g > 0.65
				and color.b > 0.65
				and color.r < 0.45
			):
				sum_x += x
				sum_y += y
				pixel_count += 1

	if pixel_count == 0:
		return null

	var beacon_x: float = (
		sum_x / float(pixel_count)
	)

	var beacon_y: float = (
		sum_y / float(pixel_count)
	)

	return Vector2(beacon_x, beacon_y)


# =========================================================
# FRAME DISPLACEMENT
# =========================================================
# Measures centroid movement between consecutive
# rendered frames where the beacon is detected.
# =========================================================

func _update_frame_displacement(
	beacon_position: Variant
) -> void:

	# If detection fails, do not measure across the gap.
	if beacon_position == null:
		has_previous_beacon_position = false
		return

	var current_position: Vector2 = beacon_position

	if has_previous_beacon_position:

		var displacement: float = (
			current_position.distance_to(
				previous_beacon_position
			)
		)

		displacement_frame_count += 1
		displacement_total += displacement

		displacement_max = max(
			displacement_max,
			displacement
		)

		if displacement > MAX_PIXEL_DISPLACEMENT:
			displacement_over_limit += 1

	# Store current centroid for the next frame
	previous_beacon_position = current_position
	has_previous_beacon_position = true

	# Print displacement statistics periodically
	if displacement_timer >= displacement_log_interval:

		var mean_displacement: float = 0.0

		if displacement_frame_count > 0:
			mean_displacement = (
				displacement_total
				/ float(displacement_frame_count)
			)

		print("")
		print("======= FRAME DISPLACEMENT =======")

		print(
			"Image resolution: ",
			"640 x 480"
			if (
				get_viewport().get_texture().get_width() == 640
				and get_viewport().get_texture().get_height() == 480
			)
			else "See actual viewport resolution"
		)

		print(
			"Measured frame intervals: ",
			displacement_frame_count
		)

		print(
			"Mean displacement: ",
			"%.2f" % mean_displacement,
			" px/frame"
		)

		print(
			"Maximum displacement: ",
			"%.2f" % displacement_max,
			" px/frame"
		)

		print(
			"Frames above 20 px: ",
			displacement_over_limit
		)

		if displacement_frame_count > 0:

			if displacement_max <= MAX_PIXEL_DISPLACEMENT:
				print("20 px/frame limit: PASS")
			else:
				print("20 px/frame limit: EXCEEDED")

		else:
			print(
				"20 px/frame limit: INSUFFICIENT DATA"
			)

		print("==================================")

		# Reset displacement statistics
		displacement_timer = 0.0
		displacement_frame_count = 0
		displacement_total = 0.0
		displacement_max = 0.0
		displacement_over_limit = 0


# =========================================================
# BEACON TRACKING AND GIMBAL CONTROL
# =========================================================

func scan_and_track(
	beacon_position: Variant,
	image_width: int,
	image_height: int
) -> void:

	detection_attempts += 1

	# -----------------------------------------------------
	# HANDLE NO DETECTION
	# -----------------------------------------------------

	if beacon_position == null:
		print("BEACON NOT DETECTED")
		return

	detection_successes += 1

	var beacon: Vector2 = beacon_position

	# -----------------------------------------------------
	# CALCULATE BEACON ERROR
	# -----------------------------------------------------

	var center_x: float = image_width / 2.0
	var center_y: float = image_height / 2.0

	var raw_error_x: float = beacon.x - center_x
	var raw_error_y: float = beacon.y - center_y

	var pixel_error: float = Vector2(
		raw_error_x,
		raw_error_y
	).length()

	total_pixel_error += pixel_error

	max_pixel_error = max(
		max_pixel_error,
		pixel_error
	)

	# -----------------------------------------------------
	# APPLY DEAD BAND
	# -----------------------------------------------------

	var control_error_x: float = raw_error_x
	var control_error_y: float = raw_error_y

	if abs(control_error_x) < deadband:
		control_error_x = 0.0

	if abs(control_error_y) < deadband:
		control_error_y = 0.0

	# -----------------------------------------------------
	# CONVERT PIXEL ERROR TO ANGULAR ERROR
	# -----------------------------------------------------

	var fov_radians: float = deg_to_rad(camera.fov)

	var focal_px: float = (
		float(image_height) / 2.0
	) / tan(fov_radians / 2.0)

	var angle_x: float = atan(
		control_error_x / focal_px
	)

	var angle_y: float = atan(
		control_error_y / focal_px
	)

	# -----------------------------------------------------
	# PROPORTIONAL CONTROLLER
	# -----------------------------------------------------

	var pan_step: float = clamp(
		angle_x * correction_gain,
		-max_step,
		max_step
	)

	var tilt_step: float = clamp(
		angle_y * correction_gain,
		-max_step,
		max_step
	)

	# -----------------------------------------------------
	# APPLY GIMBAL CORRECTIONS
	# -----------------------------------------------------

	pan.rotation.y -= pan_step
	tilt.rotation.x -= tilt_step

	# -----------------------------------------------------
	# DEBUG OUTPUT
	# -----------------------------------------------------

	print(
		"RAW ERROR: X = ",
		"%.2f" % raw_error_x,
		" | Y = ",
		"%.2f" % raw_error_y
	)

	print(
		"CONTROL ERROR: X = ",
		"%.2f" % control_error_x,
		" | Y = ",
		"%.2f" % control_error_y
	)

	print(
		"PAN STEP: ",
		"%.3f" % rad_to_deg(pan_step),
		" degrees"
	)

	print(
		"TILT STEP: ",
		"%.3f" % rad_to_deg(tilt_step),
		" degrees"
	)

	print("------------------------------------")


# =========================================================
# TRACKING PERFORMANCE METRICS
# =========================================================

func _print_metrics() -> void:

	var detection_rate: float = 0.0
	var mean_error: float = 0.0

	if detection_attempts > 0:
		detection_rate = (
			float(detection_successes)
			/ float(detection_attempts)
		) * 100.0

	if detection_successes > 0:
		mean_error = (
			total_pixel_error
			/ float(detection_successes)
		)

	print("")
	print("========== TRACKING METRICS ==========")

	print(
		"Detection rate: ",
		"%.1f" % detection_rate,
		"%"
	)

	print(
		"Mean pixel error: ",
		"%.2f" % mean_error,
		" px"
	)

	print(
		"Maximum pixel error: ",
		"%.2f" % max_pixel_error,
		" px"
	)

	print(
		"Successful detections: ",
		detection_successes,
		"/",
		detection_attempts
	)

	print("======================================")

	_append_metrics_to_csv(
		detection_rate,
		mean_error,
		max_pixel_error
	)


# =========================================================
# RESET TRACKING METRICS
# =========================================================

func _reset_metrics() -> void:

	metrics_timer = 0.0

	detection_attempts = 0
	detection_successes = 0

	total_pixel_error = 0.0
	max_pixel_error = 0.0


# =========================================================
# SAVE TRACKING METRICS TO CSV
# Location: user://tracking_metrics.csv
# =========================================================

func _append_metrics_to_csv(
	detection_rate: float,
	mean_error: float,
	max_error: float
) -> void:

	var file_path: String = (
		"user://tracking_metrics.csv"
	)

	var file_exists: bool = (
		FileAccess.file_exists(file_path)
	)

	var file: FileAccess

	if file_exists:
		file = FileAccess.open(
			file_path,
			FileAccess.READ_WRITE
		)
	else:
		file = FileAccess.open(
			file_path,
			FileAccess.WRITE
		)

	if file == null:
		push_error(
			"Unable to open tracking_metrics.csv"
		)
		return

	if not file_exists:
		file.store_line(
			"timestamp,detection_rate,mean_error,max_error,successful_detections,attempts"
		)

	file.seek_end()

	var timestamp: String = (
		Time.get_datetime_string_from_system()
	)

	var row: String = (
		"%s,%.2f,%.2f,%.2f,%d,%d"
		% [
			timestamp,
			detection_rate,
			max_error,
			max_error,
			detection_successes,
			detection_attempts
		]
	)

	file.store_line(row)
	file.close()
