
import socket
import threading
import ssl
import html
import os
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from datetime import datetime, timedelta

from shared.protocol import (
    send_message,
    receive_message,
)

from database.database import (
    initialize_database,
    register_user,
    authenticate_user,
    save_public_message,
    save_private_message,
    get_public_history,
    get_private_history,
    create_group,
    get_groups,
    group_exists,
    save_group_message,
    get_group_history,
    add_group_membership,
    remove_group_membership,
    get_all_group_memberships,
    get_user_groups,
)


HOST = "0.0.0.0"
PORT = 5000
MAX_WORKERS = 100
LOGIN_ATTEMPTS_LIMIT = 5
LOCKOUT_DURATION = timedelta(minutes=15)

# Path to TLS certificate and private key
# In a real production environment, these would be loaded from environment variables or a secure vault.
CERT_FILE = "server.crt"
KEY_FILE = "server.key"

clients = {}
clients_lock = threading.Lock()
group_members = {}
group_lock = threading.Lock()
login_attempts = defaultdict(lambda: [datetime.min, 0])
attempts_lock = threading.Lock()


# --------------------------------------------------
# SECURITY HELPERS
# --------------------------------------------------

def sanitize_text(text):
    """Prevent XSS/Injection by escaping HTML characters."""
    if not isinstance(text, str):
        return ""
    return html.escape(text.strip())

def check_rate_limit(ip):
    """Enforce login attempt limits to prevent brute force."""
    with attempts_lock:
        now = datetime.now()
        last_time, count = login_attempts[ip]
        if now - last_time > LOCKOUT_DURATION:
            login_attempts[ip] = [now, 0]
            return True
        if count >= LOGIN_ATTEMPTS_LIMIT:
            return False
        return True

def update_login_attempt(ip, success):
    """Track login attempts per IP."""
    with attempts_lock:
        now = datetime.now()
        if success:
            login_attempts[ip] = [now, 0]
        else:
            last_time, count = login_attempts[ip]
            login_attempts[ip] = [now, count + 1]


# --------------------------------------------------
# NETWORK HELPERS
# --------------------------------------------------

def send_to_user(username, message):
    with clients_lock:
        client_socket = clients.get(username)
    if client_socket is None:
        return False
    try:
        send_message(client_socket, message)
        return True
    except (OSError, ConnectionError, ValueError):
        return False

def broadcast(message, exclude_username=None):
    with clients_lock:
        connected_users = list(clients.items())
    for username, client_socket in connected_users:
        if username == exclude_username:
            continue
        try:
            send_message(client_socket, message)
        except (OSError, ConnectionError, ValueError):
            pass

def send_user_list(client_socket):
    with clients_lock:
        usernames = sorted(clients.keys())
    send_message(client_socket, {"type": "user_list", "users": usernames})


# --------------------------------------------------
# GROUP LOGIC
# --------------------------------------------------

def send_group_message(group_name, message, exclude=None):
    with group_lock:
        members = list(group_members.get(group_name, set()))
    for username in members:
        if username != exclude:
            send_to_user(username, message)

def join_group(username, group_name):
    group_name = group_name.strip().lower()
    if not group_exists(group_name):
        send_to_user(username, {"type": "error", "message": f"Group '{group_name}' does not exist."})
        return
    with group_lock:
        already_joined = username in group_members.get(group_name, set())
    if not already_joined:
        try:
            add_group_membership(username, group_name)
        except Exception as error:
            print(f"DB Error: {error}")
            send_to_user(username, {"type": "error", "message": "Could not save membership."})
            return
        with group_lock:
            group_members.setdefault(group_name, set()).add(username)
        send_group_message(group_name, {"type": "group_member_joined", "group": group_name, "username": username}, exclude=username)
    send_to_user(username, {"type": "group_joined", "group": group_name})
    send_to_user(username, {"type": "group_history", "group": group_name, "messages": get_group_history(group_name, limit=50)})

