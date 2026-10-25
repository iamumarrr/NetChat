# Backend Schema - NetChat

## 1. Entity Relationship Diagram (Logical)
- **User** (1) $\rightarrow$ (N) **Messages**
- **User** (N) $\rightarrow$ (M) **Groups** (via `group_memberships`)
- **Group** (1) $\rightarrow$ (N) **GroupMessages**

## 2. Table Definitions

### Table: `users`
| Column | Type | Constraint | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PK, AI | Unique User ID |
| `username` | TEXT | UNIQUE, NOT NULL | User login name |
| `password_hash` | TEXT | NOT NULL | PBKDF2 hash |
| `salt` | TEXT | NOT NULL | Random salt for hashing |
| `created_at` | TEXT | NOT NULL | ISO timestamp |

### Table: `messages` (Public & Private)
| Column | Type | Constraint | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PK, AI | Message ID |
| `sender` | TEXT | NOT NULL | Username of sender |
| `recipient` | TEXT | NULLABLE | NULL for Public, Username for Private |
| `message` | TEXT | NOT NULL | Sanitized content |
| `created_at` | TEXT | NOT NULL | ISO timestamp |

### Table: `groups`
| Column | Type | Constraint | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PK, AI | Group ID |
| `name` | TEXT | UNIQUE, NOT NULL | Room name (Case Insensitive) |
| `created_by` | TEXT | NOT NULL | Admin username |
| `created_at` | TEXT | NOT NULL | ISO timestamp |

### Table: `group_messages`
| Column | Type | Constraint | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PK, AI | Message ID |
| `group_name` | TEXT | NOT NULL | FK to `groups.name` |
| `sender` | TEXT | NOT NULL | Username of sender |
| `message` | TEXT | NOT NULL | Sanitized content |
| `created_at` | TEXT | NOT NULL | ISO timestamp |

### Table: `group_memberships`
| Column | Type | Constraint | Description |
| :--- | :--- | :--- | :--- |
| `group_name` | TEXT | PK, NOT NULL | FK to `groups.name` |
| `username` | TEXT | PK, NOT NULL | User belonging to group |
| `joined_at` | TEXT | NOT NULL | ISO timestamp |
