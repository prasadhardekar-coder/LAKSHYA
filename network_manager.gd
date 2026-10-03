extends Node

# ============================================================
# UDP NETWORK MANAGER
# Sends camera frames to Python and receives tracking commands.
# ============================================================


# ============================================================
# UDP SETTINGS
# ============================================================

@export_group("UDP Settings")

@export var python_ip: String = "127.0.0.1"
@export var command_port: int = 5005
@export var frame_port: int = 5006


# ============================================================
# FRAME STREAMING
# ============================================================

@export_group("Frame Streaming")

@export var send_frames: bool = true

@export_range(1, 60, 1)
var send_fps: int = 30

@export_range(1, 100, 1)
var jpeg_quality: int = 75

@export var target_width: int = 640
@export var target_height: int = 480

# Keep UDP packets small to reduce fragmentation.
@export_range(256, 1400, 1)
var chunk_size: int = 1200


# ============================================================
# GIMBAL COMMANDS
# ============================================================

@export_group("Gimbal Commands")

@export var accept_python_commands: bool = true

# Maximum angular velocity in radians per second.
@export var max_pan_speed: float = 2.0
@export var max_tilt_speed: float = 2.0

# Stop the gimbal if commands stop arriving.
@export var command_timeout: float = 0.5


# ============================================================
# NETWORK OBJECTS
# ============================================================

var command_receiver: PacketPeerUDP
var frame_sender: PacketPeerUDP

var network_ready: bool = false

var frame_id: int = 0
var frame_timer: float = 0.0

# Latest velocities received from Python.
var current_pan_velocity: float = 0.0
var current_tilt_velocity: float = 0.0

# Time when the last valid command arrived.
var last_command_time_msec: int = 0


# ============================================================
# EXISTING SCENE NODES
# ============================================================

@onready var pan: Node3D = get_node_or_null(
	"../HostPlatformB/drone1/gimbal/pan"
)

@onready var tilt: Node3D = get_node_or_null(
	"../HostPlatformB/drone1/gimbal/pan/tilt"
)


# ============================================================
# INITIALIZATION
# ============================================================

func _ready() -> void:
	print("")
	print("====================================")
	print("       UDP NETWORK MANAGER")
	print("====================================")

	_start_network()

	if pan == null:
		push_warning(
			"Pan node was not found. Check the scene path."
		)

	if tilt == null:
		push_warning(
			"Tilt node was not found. Check the scene path."
		)


func _start_network() -> void:

	# --------------------------------------------------------
	# Receiver: Python sends commands to this port.
	# --------------------------------------------------------

	command_receiver = PacketPeerUDP.new()

	var receive_error: Error = command_receiver.bind(
		command_port,
		"0.0.0.0"
	)

	if receive_error != OK:
		push_error(
			"Could not bind command port %d. Error: %s"
			% [
				command_port,
				error_string(receive_error)
			]
		)
		return

	# --------------------------------------------------------
	# Sender: Godot sends camera frames to Python.
	# --------------------------------------------------------

	frame_sender = PacketPeerUDP.new()

	var destination_error: Error = (
		frame_sender.set_dest_address(
			python_ip,
			frame_port
		)
	)

	if destination_error != OK:
		push_error(
			"Could not set Python destination. Error: %s"
			% error_string(destination_error)
		)

		command_receiver.close()
		return

	network_ready = true

	print("Command receiver port: ", command_port)
	print(
		"Python frame destination: ",
		python_ip,
		":",
		frame_port
	)

	print("Frame streaming: ", send_frames)
	print(
		"Target resolution: ",
		target_width,
		" x ",
		target_height
	)
	print("Target FPS: ", send_fps)
	print("Maximum pan speed: ", max_pan_speed, " rad/s")
	print("Maximum tilt speed: ", max_tilt_speed, " rad/s")
	print("Command timeout: ", command_timeout, " seconds")
	print("Network initialized.")
	print("====================================")


# ============================================================
# MAIN LOOP
# ============================================================