def leave_group(username, group_name):
    group_name = group_name.strip().lower()
    with group_lock:
        is_member = username in group_members.get(group_name, set())
    if not is_member:
        send_to_user(username, {"type": "error", "message": f"You are not in group '{group_name}'."})
        return
    try:
        remove_group_membership(username, group_name)
    except Exception as error:
        print(f"DB Error: {error}")
        send_to_user(username, {"type": "error", "message": "Could not save membership change."})
        return
    with group_lock:
        members = group_members.get(group_name, set())
        members.discard(username)
        if not members:
            group_members.pop(group_name, None)
    send_to_user(username, {"type": "group_left", "group": group_name})
    send_group_message(group_name, {"type": "group_member_left", "group": group_name, "username": username})

def handle_group_message(username, message):
    raw_group = message.get("group", "")
    raw_text = message.get("message", "")
    if not isinstance(raw_group, str) or not isinstance(raw_text, str):
        send_to_user(username, {"type": "error", "message": "Invalid input."})
        return
    group_name = raw_group.strip().lower()
    text = sanitize_text(raw_text)
    if not group_name or not text:
        return
    with group_lock:
        is_member = username in group_members.get(group_name, set())
    if not is_member:
        send_to_user(username, {"type": "error", "message": "Join group first."})
        return
    if not group_exists(group_name):
        send_to_user(username, {"type": "error", "message": "Group does not exist."})
        return
    save_group_message(group_name, username, text)
    send_group_message(group_name, {"type": "group_message", "group": group_name, "sender": username, "message": text})


# --------------------------------------------------
# PRIVATE MESSAGES
# --------------------------------------------------

def handle_private_message(sender, recipient, message):
    with clients_lock:
        recipient_socket = clients.get(recipient)
    if recipient_socket is None:
        send_to_user(sender, {"type": "error", "message": f"User '{recipient}' is offline."})
        return
    sanitized_msg = sanitize_text(message)
    save_private_message(sender, recipient, sanitized_msg)
    try:
        send_message(recipient_socket, {"type": "private_message", "sender": sender, "message": sanitized_msg})
        send_to_user(sender, {"type": "private_message_sent", "recipient": recipient, "message": sanitized_msg})
    except (OSError, ConnectionError, ValueError):
        send_to_user(sender, {"type": "error", "message": "Delivery failed."})


# --------------------------------------------------
# AUTHENTICATION
# --------------------------------------------------

def authenticate_client(client_socket, address):
    ip = address[0]
    if not check_rate_limit(ip):
        send_message(client_socket, {"type": "error", "message": "Too many attempts. Locked out."})
        return None
    send_message(client_socket, {"type": "authentication_required"})
    while True:
        try:
            message = receive_message(client_socket)
        except Exception:
            return None
        if not isinstance(message, dict):
            continue
        message_type = message.get("type")
        if message_type == "register":
            username = message.get("username", "")
            password = message.get("password", "")
            if not isinstance(username, str) or not isinstance(password, str):
                send_message(client_socket, {"type": "registration_failed", "message": "Invalid details."})
                continue
            success, result = register_user(username, password)
            send_message(client_socket, {"type": "registration_success" if success else "registration_failed", "message": result})
        elif message_type == "login":
            username = message.get("username", "")
            password = message.get("password", "")
            if not isinstance(username, str) or not isinstance(password, str):
                send_message(client_socket, {"type": "login_failed", "message": "Invalid details."})
                continue
            username = username.strip()
            if not authenticate_user(username, password):
                update_login_attempt(ip, False)
                send_message(client_socket, {"type": "login_failed", "message": "Invalid credentials."})
                continue
            update_login_attempt(ip, True)
            with clients_lock:
                if username in clients:
                    send_message(client_socket, {"type": "login_failed", "message": "Already logged in."})
                    continue
                clients[username] = client_socket
            send_message(client_socket, {"type": "login_success", "username": username})
            broadcast({"type": "user_joined", "username": username}, exclude_username=username)
            send_user_list(client_socket)
            send_to_user(username, {"type": "my_groups_list", "groups": get_user_groups(username)})
            return username
        elif message_type == "logout":
            send_message(client_socket, {"type": "logout_success"})
            return None
        else:
            send_message(client_socket, {"type": "error", "message": "Auth required."})
    return None


# --------------------------------------------------
# MAIN HANDLER
# --------------------------------------------------

