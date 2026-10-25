
"""
NetChat desktop UI (Tkinter) — Obsidian & Indigo Edition
Run from the project root with: python -m client.gui

Uses the existing shared.protocol framing and existing server request types.
Does not access or modify the SQLite database directly.
"""
from __future__ import annotations

import queue
import socket
import threading
import ssl
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from datetime import datetime

from shared.protocol import send_message, receive_message


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = "5000"

# ─── Modern Obsidian & Electric Indigo Palette ───────────────────────────────
BG = "#0B0F19"               # Deep obsidian background
SIDEBAR_BG = "#111827"       # Slate dark sidebar
PANEL = "#161F33"            # Elevated surface / panel
CARD_BG = "#1E293B"          # Login & modal card surface
CHAT_BG = "#0D1322"          # Conversation canvas background
INPUT_BG = "#0F172A"         # Text entry surface
BORDER = "#26334D"           # Subtle hairline border
BORDER_FOCUS = "#6366F1"     # Active input border

TEXT = "#F8FAFC"             # Crisp alabaster primary text
TEXT_SUB = "#CBD5E1"         # Secondary readable text
MUTED = "#64748B"            # Muted captions & timestamps

ACCENT = "#6366F1"           # Electric Indigo primary accent
ACCENT_HOVER = "#4F46E5"     # Deep Indigo hover state
ACCENT_SOFT = "#1E1B4B"      # Subtle indigo tint for active nav
CYAN = "#06B6D4"             # Cyber cyan secondary accent
GREEN = "#10B981"            # Emerald online indicator
AMBER = "#F59E0B"            # Warning / system notice
ERROR = "#EF4444"            # Coral crimson error

BUBBLE_MINE = "#312E81"      # Outgoing message bubble fill
BUBBLE_MINE_BORDER = "#4338CA"
BUBBLE_OTHER = "#1E293B"     # Incoming message bubble fill
BUBBLE_OTHER_BORDER = "#334155"
SYSTEM_PILL = "#172036"      # System event badge background

AVATAR_COLORS = [
    "#6366F1", "#06B6D4", "#10B981", "#F59E0B",
    "#EC4899", "#8B5CF6", "#14B8A6", "#F97316",
]


def _avatar_color(name: str) -> str:
    if not name:
        return ACCENT
    return AVATAR_COLORS[sum(ord(ch) for ch in name) % len(AVATAR_COLORS)]


class NetChatApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("NetChat")
        self.root.geometry("1160x760")
        self.root.minsize(920, 620)
        self.root.configure(bg=BG)

        self.sock: socket.socket | None = None
        self.send_lock = threading.Lock()
        self.incoming: queue.Queue[dict] = queue.Queue()
        self.reader_thread: threading.Thread | None = None
        self.logged_in = False
        self.username = ""
        self.current_view = "public"   # public, private, group
        self.current_target = ""
        self.online_users: list[str] = []
        self.groups: list[str] = []
        self.joined_groups: set[str] = set()
        self.closing = False
        self._show_password = False

        self._configure_styles()
        self._build_login()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self._process_incoming)

    def _configure_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure(
            "TLabel",
            background=BG,
            foreground=TEXT,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Title.TLabel",
            background=BG,
            foreground=TEXT,
            font=("Segoe UI Semibold", 24),
        )
        style.configure(
            "Sub.TLabel",
            background=BG,
            foreground=MUTED,
            font=("Segoe UI", 10),
        )
        style.configure(
            "PanelTitle.TLabel",
            background=PANEL,
            foreground=TEXT,
            font=("Segoe UI Semibold", 11),
        )

        # Primary Accent Button
        style.configure(
            "Accent.TButton",
            font=("Segoe UI Semibold", 10),
            padding=(16, 10),
            background=ACCENT,
            foreground="#FFFFFF",
            borderwidth=0,
            focusthickness=0,
        )
        style.map(
            "Accent.TButton",
            background=[("active", ACCENT_HOVER), ("pressed", ACCENT_HOVER)],
            foreground=[("active", "#FFFFFF")],
        )

        # Secondary Ghost / Slate Button
        style.configure(
            "TButton",
            padding=(12, 8),
            font=("Segoe UI Semibold", 9),
            background=CARD_BG,
            foreground=TEXT_SUB,
            borderwidth=1,
            relief="flat",
            focusthickness=0,
        )
        style.map(
            "TButton",
            background=[("active", "#28354D"), ("pressed", "#334155")],
            foreground=[("active", TEXT)],
        )

        # Danger / Leave Button
        style.configure(
            "Danger.TButton",
            padding=(12, 8),
            font=("Segoe UI Semibold", 9),
            background="#2A1621",
            foreground="#FCA5A5",
            borderwidth=0,
            focusthickness=0,
        )
        style.map(
            "Danger.TButton",
            background=[("active", "#451A2B"), ("pressed", "#451A2B")],
            foreground=[("active", "#FEE2E2")],
        )

        # Modern Dark Entry
        style.configure(
            "TEntry",
            padding=10,
            fieldbackground=INPUT_BG,
            background=INPUT_BG,
            foreground=TEXT,
            insertcolor=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            borderwidth=1,
        )
        style.map(
            "TEntry",
            bordercolor=[("focus", BORDER_FOCUS)],
            lightcolor=[("focus", BORDER_FOCUS)],
        )

        # Subtle Dark Scrollbar
        style.configure(
            "Vertical.TScrollbar",
            gripcount=0,
            background=PANEL,
            darkcolor=CHAT_BG,
            lightcolor=CHAT_BG,
            troughcolor=CHAT_BG,
            bordercolor=CHAT_BG,
            arrowcolor=MUTED,
            width=10,
        )
        style.map(
            "Vertical.TScrollbar",
            background=[("active", BORDER_FOCUS), ("!disabled", "#26334D")],
        )

    def _clear_root(self):
        for child in self.root.winfo_children():
            child.destroy()

    # ─── Authentication View ─────────────────────────────────────────────────
    def _build_login(self):
        self._clear_root()
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill="both", expand=True)

        # Ambient top accent bar
        accent_bar = tk.Frame(outer, bg=ACCENT, height=3)
        accent_bar.pack(fill="x", side="top")

        # Centered container
        card_border = tk.Frame(outer, bg=BORDER, padx=1, pady=1)
        card_border.place(relx=0.5, rely=0.5, anchor="center", width=468)

        card = tk.Frame(card_border, bg=PANEL, padx=40, pady=36)
        card.pack(fill="both", expand=True)

        # Brand Header
        brand_row = tk.Frame(card, bg=PANEL)
        brand_row.pack(fill="x")

        badge = tk.Label(
            brand_row,
            text="◈",
            bg=ACCENT_SOFT,
            fg=ACCENT,
            font=("Segoe UI Semibold", 14),
            padx=9,
            pady=3,
        )
        badge.pack(side="left")

        tk.Label(
            brand_row,
            text="NetChat",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 15),
        ).pack(side="left", padx=(10, 0))

        tk.Label(
            brand_row,
            text="DESKTOP v2",
            bg=CARD_BG,
            fg=CYAN,
            font=("Segoe UI Semibold", 8),
            padx=7,
            pady=2,
        ).pack(side="right")

        tk.Label(
            card,
            text="Connect to your workspace.",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 22),
            wraplength=380,
            justify="left",
        ).pack(anchor="w", pady=(20, 4))

        tk.Label(
            card,
            text="Sign in to an active server or register a new handle to start chatting in real time.",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 10),
            wraplength=380,
            justify="left",
        ).pack(anchor="w", pady=(0, 22))

        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        self.port_var = tk.StringVar(value=DEFAULT_PORT)
        self.login_user_var = tk.StringVar()
        self.login_pass_var = tk.StringVar()

        # Side-by-side Server Host & Port
        net_row = tk.Frame(card, bg=PANEL)
        net_row.pack(fill="x", pady=(0, 12))

        host_col = tk.Frame(net_row, bg=PANEL)
        host_col.pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Label(
            host_col,
            text="SERVER HOST",
            bg=PANEL,
            fg=TEXT_SUB,
            font=("Segoe UI Semibold", 8),
        ).pack(anchor="w", pady=(0, 5))
        ttk.Entry(host_col, textvariable=self.host_var).pack(fill="x")

        port_col = tk.Frame(net_row, bg=PANEL, width=115)
        port_col.pack(side="right", fill="y")
        port_col.pack_propagate(False)
        tk.Label(
            port_col,
            text="PORT",
            bg=PANEL,
            fg=TEXT_SUB,
            font=("Segoe UI Semibold", 8),
        ).pack(anchor="w", pady=(0, 5))
        ttk.Entry(port_col, textvariable=self.port_var).pack(fill="x")

        user_entry = self._field(card, "USERNAME", self.login_user_var)
        self._password_field(card, "PASSWORD", self.login_pass_var)

        # Status banner inside login
        status_box = tk.Frame(
            card,
            bg=INPUT_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=12,
            pady=9,
        )
        status_box.pack(fill="x", pady=(4, 18))

        self.auth_status_dot = tk.Label(
            status_box,
            text="●",
            bg=INPUT_BG,
            fg=CYAN,
            font=("Segoe UI", 9),
        )
        self.auth_status_dot.pack(side="left", padx=(0, 8))

        self.auth_status = tk.StringVar(
            value="Server must be running before you connect."
        )
        tk.Label(
            status_box,
            textvariable=self.auth_status,
            bg=INPUT_BG,
            fg=TEXT_SUB,
            font=("Segoe UI", 9),
            wraplength=330,
            justify="left",
        ).pack(side="left", fill="x")

        buttons = tk.Frame(card, bg=PANEL)
        buttons.pack(fill="x")
        ttk.Button(
            buttons,
            text="Sign In  →",
            style="Accent.TButton",
            command=self.login,
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(
            buttons,
            text="Create Account",
            command=self.register,
        ).pack(side="left", fill="x", expand=True, padx=(6, 0))

        user_entry.focus_set()
        self.root.bind("<Return>", lambda _event: self.login())

    def _field(self, parent, label, variable, show=None):
        tk.Label(
            parent,
            text=label,
            bg=PANEL,
            fg=TEXT_SUB,
            font=("Segoe UI Semibold", 8),
        ).pack(anchor="w", pady=(0, 5))
        entry = ttk.Entry(parent, textvariable=variable, show=show)
        entry.pack(fill="x", pady=(0, 12))
        return entry

    def _password_field(self, parent, label, variable):
        header = tk.Frame(parent, bg=PANEL)
        header.pack(fill="x", pady=(0, 5))
        tk.Label(
            header,
            text=label,
            bg=PANEL,
            fg=TEXT_SUB,
            font=("Segoe UI Semibold", 8),
        ).pack(side="left")

        self._show_password = False
        toggle_lbl = tk.Label(
            header,
            text="Show",
            bg=PANEL,
            fg=ACCENT,
            font=("Segoe UI Semibold", 8),
            cursor="hand2",
        )
        toggle_lbl.pack(side="right")

        entry = ttk.Entry(parent, textvariable=variable, show="●")
        entry.pack(fill="x", pady=(0, 12))

        def _toggle(_e=None):
            self._show_password = not self._show_password
            entry.configure(show="" if self._show_password else "●")
            toggle_lbl.configure(text="Hide" if self._show_password else "Show")

        toggle_lbl.bind("<Button-1>", _toggle)
        return entry

    # ─── Networking & Protocol Handling ──────────────────────────────────────
    def _connect(self) -> bool:
        if self.sock is not None:
            return True
        host = self.host_var.get().strip()
        try:
            port = int(self.port_var.get().strip())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            self.auth_status.set("Enter a valid TCP port from 1 to 65535.")
            return False
        try:
            raw_socket = socket.create_connection((host, port), timeout=6)

            # Wrap the socket with SSL/TLS
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            client_socket = context.wrap_socket(raw_socket, server_hostname=host)
            client_socket.settimeout(None)
        except (OSError, socket.timeout, ssl.SSLError) as error:
            self.auth_status.set(f"Secure connection failed: {error}")
            return False

        self.sock = client_socket
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()
        return True

    def _send(self, payload: dict):
        sock = self.sock
        if sock is None:
            raise ConnectionError("Not connected to the server.")
        with self.send_lock:
            send_message(sock, payload)

    def login(self):
        if self.logged_in:
            return
        username = self.login_user_var.get().strip()
        password = self.login_pass_var.get()
        if not username or not password:
            self.auth_status.set("Enter both username and password.")
            return
        if not self._connect():
            return
        try:
            self._send({"type": "login", "username": username, "password": password})
            self.auth_status.set("Authenticating with server…")
        except (OSError, ConnectionError, ValueError) as error:
            self.auth_status.set(f"Could not send login request: {error}")
            self._disconnect_socket()

    def register(self):
        if self.logged_in:
            return
        username = self.login_user_var.get().strip()
        password = self.login_pass_var.get()
        if not username or not password:
            self.auth_status.set("Choose a username and password first.")
            return
        if len(password) < 6:
            self.auth_status.set("Use a password with at least 6 characters.")
            return
        if not self._connect():
            return
        try:
            self._send({"type": "register", "username": username, "password": password})
            self.auth_status.set("Creating your account…")
        except (OSError, ConnectionError, ValueError) as error:
            self.auth_status.set(f"Could not send registration request: {error}")
            self._disconnect_socket()

    def _reader_loop(self):
        while not self.closing:
            sock = self.sock
            if sock is None:
                return
            try:
                message = receive_message(sock)
            except (OSError, ConnectionError, ValueError) as error:
                self.incoming.put({"type": "_disconnected", "message": str(error)})
                return
            self.incoming.put(message)

    def _process_incoming(self):
        if self.closing:
            return
        try:
            while True:
                message = self.incoming.get_nowait()
                self._handle_message(message)
        except queue.Empty:
            pass
        self.root.after(100, self._process_incoming)

    def _handle_message(self, message: dict):
        kind = message.get("type", "")

        if kind == "authentication_required":
            return
        if kind == "_disconnected":
            if self.logged_in:
                self.status_var.set("Disconnected from server")
                self.logged_in = False
                self._build_login()
                self.auth_status.set(
                    "Connection closed. Check the server and sign in again."
                )
            else:
                self.auth_status.set(
                    "Connection closed. Check the server address and try again."
                )
            self._disconnect_socket()
            return

        if kind == "registration_success":
            self.auth_status.set(
                message.get("message", "Account created. You can sign in now.")
            )
            self._disconnect_socket()
            return
        if kind == "registration_failed":
            self.auth_status.set(message.get("message", "Registration failed."))
            self._disconnect_socket()
            return
        if kind == "login_failed":
            self.auth_status.set(message.get("message", "Login failed."))
            self._disconnect_socket()
            return
        if kind == "login_success":
            self.username = message.get(
                "username", self.login_user_var.get().strip()
            )
            self.logged_in = True
            self._build_chat()
            self.status_var.set(f"Connected as {self.username}")
            self._send_safe({"type": "get_users"})
            self._send_safe({"type": "get_public_history"})
            self._send_safe({"type": "get_groups"})
            return

        if not self.logged_in:
            if kind == "error":
                self.auth_status.set(message.get("message", "Server error."))
            return

        if kind in ("users_list", "user_list", "online_users"):
            users = message.get("users", message.get("online_users", []))
            if isinstance(users, list):
                self.online_users = sorted(
                    u for u in users if isinstance(u, str) and u != self.username
                )
                self._refresh_user_list()
            return

        if kind == "user_joined":
            user = message.get("username")
            if user and user != self.username and user not in self.online_users:
                self.online_users.append(user)
                self.online_users.sort()
                self._refresh_user_list()
            self._system_message(f"●  {user} came online.")
            return
        if kind == "user_left":
            user = message.get("username")
            if user in self.online_users:
                self.online_users.remove(user)
                self._refresh_user_list()
            self._system_message(f"○  {user} went offline.")
            return

        if kind == "public_history":
            for item in message.get("messages", []):
                self._append_message(
                    item.get("sender", "?"),
                    item.get("message", ""),
                    item.get("created_at"),
                    "public",
                    "",
                    history=True,
                )
            self._scroll_chat()
            return
        if kind == "public_message":
            self._append_message(
                message.get("sender", "?"),
                message.get("message", ""),
                None,
                "public",
                "",
            )
            return

        if kind == "private_history":
            peer = message.get("username", "")
            for item in message.get("messages", []):
                self._append_message(
                    item.get("sender", "?"),
                    item.get("message", ""),
                    item.get("created_at"),
                    "private",
                    peer,
                    history=True,
                )
            self._scroll_chat()
            return
        if kind == "private_message":
            sender = message.get("sender", "")
            if self.current_view == "private" and self.current_target == sender:
                self._append_message(
                    sender, message.get("message", ""), None, "private", sender
                )
            else:
                self._system_message(
                    f"✉  New direct message from {sender}. Select their name in Direct Messages to view."
                )
            return
        if kind == "private_message_sent":
            recipient = message.get("recipient", self.current_target)
            self._append_message(
                self.username,
                message.get("message", ""),
                None,
                "private",
                recipient,
            )
            return

        if kind == "groups_list":
            raw_groups = message.get("groups", [])
            parsed = []
            for group in raw_groups:
                if isinstance(group, str):
                    parsed.append(group)
                elif isinstance(group, dict):
                    name = group.get("name", group.get("group"))
                    if name:
                        parsed.append(str(name))
            self.groups = sorted(set(parsed))
            self._refresh_group_list()
            return
        if kind == "group_created":
            group = message.get("group", "")
            self._system_message(message.get("message", f"Created group #{group}."))
            self._send_safe({"type": "get_groups"})
            if group:
                self._send_safe({"type": "join_group", "group": group})
            return
        if kind == "group_joined":
            group = message.get("group", "")
            self.joined_groups.add(group)
            self.current_view, self.current_target = "group", group
            self._refresh_group_list()
            self._set_chat_header()
            self._clear_chat()
            self._send_safe({"type": "get_group_history", "group": group})
            self._send_safe({"type": "get_group_members", "group": group})
            self._system_message(f"You joined #{group}.")
            return
        if kind == "group_left":
            group = message.get("group", "")
            self.joined_groups.discard(group)
            self._refresh_group_list()
            if self.current_view == "group" and self.current_target == group:
                self.current_view, self.current_target = "public", ""
                self._set_chat_header()
                self._clear_chat()
            self._system_message(f"You left #{group}.")
            return
        if kind == "group_history":
            group = message.get("group", "")
            for item in message.get("messages", []):
                if isinstance(item, dict):
                    self._append_message(
                        item.get("sender", "?"),
                        item.get("message", ""),
                        item.get("created_at"),
                        "group",
                        group,
                        history=True,
                    )
            self._scroll_chat()
            return
        if kind == "group_message":
            group = message.get("group", "")
            if self.current_view == "group" and self.current_target == group:
                self._append_message(
                    message.get("sender", "?"),
                    message.get("message", ""),
                    None,
                    "group",
                    group,
                )
            else:
                self._system_message(f"#  New message in #{group}.")
            return
        if kind in ("group_member_joined", "group_member_left"):
            who = message.get("username", "A member")
            group = message.get("group", "")
            verb = "joined" if kind == "group_member_joined" else "left"
            if self.current_view == "group" and self.current_target == group:
                self._system_message(f"{who} {verb} #{group}.")
            return
        if kind == "group_members":
            group = message.get("group", "")
            members = message.get("members", [])
            if self.current_view == "group" and self.current_target == group:
                self.header_detail_var.set(
                    f"Group channel  ·  {len(members)} active member(s)"
                )
            return
        if kind == "error":
            text = message.get("message", "An error occurred.")
            self._system_message(f"⚠  {text}")
            if not self.logged_in:
                self.auth_status.set(text)
            return
        if kind == "logout_success":
            self.logged_in = False
            self._disconnect_socket()
            self._build_login()
            self.auth_status.set("You have signed out.")
            return

    # ─── Main Workspace UI ───────────────────────────────────────────────────
    def _build_chat(self):
        self._clear_root()
        self.root.unbind("<Return>")

        # Top accent hairline
        tk.Frame(self.root, bg=ACCENT, height=2).pack(fill="x", side="top")

        shell = tk.Frame(self.root, bg=BG)
        shell.pack(fill="both", expand=True, padx=16, pady=14)

        # Top Navigation Bar
        top = tk.Frame(shell, bg=BG)
        top.pack(fill="x", pady=(0, 12))

        brand = tk.Frame(top, bg=BG)
        brand.pack(side="left")
        tk.Label(
            brand,
            text="◈",
            bg=ACCENT_SOFT,
            fg=ACCENT,
            font=("Segoe UI Semibold", 13),
            padx=8,
            pady=2,
        ).pack(side="left")
        tk.Label(
            brand,
            text="NetChat",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI Semibold", 17),
        ).pack(side="left", padx=(10, 8))
        tk.Label(
            brand,
            text="LIVE",
            bg="#06392F",
            fg=GREEN,
            font=("Segoe UI Semibold", 8),
            padx=7,
            pady=2,
        ).pack(side="left")

        # User Profile & Sign Out on right
        right_bar = tk.Frame(top, bg=BG)
        right_bar.pack(side="right")

        status_pill = tk.Frame(
            right_bar,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=12,
            pady=5,
        )
        status_pill.pack(side="left", padx=(0, 10))
        tk.Label(
            status_pill,
            text="●",
            bg=PANEL,
            fg=GREEN,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 6))
        self.status_var = tk.StringVar(value=f"Connected as {self.username}")
        tk.Label(
            status_pill,
            textvariable=self.status_var,
            bg=PANEL,
            fg=TEXT_SUB,
            font=("Segoe UI Semibold", 9),
        ).pack(side="left")

        ttk.Button(right_bar, text="Sign Out", command=self.logout).pack(side="right")

        # Main Split Body
        body = tk.Frame(shell, bg=BG)
        body.pack(fill="both", expand=True)

        # ── Left Navigation Sidebar ──
        sidebar = tk.Frame(
            body,
            bg=SIDEBAR_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            width=275,
        )
        sidebar.pack(side="left", fill="y", padx=(0, 14))
        sidebar.pack_propagate(False)

        # Workspace Channel Section
        tk.Label(
            sidebar,
            text="CHANNELS",
            bg=SIDEBAR_BG,
            fg=MUTED,
            font=("Segoe UI Semibold", 8),
        ).pack(anchor="w", padx=16, pady=(16, 6))

        self.public_btn = tk.Button(
            sidebar,
            text="  🌐   Public Lounge",
            anchor="w",
            bg=ACCENT_SOFT,
            fg=TEXT,
            activebackground=ACCENT,
            activeforeground="#FFFFFF",
            bd=0,
            relief="flat",
            padx=12,
            pady=9,
            cursor="hand2",
            font=("Segoe UI Semibold", 10),
            command=self.open_public,
        )
        self.public_btn.pack(fill="x", padx=12, pady=(0, 4))

        # Online People Section
        people_header = tk.Frame(sidebar, bg=SIDEBAR_BG)
        people_header.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(
            people_header,
            text="DIRECT MESSAGES",
            bg=SIDEBAR_BG,
            fg=MUTED,
            font=("Segoe UI Semibold", 8),
        ).pack(side="left")
        self.online_count_var = tk.StringVar(value="0")
        tk.Label(
            people_header,
            textvariable=self.online_count_var,
            bg=CARD_BG,
            fg=CYAN,
            font=("Segoe UI Semibold", 8),
            padx=6,
            pady=1,
        ).pack(side="right")

        users_frame = tk.Frame(
            sidebar,
            bg=INPUT_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        users_frame.pack(fill="x", padx=12)
        self.users_list = tk.Listbox(
            users_frame,
            height=8,
            bd=0,
            highlightthickness=0,
            activestyle="none",
            bg=INPUT_BG,
            fg=TEXT_SUB,
            selectbackground=ACCENT_SOFT,
            selectforeground=TEXT,
            font=("Segoe UI", 10),
        )
        self.users_list.pack(fill="x", padx=6, pady=6)
        self.users_list.bind("<<ListboxSelect>>", self._on_user_selected)

        # Groups Section
        group_header = tk.Frame(sidebar, bg=SIDEBAR_BG)
        group_header.pack(fill="x", padx=16, pady=(16, 6))
        tk.Label(
            group_header,
            text="GROUP ROOMS",
            bg=SIDEBAR_BG,
            fg=MUTED,
            font=("Segoe UI Semibold", 8),
        ).pack(side="left")

        new_grp_btn = tk.Button(
            group_header,
            text="＋ New",
            bg=CARD_BG,
            fg=ACCENT,
            activebackground=ACCENT,
            activeforeground="#FFFFFF",
            bd=0,
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            font=("Segoe UI Semibold", 8),
            command=self.create_group,
        )
        new_grp_btn.pack(side="right")

        groups_frame = tk.Frame(
            sidebar,
            bg=INPUT_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        groups_frame.pack(fill="both", expand=True, padx=12)
        self.groups_list = tk.Listbox(
            groups_frame,
            height=7,
            bd=0,
            highlightthickness=0,
            activestyle="none",
            bg=INPUT_BG,
            fg=TEXT_SUB,
            selectbackground=ACCENT_SOFT,
            selectforeground=TEXT,
            font=("Segoe UI", 10),
        )
        self.groups_list.pack(fill="both", expand=True, padx=6, pady=6)
        self.groups_list.bind("<<ListboxSelect>>", self._on_group_selected)

        group_buttons = tk.Frame(sidebar, bg=SIDEBAR_BG)
        group_buttons.pack(fill="x", padx=12, pady=12)
        ttk.Button(
            group_buttons,
            text="Join Room",
            command=self.join_selected_group,
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(
            group_buttons,
            text="Leave",
            style="Danger.TButton",
            command=self.leave_current_group,
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))

        # ── Main Conversation Panel ──
        main = tk.Frame(
            body,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        main.pack(side="left", fill="both", expand=True)

        # Chat Header
        header = tk.Frame(main, bg=PANEL, padx=22, pady=14)
        header.pack(fill="x")

        header_left = tk.Frame(header, bg=PANEL)
        header_left.pack(side="left", fill="x", expand=True)

        self.chat_badge_var = tk.StringVar(value="🌐")
        self.chat_badge = tk.Label(
            header_left,
            textvariable=self.chat_badge_var,
            bg=ACCENT_SOFT,
            fg=ACCENT,
            font=("Segoe UI Semibold", 13),
            padx=10,
            pady=6,
        )
        self.chat_badge.pack(side="left", padx=(0, 12))

        title_stack = tk.Frame(header_left, bg=PANEL)
        title_stack.pack(side="left", fill="x")

        self.chat_title_var = tk.StringVar(value="Public Lounge")
        self.header_detail_var = tk.StringVar(
            value="Broadcast messages to everyone currently online"
        )
        tk.Label(
            title_stack,
            textvariable=self.chat_title_var,
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 15),
        ).pack(anchor="w")
        tk.Label(
            title_stack,
            textvariable=self.header_detail_var,
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(2, 0))

        tk.Frame(main, bg=BORDER, height=1).pack(fill="x")

        # Scrollable Message Feed
        chat_area = tk.Frame(main, bg=CHAT_BG)
        chat_area.pack(fill="both", expand=True)
        self.chat_canvas = tk.Canvas(
            chat_area, bg=CHAT_BG, highlightthickness=0, bd=0
        )
        self.chat_scrollbar = ttk.Scrollbar(
            chat_area,
            orient="vertical",
            style="Vertical.TScrollbar",
            command=self.chat_canvas.yview,
        )
        self.chat_canvas.configure(yscrollcommand=self.chat_scrollbar.set)
        self.chat_scrollbar.pack(side="right", fill="y")
        self.chat_canvas.pack(side="left", fill="both", expand=True)

        self.messages_frame = tk.Frame(self.chat_canvas, bg=CHAT_BG)
        self.canvas_window = self.chat_canvas.create_window(
            (0, 0), window=self.messages_frame, anchor="nw"
        )
        self.messages_frame.bind("<Configure>", self._on_messages_configure)
        self.chat_canvas.bind("<Configure>", self._on_canvas_configure)
        self.chat_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.chat_canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.chat_canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

        # Bottom Message Composer
        tk.Frame(main, bg=BORDER, height=1).pack(fill="x")
        composer = tk.Frame(main, bg=PANEL, padx=18, pady=14)
        composer.pack(fill="x")

        self.message_var = tk.StringVar()
        self.message_entry = ttk.Entry(
            composer,
            textvariable=self.message_var,
            font=("Segoe UI", 10),
        )
        self.message_entry.pack(
            side="left", fill="x", expand=True, ipady=4, padx=(0, 12)
        )
        self.message_entry.bind("<Return>", lambda _event: self.send_chat_message())

        ttk.Button(
            composer,
            text="Send Message  ➤",
            style="Accent.TButton",
            command=self.send_chat_message,
        ).pack(side="right")
        self.message_entry.focus_set()

        self._refresh_user_list()
        self._refresh_group_list()
        self._clear_chat()
        self._system_message(
            "Welcome to NetChat. Choose a channel or direct message to start talking."
        )

    def _on_messages_configure(self, _event=None):
        if hasattr(self, "chat_canvas"):
            self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        if hasattr(self, "chat_canvas"):
            self.chat_canvas.itemconfigure(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        if hasattr(self, "chat_canvas") and event.delta:
            self.chat_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux(self, event):
        if not hasattr(self, "chat_canvas"):
            return
        if event.num == 4:
            self.chat_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.chat_canvas.yview_scroll(1, "units")

    def _scroll_chat(self):
        if hasattr(self, "chat_canvas"):
            self.root.after(40, lambda: self.chat_canvas.yview_moveto(1.0))

    def _clear_chat(self):
        if not hasattr(self, "messages_//frame"):
            return
        for child in self.messages_frame.winfo_children():
            child.destroy()

    def _append_message(
        self, sender, text, created_at=None, view=None, target="", history=False
    ):
        if not hasattr(self, "messages_frame"):
            return
        if view == "private" and not (
            self.current_view == "private" and target == self.current_target
        ):
            return
        if view == "group" and not (
            self.current_view == "group" and target == self.current_target
        ):
            return
        if view == "public" and self.current_view != "public":
            return

        mine = sender == self.username
        row = tk.Frame(self.messages_frame, bg=CHAT_BG)
        row.pack(fill="x", padx=20, pady=6)

        anchor = "e" if mine else "w"
        wrap = max(280, min(580, self.chat_canvas.winfo_width() - 190))

        bubble_bg = BUBBLE_MINE if mine else BUBBLE_OTHER
        bubble_border = BUBBLE_MINE_BORDER if mine else BUBBLE_OTHER_BORDER

        container = tk.Frame(row, bg=CHAT_BG)
        container.pack(anchor=anchor)

        # Avatar badge for incoming messages
        if not mine:
            initial = (sender[:1] or "?").upper()
            av_color = _avatar_color(sender)
            avatar = tk.Label(
                container,
                text=initial,
                bg=av_color,
                fg="#FFFFFF",
                font=("Segoe UI Semibold", 10),
                width=3,
                pady=4,
            )
            avatar.pack(side="left", anchor="n", padx=(0, 10), pady=(2, 0))

        bubble = tk.Frame(
            container,
            bg=bubble_bg,
            padx=14,
            pady=9,
            highlightbackground=bubble_border,
            highlightthickness=1,
        )
        bubble.pack(side="left")

        # Top Metadata Row (Sender + Timestamp)
        meta = tk.Frame(bubble, bg=bubble_bg)
        meta.pack(fill="x")

        heading = "You" if mine else sender
        name_color = "#C7D2FE" if mine else _avatar_color(sender)
        tk.Label(
            meta,
            text=heading,
            bg=bubble_bg,
            fg=name_color,
            font=("Segoe UI Semibold", 9),
        ).pack(side="left")

        timestamp = created_at
        if not timestamp:
            timestamp = datetime.now().strftime("%H:%M")
        elif isinstance(timestamp, str):
            timestamp = timestamp[-8:-3] if len(timestamp) >= 8 else timestamp

        tk.Label(
            meta,
            text=f"  ·  {timestamp}",
            bg=bubble_bg,
            fg="#94A3B8" if mine else MUTED,
            font=("Segoe UI", 8),
        ).pack(side="right")

        # Message Body
        tk.Label(
            bubble,
            text=text,
            bg=bubble_bg,
            fg=TEXT,
            font=("Segoe UI", 10),
            justify="left",
            wraplength=wrap,
            anchor="w",
        ).pack(anchor="w", pady=(4, 1))

        self._scroll_chat()

    def _system_message(self, text):
        if not hasattr(self, "messages_frame"):
            return
        row = tk.Frame(self.messages_frame, bg=CHAT_BG)
        row.pack(fill="x", padx=20, pady=7)
        pill = tk.Frame(
            row,
            bg=SYSTEM_PILL,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=14,
            pady=5,
        )
        pill.pack(anchor="center")
        tk.Label(
            pill,
            text=text,
            bg=SYSTEM_PILL,
            fg=TEXT_SUB,
            font=("Segoe UI", 9),
            wraplength=640,
        ).pack()
        self._scroll_chat()

    def _set_chat_header(self):
        if hasattr(self, "public_btn"):
            if self.current_view == "public":
                self.public_btn.configure(bg=ACCENT_SOFT, fg=TEXT)
            else:
                self.public_btn.configure(bg=SIDEBAR_BG, fg=TEXT_SUB)

        if self.current_view == "public":
            self.chat_badge_var.set("🌐")
            self.chat_title_var.set("Public Lounge")
            self.header_detail_var.set(
                "Broadcast messages to everyone currently online"
            )
        elif self.current_view == "private":
            self.chat_badge_var.set("💬")
            self.chat_title_var.set(self.current_target)
            self.header_detail_var.set("Encrypted-style direct conversation")
        else:
            self.chat_badge_var.set("#")
            self.chat_title_var.set(f"{self.current_target}")
            self.header_detail_var.set("Group room conversation")

    def open_public(self):
        if hasattr(self, "users_list"):
            self.users_list.selection_clear(0, tk.END)
        if hasattr(self, "groups_list"):
            self.groups_list.selection_clear(0, tk.END)
        self.current_view, self.current_target = "public", ""
        self._set_chat_header()
        self._clear_chat()
        self._send_safe({"type": "get_public_history"})

    def _on_user_selected(self, _event=None):
        selection = self.users_list.curselection()
        if not selection:
            return
        if hasattr(self, "groups_list"):
            self.groups_list.selection_clear(0, tk.END)
        peer = self.users_list.get(selection[0]).lstrip("● ").strip()
        if not peer:
            return
        self.current_view, self.current_target = "private", peer
        self._set_chat_header()
        self._clear_chat()
        self._send_safe({"type": "get_private_history", "username": peer})

    def _on_group_selected(self, _event=None):
        selection = self.groups_list.curselection()
        if not selection:
            return
        if hasattr(self, "users_list"):
            self.users_list.selection_clear(0, tk.END)
        group = self.groups_list.get(selection[0]).lstrip("●# ").strip()
        self.current_target = group
        self.current_view = "group"
        self._set_chat_header()
        self._clear_chat()
        if group in self.joined_groups:
            self._send_safe({"type": "get_group_history", "group": group})
            self._send_safe({"type": "get_group_members", "group": group})
            self._system_message(f"Viewing #{group}.")
        else:
            self._system_message(
                f"Click 'Join Room' in the sidebar to enter #{group} and send messages."
            )

    def _refresh_user_list(self):
        if hasattr(self, "online_count_var"):
            self.online_count_var.set(str(len(self.online_users)))
        if not hasattr(self, "users_list"):
            return
        self.users_list.delete(0, tk.END)
        for idx, user in enumerate(self.online_users):
            self.users_list.insert(tk.END, f"  ●   {user}")
            try:
                self.users_list.itemconfig(idx, fg=TEXT_SUB)
            except tk.TclError:
                pass

    def _refresh_group_list(self):
        if not hasattr(self, "groups_list"):
            return
        self.groups_list.delete(0, tk.END)
        for idx, group in enumerate(self.groups):
            joined = group in self.joined_groups
            prefix = "  ●   #" if joined else "      #"
            self.groups_list.insert(tk.END, f"{prefix}{group}")
            try:
                self.groups_list.itemconfig(
                    idx, fg=TEXT if joined else MUTED
                )
            except tk.TclError:
                pass

    def create_group(self):
        name = simpledialog.askstring(
            "Create group", "Choose a group name:", parent=self.root
        )
        if name and name.strip():
            self._send_safe({"type": "create_group", "group": name.strip()})

    def join_selected_group(self):
        selection = self.groups_list.curselection()
        if not selection:
            messagebox.showinfo(
                "Choose a group", "Select a group first.", parent=self.root
            )
            return
        group = self.groups_list.get(selection[0]).lstrip("●# ").strip()
        self._send_safe({"type": "join_group", "group": group})

    def leave_current_group(self):
        if self.current_view != "group" or not self.current_target:
            messagebox.showinfo(
                "Leave group",
                "Open a group conversation first.",
                parent=self.root,
            )
            return
        group = self.current_target
        self._send_safe({"type": "leave_group", "group": group})

    def send_chat_message(self):
        text = self.message_var.get().strip()
        if not text:
            return
        if self.current_view == "public":
            payload = {"type": "public_message", "message": text}
        elif self.current_view == "private":
            payload = {
                "type": "private_message",
                "recipient": self.current_target,
                "message": text,
            }
        elif self.current_view == "group":
            if self.current_target not in self.joined_groups:
                messagebox.showinfo(
                    "Join group",
                    "Join this group before sending messages.",
                    parent=self.root,
                )
                return
            payload = {
                "type": "group_message",
                "group": self.current_target,
                "message": text,
            }
        else:
            return
        if self._send_safe(payload):
            self.message_var.set("")

    def _send_safe(self, payload):
        try:
            self._send(payload)
            return True
        except (OSError, ConnectionError, ValueError) as error:
            self._system_message(f"Could not send message: {error}")
            return False

    def logout(self):
        if self.sock is not None:
            self._send_safe({"type": "logout"})
        else:
            self.logged_in = False
            self._disconnect_socket()
            self._build_login()

    def _disconnect_socket(self):
        sock, self.sock = self.sock, None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

    def on_close(self):
        self.closing = True
        if self.logged_in and self.sock is not None:
            try:
                self._send({"type": "logout"})
            except Exception:
                pass
        self._disconnect_socket()
        self.root.destroy()


def main():
    root = tk.Tk()
    NetChatApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