func _process(delta: float) -> void:

	if not network_ready:
		return

	# --------------------------------------------------------
	# Receive commands from Python.
	# --------------------------------------------------------

	if accept_python_commands:
		_receive_python_commands()

	# --------------------------------------------------------
	# Stop movement if commands become stale.
	# --------------------------------------------------------

	var current_time: int = Time.get_ticks_msec()

	if last_command_time_msec == 0:
		current_pan_velocity = 0.0
		current_tilt_velocity = 0.0

	elif (
		float(current_time - last_command_time_msec)
		> command_timeout * 1000.0
	):
		current_pan_velocity = 0.0
		current_tilt_velocity = 0.0

	# --------------------------------------------------------
	# Apply the latest velocities every frame.
	# --------------------------------------------------------

	if accept_python_commands:

		if pan != null:
			pan.rotation.y += (
				current_pan_velocity * delta
			)

		if tilt != null:
			tilt.rotation.x += (
				current_tilt_velocity * delta
			)

	# --------------------------------------------------------
	# Send camera frames at the configured rate.
	# --------------------------------------------------------

	if send_frames:

		frame_timer += delta

		var frame_interval: float = (
			1.0 / float(send_fps)
		)

		if frame_timer >= frame_interval:
			frame_timer = 0.0
			_send_camera_frame()


# ============================================================
# RECEIVE PYTHON PAN / TILT COMMANDS
#
# Expected JSON:
# {"pan_velocity": 0.1, "tilt_velocity": -0.1}
# ============================================================

func _receive_python_commands() -> void:

	while command_receiver.get_available_packet_count() > 0:

		var packet: PackedByteArray = (
			command_receiver.get_packet()
		)

		var message: String = (
			packet.get_string_from_utf8()
		)

		var parsed: Variant = JSON.parse_string(message)

		if not parsed is Dictionary:
			push_warning(
				"Invalid Python command: " + message
			)
			continue

		var command: Dictionary = parsed

		# Read velocities.
		var pan_velocity: float = float(
			command.get("pan_velocity", 0.0)
		)

		var tilt_velocity: float = float(
			command.get("tilt_velocity", 0.0)
		)

		# Limit the commanded speeds.
		pan_velocity = clamp(
			pan_velocity,
			-max_pan_speed,
			max_pan_speed
		)

		tilt_velocity = clamp(
			tilt_velocity,
			-max_tilt_speed,
			max_tilt_speed
		)

		# Store the latest command.
		# _process() applies it every frame.
		current_pan_velocity = pan_velocity
		current_tilt_velocity = tilt_velocity

		last_command_time_msec = (
			Time.get_ticks_msec()
		)


# ============================================================
# CAPTURE AND SEND CAMERA FRAME
# ============================================================

func _send_camera_frame() -> void:

	var viewport: Viewport = get_viewport()

	if viewport == null:
		return

	var viewport_texture: ViewportTexture = (
		viewport.get_texture()
	)

	if viewport_texture == null:
		return

	var image: Image = viewport_texture.get_image()

	if image == null or image.is_empty():
		return

	# Resize to the Python input resolution.
	if (
		image.get_width() != target_width
		or image.get_height() != target_height
	):
		image.resize(
			target_width,
			target_height
		)

	# Compress the image into JPEG bytes.
	var quality: float = (
		float(jpeg_quality) / 100.0
	)

	var jpeg_data: PackedByteArray = (
		image.save_jpg_to_buffer(quality)
	)

	if jpeg_data.is_empty():
		push_warning(
			"Could not encode camera frame."
		)
		return

	_send_frame_chunks(jpeg_data)


# ============================================================
# SEND JPEG AS UDP CHUNKS
#
# Packet format:
# FRAME|frame_id|chunk_index|total_chunks\n + JPEG bytes
# ============================================================

func _send_frame_chunks(
	jpeg_data: PackedByteArray
) -> void:

	var total_chunks: int = ceili(
		float(jpeg_data.size())
		/ float(chunk_size)
	)

	for chunk_index in range(total_chunks):

		var start_index: int = (
			chunk_index * chunk_size
		)

		var end_index: int = mini(
			start_index + chunk_size,
			jpeg_data.size()
		)

		var header: String = (
			"FRAME|%d|%d|%d\n"
			% [
				frame_id,
				chunk_index,
				total_chunks
			]
		)

		var packet: PackedByteArray = (
			header.to_utf8_buffer()
		)

		packet.append_array(
			jpeg_data.slice(
				start_index,
				end_index
			)
		)

		var send_error: Error = (
			frame_sender.put_packet(packet)
		)

		if send_error != OK:
			push_warning(
				"Frame chunk send failed: "
				+ error_string(send_error)
			)
			return

	frame_id += 1


# ============================================================
# CLEANUP
# ============================================================

func _exit_tree() -> void:

	network_ready = false

	if command_receiver != null:
		command_receiver.close()

	if frame_sender != null:
		frame_sender.close()

	print("UDP Network Manager stopped.")
