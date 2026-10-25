import socket
import threading

from shared.protocol import (
    send_message,
    receive_message
)


HOST = "0.0.0.0"
PORT = 5000


# Connected users
clients = {}

# Protect shared clients dictionary
clients_lock = threading.Lock()


def send_to_user(username, message):
    """
    Send a JSON message to a specific user.
    """

    with clients_lock:
        user_info = clients.get(username)

    if user_info is None:
        return False

    try:

        send_message(
            user_info["socket"],
            message
        )

        return True

    except (ConnectionResetError, BrokenPipeError, OSError):

        return False


def broadcast(message, exclude_username=None):
    """
    Send a message to all connected users.
    """

    with clients_lock:
        users = list(clients.items())

    for username, user_info in users:

        if username == exclude_username:
            continue

        try:

            send_message(
                user_info["socket"],
                message
            )

        except (ConnectionResetError, BrokenPipeError, OSError):

            pass


def send_user_list(client_socket):
    """
    Send list of online users.
    """

    with clients_lock:
        usernames = list(clients.keys())

    send_message(
        client_socket,
        {
            "type": "user_list",
            "users": usernames
        }
    )


def handle_private_message(
    sender,
    recipient,
    message
):
    """
    Send a private message.
    """

    success = send_to_user(
        recipient,
        {
            "type": "private_message",
            "sender": sender,
            "message": message
        }
    )

    if not success:

        send_to_user(
            sender,
            {
                "type": "error",
                "message": (
                    f"User '{recipient}' "
                    "is not online."
                )
            }
        )

        return

    # Confirmation to sender
    send_to_user(
        sender,
        {
            "type": "private_message_sent",
            "recipient": recipient,
            "message": message
        }
    )


def remove_client(username):

    with clients_lock:

        user_info = clients.pop(
            username,
            None
        )

    if user_info is None:
        return

    try:
        user_info["socket"].close()
    except OSError:
        pass

    print(
        f"[DISCONNECTED] {username}"
    )

    broadcast(
        {
            "type": "user_left",
            "username": username
        }
    )


def handle_client(
    client_socket,
    address
):

    username = None

    try:

        print(
            f"[CONNECTION] {address}"
        )

        # Ask for username
        send_message(
            client_socket,
            {
                "type": "request_username"
            }
        )

        # Receive username message
        message = receive_message(
            client_socket
        )

        if message.get("type") != "login":

            send_message(
                client_socket,
                {
                    "type": "error",
                    "message": (
                        "Expected login message."
                    )
                }
            )

            client_socket.close()
            return

        username = message.get(
            "username",
            ""
        ).strip()

        # Validate username
        if not username:

            send_message(
                client_socket,
                {
                    "type": "error",
                    "message": (
                        "Username cannot be empty."
                    )
                }
            )

            client_socket.close()
            return

        # Basic username validation
        if len(username) > 20:

            send_message(
                client_socket,
                {
                    "type": "error",
                    "message": (
                        "Username must be 20 "
                        "characters or fewer."
                    )
                }
            )

            client_socket.close()
            return

        # Check duplicate username
        with clients_lock:

            if username in clients:

                send_message(
                    client_socket,
                    {
                        "type": "error",
                        "message": (
                            "Username already taken."
                        )
                    }
                )

                client_socket.close()
                return

            clients[username] = {
                "socket": client_socket,
                "address": address
            }

        print(
            f"[LOGIN] {username} "
            f"from {address}"
        )

        # Login success
        send_message(
            client_socket,
            {
                "type": "login_success",
                "username": username,
                "message": (
                    f"Welcome, {username}!"
                )
            }
        )

        # Send current user list
        send_user_list(
            client_socket
        )

        # Notify everyone else
        broadcast(
            {
                "type": "user_joined",
                "username": username
            },
            exclude_username=username
        )

        # Main client loop
        while True:

            message = receive_message(
                client_socket
            )

            message_type = message.get(
                "type"
            )

            print(
                f"[{username}] "
                f"{message}"
            )

            # Public chat
            if message_type == "public_message":

                text = message.get(
                    "message",
                    ""
                ).strip()

                if not text:
                    continue

                broadcast(
                    {
                        "type": "public_message",
                        "sender": username,
                        "message": text
                    }
                )

            # Private chat
            elif message_type == "private_message":

                recipient = message.get(
                    "recipient",
                    ""
                ).strip()

                text = message.get(
                    "message",
                    ""
                ).strip()

                if not recipient or not text:
                    continue

                handle_private_message(
                    username,
                    recipient,
                    text
                )

            # User list
            elif message_type == "get_users":

                send_user_list(
                    client_socket
                )

            # Disconnect
            elif message_type == "logout":

                send_message(
                    client_socket,
                    {
                        "type": "logout_success",
                        "message": "Goodbye!"
                    }
                )

                break

            # Unknown message
            else:

                send_message(
                    client_socket,
                    {
                        "type": "error",
                        "message": (
                            "Unknown message type."
                        )
                    }
                )

    except ConnectionError:

        print(
            f"[CONNECTION LOST] {address}"
        )

    except ValueError as error:

        print(
            f"[PROTOCOL ERROR] "
            f"{address}: {error}"
        )

    except Exception as error:

        print(
            f"[ERROR] {username}: {error}"
        )

    finally:

        if username:
            remove_client(username)

        else:

            try:
                client_socket.close()
            except OSError:
                pass


def start_server():

    server = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    server.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    server.bind(
        (HOST, PORT)
    )

    server.listen(10)

    print("================================")
    print("       NETCHAT SERVER")
    print("================================")
    print(
        f"Server running on "
        f"{HOST}:{PORT}"
    )
    print(
        "JSON protocol enabled."
    )
    print(
        "Waiting for connections..."
    )
    print()

    while True:

        client_socket, address = (
            server.accept()
        )

        thread = threading.Thread(
            target=handle_client,
            args=(
                client_socket,
                address
            )
        )

        thread.daemon = True

        thread.start()

        with clients_lock:
            active_users = len(clients)

        print(
            f"[ACTIVE USERS] "
            f"{active_users}"
        )


if __name__ == "__main__":
    start_server()