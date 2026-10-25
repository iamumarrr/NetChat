# App Flow Document - NetChat

## 1. Connection & Authentication Flow
`Client` $\rightarrow$ `TCP Connect` $\rightarrow$ `TLS Handshake` $\rightarrow$ `Server`
1. **Handshake**: Server sends `authentication_required`.
2. **Identity**: Client sends `register` or `login` request.
3. **Validation**: Server checks rate limits $\rightarrow$ Verifies hash in DB.
4. **Session**: Server sends `login_success` $\rightarrow$ Client enters Main Chat.

## 2. Messaging Flow
### Public Chat
`User A` $\rightarrow$ `public_message` $\rightarrow$ `Server` $\rightarrow$ `Save to DB` $\rightarrow$ `Broadcast to all`

### Private Chat
`User A` $\rightarrow$ `private_message(User B)` $\rightarrow$ `Server` $\rightarrow$ `Save to DB` $\rightarrow$ `Route to User B Socket`

### Group Chat
`User` $\rightarrow$ `join_group(GroupName)` $\rightarrow$ `Server` $\rightarrow$ `Verify/Save Membership` $\rightarrow$ `Send Group History`

## 3. Disconnection Flow
`Client Socket Close` $\rightarrow$ `Server` $\rightarrow$ `Remove from Online Map` $\rightarrow$ `Broadcast user_left`
