import socket
import threading

from shared.protocol import (
    send_message,
    receive_message
)


def test_protocol():

    server_socket, client_socket = (
        socket.socketpair()
    )

    message = {
        "type": "test",
        "message": "Hello NetChat!",
        "number": 123
    }

    def sender():

        send_message(
            server_socket,
            message
        )

        server_socket.close()

    thread = threading.Thread(
        target=sender
    )

    thread.start()

    received = receive_message(
        client_socket
    )

    print(
        "Original:",
        message
    )

    print(
        "Received:",
        received
    )

    assert received == message

    client_socket.close()

    thread.join()

    print(
        "✓ Protocol test passed!"
    )


if __name__ == "__main__":
    test_protocol()