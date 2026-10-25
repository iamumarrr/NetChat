
import json
import socket
import struct
import threading
import weakref

HEADER_SIZE = 4
MAX_MESSAGE_SIZE = 64 * 1024  # Reduced to 64KB to prevent memory exhaustion DoS

# Each socket gets its own lock so concurrent server threads cannot
# interleave message frames when sending to the same client.
_socket_locks = weakref.WeakKeyDictionary()
_socket_locks_guard = threading.Lock()


def _get_socket_lock(sock: socket.socket) -> threading.Lock:
    """Return the shared send lock associated with this socket."""
    with _socket_locks_guard:
        lock = _socket_locks.get(sock)

        if lock is None:
            lock = threading.Lock()
            _socket_locks[sock] = lock

        return lock


def send_message(sock: socket.socket, message: dict):
    """
    Encode a dictionary as JSON and send one complete framed message.

    Frame format:
        4-byte unsigned big-endian payload length
        UTF-8 encoded JSON payload
    """
    if not isinstance(message, dict):
        raise TypeError("Message must be a dictionary.")

    json_data = json.dumps(message, ensure_ascii=False)
    data = json_data.encode("utf-8")

    if not data:
        raise ValueError("Message cannot be empty.")

    if len(data) > MAX_MESSAGE_SIZE:
        raise ValueError("Message is too large.")

    header = struct.pack("!I", len(data))
    frame = header + data

    with _get_socket_lock(sock):
        sock.sendall(frame)


def receive_exactly(sock: socket.socket, number_of_bytes: int) -> bytes:
    """
    Receive exactly the requested number of bytes.
    """
    if number_of_bytes < 0:
        raise ValueError("Number of bytes cannot be negative.")

    data = bytearray()

    while len(data) < number_of_bytes:
        chunk = sock.recv(number_of_bytes - len(data))

        if not chunk:
            raise ConnectionError("Connection closed by remote host.")

        data.extend(chunk)

    return bytes(data)


def receive_message(sock: socket.socket) -> dict:
    """Receive and decode one complete framed JSON message."""
    header = receive_exactly(sock, HEADER_SIZE)
    message_length = struct.unpack("!I", header)[0]

    if message_length <= 0:
        raise ValueError("Invalid message length.")

    if message_length > MAX_MESSAGE_SIZE:
        raise ValueError("Message exceeds maximum allowed size.")

    data = receive_exactly(sock, message_length)

    try:
        json_data = data.decode("utf-8")
        message = json.loads(json_data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Received invalid JSON message.") from error

    if not isinstance(message, dict):
        raise ValueError("Message must be a JSON object.")

    return message
