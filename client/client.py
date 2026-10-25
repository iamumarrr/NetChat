import getpass
import socket
import threading

from shared.protocol import (
    send_message,
    receive_message
)


HOST = "127.0.0.1"
PORT = 5000


# --------------------------------------------------
# RECEIVE SERVER MESSAGES
# --------------------------------------------------

def receive_messages(client_socket):
    while True:
        try:
            message = receive_message(client_socket)
            message_type = message.get("type")

            if message_type == "user_list":
                print("\n========== Online Users ==========")

                users = message.get("users", [])

                if not users:
                    print("No users are currently online.")
                else:
                    for username in users:
                        print(f"  - {username}")

                print("=================================\n")

            elif message_type == "user_joined":
                print(f"\n→ {message['username']} joined the chat")

            elif message_type == "user_left":
                print(f"\n← {message['username']} left the chat")

            elif message_type == "public_message":
                print(
                    f"\n{message['sender']}: "
                    f"{message['message']}"
                )

            elif message_type == "private_message":
                print(
                    f"\n[Private] {message['sender']}: "
                    f"{message['message']}"
                )

            elif message_type == "private_message_sent":
                print(
                    f"\n[Private → {message['recipient']}] "
                    f"{message['message']}"
                )

            # PUBLIC HISTORY
            elif message_type == "public_history":
                messages = message.get("messages", [])

                print("\n========== Public Chat History ==========")

                if not messages:
                    print("No public messages yet.")
                else:
                    for item in messages:
                        print(
                            f"[{item['created_at']}] "
                            f"{item['sender']}: {item['message']}"
                        )

                print("=========================================\n")

            # PRIVATE HISTORY
            elif message_type == "private_history":
                other_user = message.get("username", "")
                messages = message.get("messages", [])

                print(
                    f"\n========== Chat History with "
                    f"{other_user} =========="
                )

                if not messages:
                    print("No private messages found.")
                else:
                    for item in messages:
                        print(
                            f"[{item['created_at']}] "
                            f"{item['sender']} → "
                            f"{item['recipient']}: "
                            f"{item['message']}"
                        )

                print("=========================================\n")

            # GROUP CREATED
            elif message_type == "group_created":
                print(f"\n✓ {message['message']}")

            # AVAILABLE GROUPS
            elif message_type == "groups_list":
                groups = message.get("groups", [])

                print("\n========== Available Groups ==========")

                if not groups:
                    print("No groups exist yet.")
                else:
                    for group in groups:
                        print(
                            f"  #{group['name']} "
                            f"(created by {group['created_by']})"
                        )

                print("======================================\n")

            # JOINED GROUP
            elif message_type == "group_joined":
                print(f"\n✓ Joined group #{message['group']}")

            # LEFT GROUP
            elif message_type == "group_left":
                print(f"\n✓ Left group #{message['group']}")

            # GROUP MEMBERSHIP NOTIFICATIONS
            elif message_type == "group_member_joined":
                print(
                    f"\n[#{message['group']}] "
                    f"{message['username']} joined the group."
                )

            elif message_type == "group_member_left":
                print(
                    f"\n[#{message['group']}] "
                    f"{message['username']} left the group."
                )

            # GROUP MESSAGE
            elif message_type == "group_message":
                print(
                    f"\n[#{message['group']}] "
                    f"{message['sender']}: "
                    f"{message['message']}"
                )

            # GROUP MEMBERS
            elif message_type == "group_members":
                group_name = message.get("group", "")
                members = message.get("members", [])

                print(
                    f"\n========== Members of "
                    f"#{group_name} =========="
                )

                if not members:
                    print("No members are currently online in this group.")
                else:
                    for member in members:
                        print(f"  - {member}")

                print("========================================\n")

            # GROUP HISTORY
            elif message_type == "group_history":
                group_name = message.get("group", "")
                messages = message.get("messages", [])

                print(
                    f"\n========== History of "
                    f"#{group_name} =========="
                )

                if not messages:
                    print("No messages in this group yet.")
                else:
                    for item in messages:
                        print(
                            f"[{item['created_at']}] "
                            f"{item['sender']}: "
                            f"{item['message']}"
                        )

                print("========================================\n")

            # ERRORS
            elif message_type == "error":
                print(
                    f"\n✗ Error: "
                    f"{message.get('message', 'Unknown error')}"
                )

            # LOGOUT
            elif message_type == "logout_success":
                print("\n✓ Logged out successfully.")
                break

        except (ConnectionError, OSError):
            print("\n✗ Disconnected from server.")
            break

        except Exception as error:
            print(f"\n✗ Receive error: {error}")
            break


