# 🌐 NetChat: Secure Multi-User Chat System

NetChat is a professional-grade, secure real-time communication system implemented in Python. Unlike standard socket examples, NetChat is built with a **"Security-First"** mindset, incorporating industry-standard protections against common network attacks and data breaches.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Security](https://img.shields.io/badge/Security-Hardened-green.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)

## ✨ Features

### 💬 Communication
- **Public Lounge**: A global broadcast channel for all connected users.
- **Direct Messaging**: Private, one-to-one conversations.
- **Group Rooms**: Create, join, and leave named rooms with persistent membership.
- **Real-time Presence**: Live updates when users join or leave the network.
- **Message History**: Persistent archives for public, private, and group chats.

### 🛡️ Security Hardening
- **Transport Layer Security (TLS)**: Full support for SSL/TLS wrapping to prevent Man-in-the-Middle (MitM) sniffing.
- **Password Security**: Uses **PBKDF2-HMAC-SHA256** with unique salts and 600,000 iterations for password storage.
- **DoS Protection**: 
    - **Payload Capping**: Maximum message size limited to 64KB to prevent memory exhaustion.
    - **Thread Pooling**: Uses `ThreadPoolExecutor` to prevent thread-exhaustion crashes.
- **Brute-Force Mitigation**: IP-based rate limiting with a 15-minute lockout after 5 failed attempts.
- **Injection Prevention**: 
    - **SQLi**: All database interactions use parameterized queries.
    - **XSS**: All outgoing messages are sanitized via HTML escaping.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10 or higher.
- (Optional) OpenSSL for generating TLS certificates.

### 1. Installation
Clone the repository and navigate to the project root:
```bash
git clone https://github.com/YOUR_USERNAME/netchat.git
cd netchat
```

### 2. SSL Certificate Setup (For Encryption)
To enable the secure TLS mode, generate a self-signed certificate in the root folder:
```bash
# Generate private key
openssl genrsa -out server.key 2048

# Generate certificate (Enter 127.0.0.1 as the Common Name)
openssl req -new -x509 -sha256 -key server.key -out server.crt -days 365
```

### 3. Running the Application
**Start the Server:**
```powershell
python -m server.server
```

**Start the Client:**
```powershell
python -m client.gui
```

---

## 🏗️ Architecture

### Technical Stack
- **Language**: Python 3.10+
- **GUI**: Tkinter (Modern Soft-Light Theme)
- **Database**: SQLite 3
- **Network**: TCP Sockets with a custom length-prefixed JSON framing protocol.

### Protocol Format
Every message sent over the wire follows this frame:
`[4-byte Big-Endian Length] + [UTF-8 JSON Payload]`

---

## 📂 Project Structure
```text
netchat/
├── client/         # GUI and Client Logic
├── server/         # Multi-threaded Secure Server
├── database/       # SQLite Persistence & Hashing
├── shared/         # Communication Protocol
├── docs/           # PRD, TRD, and Implementation Plans
└── tests/          # Unit tests for Protocol and DB
```

## 📜 License
This project is licensed under the MIT License.