def handle_client(client_socket, address):
    username = None
    try:
        username = authenticate_client(client_socket, address)
        if username is None:
            return
        while True:
            message = receive_message(client_socket)
            if not isinstance(message, dict):
                continue
            message_type = message.get("type")
            if message_type == "public_message":
                text = sanitize_text(message.get("message", ""))
                if text:
                    save_public_message(username, text)
                    broadcast({"type": "public_message", "sender": username, "message": text})
            elif message_type == "private_message":
                recipient = message.get("recipient", "")
                text = message.get("message", "")
                if isinstance(recipient, str) and recipient.strip():
                    handle_private_message(username, recipient.strip(), text)
            elif message_type == "get_users":
                send_user_list(client_socket)
            elif message_type == "get_public_history":
                send_to_user(username, {"type": "public_history", "messages": get_public_history(limit=50)})
            elif message_type == "get_private_history":
                other = message.get("username", "")
                if isinstance(other, str) and other.strip():
                    send_to_user(username, {"type": "private_history", "username": other.strip(), "messages": get_private_history(username, other.strip(), limit=50)})
            elif message_type == "create_group":
                group = message.get("group", "")
                if isinstance(group, str):
                    success, result = create_group(group, username)
                    if success:
                        send_to_user(username, {"type": "group_created", "group": result, "message": f"Group '{result}' created."})
                    else:
                        send_to_user(username, {"type": "error", "message": result})
            elif message_type == "get_groups":
                send_to_user(username, {"type": "groups_list", "groups": get_groups()})
            elif message_type == "join_group":
                group = message.get("group", "")
                if isinstance(group, str) and group.strip():
                    join_group(username, group)
            elif message_type == "leave_group":
                group = message.get("group", "")
                if isinstance(group, str) and group.strip():
                    leave_group(username, group)
            elif message_type == "get_group_members":
                group = message.get("group", "")
                if isinstance(group, str) and group.strip():
                    group_name = group.strip().lower()
                    if group_exists(group_name):
                        with group_lock:
                            members = sorted(group_members.get(group_name, set()))
                        send_to_user(username, {"type": "group_members", "group": group_name, "members": members})
                    else:
                        send_to_user(username, {"type": "error", "message": "Group not found."})
            elif message_type == "group_message":
                handle_group_message(username, message)
            elif message_type == "get_group_history":
                group = message.get("group", "")
                if isinstance(group, str) and group.strip():
                    group_name = group.strip().lower()
                    with group_lock:
                        is_member = username in group_members.get(group_name, set())
                    if is_member:
                        send_to_user(username, {"type": "group_history", "group": group_name, "messages": get_group_history(group_name, limit=50)})
                    else:
                        send_to_user(username, {"type": "error", "message": "Join group first."})
            elif message_type == "logout":
                break
    except (ConnectionError, OSError):
        pass
    except Exception as e:
        print(f"Error handling {username or address}: {e}")
    finally:
        remove_client(username)
        try:
            client_socket.close()
        except OSError:
            pass

def remove_client(username):
    if username is None:
        return
    with clients_lock:
        socket = clients.pop(username, None)
    if socket:
        try:
            socket.close()
        except OSError:
            pass
        broadcast({"type": "user_left", "username": username})

def start_server():
    initialize_database()
    saved = get_all_group_memberships()
    with group_lock:
        group_members.clear()
        for row in saved:
            group_members.setdefault(row["group_name"].strip().lower(), set()).add(row["username"])

    # TLS Configuration
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
        print("TLS encryption enabled.")
    else:
        print("WARNING: TLS certificates not found. Server running in plaintext mode (vulnerable to MitM).")
        context = None

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print(f"NetChat secure server listening on {HOST}:{PORT}")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        try:
            while True:
                client_sock, addr = server_socket.accept()
                if context:
                    try:
                        client_sock = context.wrap_socket(client_sock, server_side=True)
                    except ssl.SSLError as e:
                        print(f"TLS Handshake failed: {e}")
                        client_sock.close()
                        continue
                executor.submit(handle_client, client_sock, addr)
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            server_socket.close()

if __name__ == "__main__":
    start_server()