# --------------------------------------------------
# LOGIN AND REGISTRATION
# --------------------------------------------------

def login_or_register(client_socket):
    """
    Handles login and registration before the receiver thread starts.
    Only this function reads from the socket during authentication.
    """

    try:
        receive_message(client_socket)

    except (ConnectionError, OSError):
        print("\n✗ Server disconnected.")
        return None

    while True:
        print()
        print("==========================")
        print("        NetChat")
        print("==========================")
        print("1. Login")
        print("2. Register")
        print("3. Exit")
        print("==========================")

        choice = input("Choose an option: ").strip()

        if choice == "1":
            username = input("Username: ").strip()

            if not username:
                print("\n✗ Username cannot be empty.")
                continue

            password = getpass.getpass("Password: ")

            if not password:
                print("\n✗ Password cannot be empty.")
                continue

            send_message(
                client_socket,
                {
                    "type": "login",
                    "username": username,
                    "password": password
                }
            )

            try:
                response = receive_message(client_socket)

            except (ConnectionError, OSError):
                print("\n✗ Server disconnected.")
                return None

            if response.get("type") == "login_success":
                print(f"\n✓ Logged in as {response['username']}")
                return response["username"]

            print(
                f"\n✗ Login failed: "
                f"{response.get('message', 'Unknown error')}"
            )

        elif choice == "2":
            username = input("Choose username: ").strip()

            if not username:
                print("\n✗ Username cannot be empty.")
                continue

            password = getpass.getpass("Choose password: ")
            confirm_password = getpass.getpass("Confirm password: ")

            if password != confirm_password:
                print("\n✗ Passwords do not match.")
                continue

            if not password:
                print("\n✗ Password cannot be empty.")
                continue

            send_message(
                client_socket,
                {
                    "type": "register",
                    "username": username,
                    "password": password
                }
            )

            try:
                response = receive_message(client_socket)

            except (ConnectionError, OSError):
                print("\n✗ Server disconnected.")
                return None

            if response.get("type") == "registration_success":
                print(f"\n✓ {response['message']}")
                print("Please log in with your new account.")
            else:
                print(
                    f"\n✗ Registration failed: "
                    f"{response.get('message', 'Unknown error')}"
                )

        elif choice == "3":
            print("\nGoodbye!")
            return None

        else:
            print("\n✗ Invalid option.")


# --------------------------------------------------
# COMMAND HELP
# --------------------------------------------------

def print_commands():
    print()
    print("==========================")
    print("      Chat Started")
    print("==========================")
    print("PUBLIC CHAT")
    print("  /users")
    print("  /history")
    print()
    print("PRIVATE CHAT")
    print("  /msg username message")
    print("  /history username")
    print()
    print("GROUP CHAT")
    print("  /groups")
    print("  /group create name")
    print("  /join name")
    print("  /leave name")
    print("  /members name")
    print("  /groupmsg name message")
    print("  /grouphistory name")
    print()
    print("GENERAL")
    print("  /help")
    print("  /quit")
    print("==========================")
    print()


# --------------------------------------------------
# COMMANDS AFTER LOGIN
# --------------------------------------------------

