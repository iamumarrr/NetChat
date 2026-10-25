# Technical Requirement Document (TRD) - NetChat

## 1. System Architecture
- **Pattern**: Client-Server Architecture.
- **Communication**: TCP Sockets using a custom framed JSON protocol.
- **Concurrency**: Multi-threaded server using `ThreadPoolExecutor`.

## 2. Tech Stack
- **Language**: Python 3.10+
- **Database**: SQLite 3
- **Encryption**: `ssl` module for TLS, `hashlib` (PBKDF2-HMAC-SHA256) for passwords.
- **UI**: Tkinter (Desktop GUI).

## 3. Networking Specification
- **Frame Format**: `[4-byte Length Header] + [UTF-8 JSON Payload]`.
- **Port**: Default 5000.
- **Payload Limit**: 64KB per message to prevent Memory DoS.

## 4. Security Specifications
- **Transport**: TLS 1.2/1.3 mandatory for production.
- **Authentication**: Salted password hashing with 600,000 iterations.
- **Access Control**: Group memberships validated on the server before message delivery.
- **Anti-Brute Force**: IP-based rate limiting (5 attempts / 15 min lockout).

## 5. Database Requirements
- **ACID Compliance**: Guaranteed by SQLite.
- **Indexing**: B-Tree indexes on `messages(recipient)` and `group_messages(group_name)` for $O(\log n)$ history retrieval.
