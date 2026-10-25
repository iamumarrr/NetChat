# Product Requirement Document (PRD) - NetChat

## 1. Introduction
NetChat is a secure, multi-user desktop chat application allowing real-time communication via public rooms, private direct messages, and persistent group chats.

## 2. Goals & Objectives
- Provide a lightweight, secure communication tool.
- Ensure data persistence across sessions.
- Implement "Security by Design" to prevent common network attacks.

## 3. Target Audience
- Users seeking a private, self-hosted chat alternative.
- Developers looking for a reference implementation of secure TCP socket communication.

## 4. Functional Requirements
- **User Management**: Registration and secure authentication.
- **Public Chat**: A global room for all connected users.
- **Private Messaging**: One-to-one encrypted-ready communication.
- **Group Chats**: Ability to create, join, and persist membership in named rooms.
- **Presence**: Real-time visibility of online users.
- **History**: Retrieval of past messages for public, private, and group chats.

## 5. Non-Functional Requirements
- **Security**: Mandatory TLS support, password hashing (PBKDF2), and rate limiting.
- **Performance**: Support for up to 100 concurrent connections.
- **Reliability**: SQLite-backed persistence for all critical data.
- **Availability**: Server-side thread pooling to prevent resource exhaustion.