def send_messages_after_login(client_socket):
    print_commands()

    while True:
        try:
            message = input().strip()

        except (KeyboardInterrupt, EOFError):
            message = "/quit"

        if message == "/quit":
            try:
                send_message(
                    client_socket,
                    {
                        "type": "logout"
                    }
                )
            except Exception:
                pass

            break

        elif message == "/help":
            print_commands()

        # ONLINE USERS
        elif message == "/users":
            send_message(
                client_socket,
                {
                    "type": "get_users"
                }
            )

        # PUBLIC HISTORY
        elif message == "/history":
            send_message(
                client_socket,
                {
                    "type": "get_public_history"
                }
            )

        # PRIVATE HISTORY
        elif message.startswith("/history "):
            other_user = message[len("/history "):].strip()

            if not other_user:
                print("Usage: /history username")
                continue

            send_message(
                client_socket,
                {
                    "type": "get_private_history",
                    "username": other_user
                }
            )

        # LIST GROUPS
        elif message == "/groups":
            send_message(
                client_socket,
                {
                    "type": "get_groups"
                }
            )

        # CREATE GROUP
        elif message.startswith("/group create "):
            group_name = message[len("/group create "):].strip()

            if not group_name:
                print("Usage: /group create name")
                continue

            send_message(
                client_socket,
                {
                    "type": "create_group",
                    "group": group_name
                }
            )

        # JOIN GROUP
        elif message.startswith("/join "):
            group_name = message[len("/join "):].strip()

            if not group_name:
                print("Usage: /join name")
                continue

            send_message(
                client_socket,
                {
                    "type": "join_group",
                    "group": group_name
                }
            )

        # LEAVE GROUP
        elif message.startswith("/leave "):
            group_name = message[len("/leave "):].strip()

            if not group_name:
                print("Usage: /leave name")
                continue

            send_message(
                client_socket,
                {
                    "type": "leave_group",
                    "group": group_name
                }
            )

        # LIST GROUP MEMBERS
        elif message.startswith("/members "):
            group_name = message[len("/members "):].strip()

            if not group_name:
                print("Usage: /members name")
                continue

            send_message(
                client_socket,
                {
                    "type": "get_group_members",
                    "group": group_name
                }
            )

        # SEND GROUP MESSAGE
        elif message.startswith("/groupmsg "):
            parts = message.split(" ", 2)

            if len(parts) < 3:
                print("Usage: /groupmsg name message")
                continue

            group_name = parts[1].strip()
            group_text = parts[2].strip()

            if not group_name or not group_text:
                print("Group name and message cannot be empty.")
                continue

            send_message(
                client_socket,
                {
                    "type": "group_message",
                    "group": group_name,
                    "message": group_text
                }
            )

        # GROUP HISTORY
        elif message.startswith("/grouphistory "):
            group_name = message[len("/grouphistory "):].strip()

            if not group_name:
                print("Usage: /grouphistory name")
                continue

            send_message(
                client_socket,
                {
                    "type": "get_group_history",
                    "group": group_name
                }
            )

        # PRIVATE MESSAGE
        elif message.startswith("/msg "):
            parts = message.split(" ", 2)

            if len(parts) < 3:
                print("Usage: /msg username message")
                continue

            recipient = parts[1].strip()
            private_text = parts[2].strip()

            if not recipient or not private_text:
                print("Username and message cannot be empty.")
                continue

            send_message(
                client_socket,
                {
                    "type": "private_message",
                    "recipient": recipient,
                    "message": private_text
                }
            )

        # PUBLIC MESSAGE
        elif message:
            send_message(
                client_socket,
                {
                    "type": "public_message",
                    "message": message
                }
            )

    try:
        client_socket.close()
    except OSError:
        pass


# --------------------------------------------------
# START CLIENT
# --------------------------------------------------

def start_client():
    client_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    try:
        client_socket.connect((HOST, PORT))

        print("Connected to NetChat server.")

        username = login_or_register(client_socket)

        if username is None:
            client_socket.close()
            return

        receiver_thread = threading.Thread(
            target=receive_messages,
            args=(client_socket,),
            daemon=True
        )

        receiver_thread.start()

        send_messages_after_login(client_socket)

    except ConnectionRefusedError:
        print("\n✗ Could not connect to server.")
        print("Make sure the server is running.")

    except (ConnectionError, OSError) as error:
        print(f"\n✗ Connection error: {error}")

    except KeyboardInterrupt:
        print("\n\nClient stopped.")

    finally:
        try:
            client_socket.close()
        except OSError:
            pass


if __name__ == "__main__":
    start_client()