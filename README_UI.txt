# NetChat Tkinter Desktop UI

This UI is an additional client for the existing NetChat TCP server. It does not replace
`server.py`, `shared/protocol.py`, or the SQLite database.

## Install / run (PowerShell)

Open PowerShell in the existing project root:

```powershell
cd "A:\Mac\Projects\Projects\netchat"
python -m compileall client shared
python -m server.server
```

Keep the server terminal open. Open a second PowerShell terminal:

```powershell
cd "A:\Mac\Projects\Projects\netchat"
python -m client.gui
```

If your server uses a different port than `5000`, enter the actual port in the UI's
Server port field. The default host is `127.0.0.1`.

## Features
- Login and registration using existing server requests.
- Public chat and public message history.
- Private messages and private history.
- Online users.
- Create, list, join, leave, and send messages to groups.
- Group history and online group member count when returned by the server.

## Notes
- Run the server before opening the UI.
- The UI imports `send_message` and `receive_message` from the existing `shared.protocol`.
- It does not change the database or server code.
- Active group membership is maintained by the existing server and may reset when the
  server restarts, depending on the current server implementation.
