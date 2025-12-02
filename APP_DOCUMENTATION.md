# NerdPool v3 - Application Documentation

## Overview

NerdPool is a multi-carpool management application that helps groups coordinate daily carpooling schedules. Users can manage multiple carpools, track who's driving or riding each day, and view historical data with filtering capabilities.

---

## Key Features

### 1. Multi-Carpool Support
- Users can belong to multiple carpools simultaneously
- Each carpool has its own members and schedule
- Easy switching between carpools via navbar dropdown
- Carpool context clearly displayed on all relevant pages

### 2. Role Management
- **Driver (D)**: Person driving on a given day
- **Rider (R)**: Person riding in the carpool
- **Off (O)**: Person not participating that day

### 3. Credit System
- Drivers earn +1 credit per rider on days they drive
- Riders lose -1 credit on days they ride
- Only counts days ≤ today with at least one driver
- Credits help balance driving responsibilities

### 4. Smart Driver Suggestions
- Algorithm suggests next driver based on:
  - Lowest credit balance among active members
  - Rotation order from last driver
  - Only suggests from members not marked "Off"

### 5. User Roles
- **Regular Users**: Can view/edit schedules and history for their carpools
- **Admins**: Full access to user management, carpool creation, audit logs, and diagnostics

---

## Application Architecture

### File Structure

```
NerdPool/
├── app_v3.py                 # Main Flask application entry point
├── auth.py                   # Authentication routes (login/logout)
├── db.py                     # Database connection and schema management
├── constants.py              # Application constants (role choices, etc.)
├── extensions.py             # Flask extensions initialization
├── template_helpers.py       # Helper functions for template context
├── templates.py              # All HTML templates (Jinja2)
│
├── routes_account.py         # User account settings and preferences
├── routes_admin.py           # Admin dashboard, users, audit, diagnostics
├── routes_carpools.py        # Carpool management (create, memberships)
├── routes_history.py         # Historical data viewing with filters
├── routes_today.py           # Schedule page (main interface)
│
├── migrate_legacy.py         # Incremental migration from legacy DB
├── migrate_legacy_fresh.py   # Fresh production migration script
└── requirements.txt          # Python dependencies
```

### Technology Stack

- **Backend**: Flask (Python web framework)
- **Database**: SQLite with row factory for dict-like access
- **Templates**: Jinja2 (inline templates in templates.py)
- **Authentication**: Session-based with SHA-256 password hashing
- **Styling**: Custom CSS with dark theme and glassmorphism

---

## Database Schema

### Tables

#### `users`
Stores user accounts and authentication.

```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  is_admin INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1
);
```

#### `carpools`
Defines carpool groups.

```sql
CREATE TABLE carpools (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE
);
```

#### `carpool_memberships`
Links users to carpools with display names and member keys.

```sql
CREATE TABLE carpool_memberships (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  carpool_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  member_key TEXT NOT NULL,        -- Short key like "CA", "ER", "SJ"
  display_name TEXT NOT NULL,      -- Display name like "Christian"
  active INTEGER NOT NULL DEFAULT 1,
  UNIQUE(carpool_id, member_key),
  UNIQUE(carpool_id, user_id),
  FOREIGN KEY(carpool_id) REFERENCES carpools(id) ON DELETE CASCADE,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

#### `entries`
Stores daily role assignments.

```sql
CREATE TABLE entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  day TEXT NOT NULL,               -- Date in YYYY-MM-DD format
  member_key TEXT NOT NULL,        -- Member key for display
  role TEXT NOT NULL CHECK(role IN ('D','R','O')),
  update_user TEXT DEFAULT 'admin',
  update_ts TEXT DEFAULT (CURRENT_TIMESTAMP),
  update_date TEXT,
  carpool_id INTEGER,              -- NULL for legacy entries
  user_id INTEGER                  -- NULL for legacy entries
);

CREATE UNIQUE INDEX idx_entries_cid_day_uid 
ON entries(carpool_id, day, user_id);
```

#### `user_prefs`
Global user preferences for fuel calculations.

```sql
CREATE TABLE user_prefs (
  user_id INTEGER PRIMARY KEY,
  gas_price REAL DEFAULT 4.78,
  avg_mpg REAL DEFAULT 22.0,
  miles_per_ride REAL DEFAULT 36.0,  -- Legacy mode only
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

#### `user_carpool_prefs`
Per-carpool preferences for miles per ride.

```sql
CREATE TABLE user_carpool_prefs (
  user_id INTEGER NOT NULL,
  carpool_id INTEGER NOT NULL,
  miles_per_ride REAL DEFAULT 36.0,
  avg_mpg REAL,                      -- Optional override
  PRIMARY KEY(user_id, carpool_id),
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY(carpool_id) REFERENCES carpools(id) ON DELETE CASCADE
);
```

---

## Business Rules

### 1. Schedule Editing Permissions

- **Regular users**: Can edit current day and up to 7 days in the past
- **Admins**: Can edit any date (past or future)
- Locked dates show "Save (locked)" button

### 2. Credit Calculation

```python
# Pseudo-code
for each day <= today:
    if day has at least one driver:
        for each driver:
            credits[driver] += count(riders)
        for each rider:
            credits[rider] -= 1
    # Days with no driver don't count
    # Future days don't count
```

### 3. Driver Suggestion Algorithm

```python
# Step 1: Filter active members (not "Off")
active_members = [m for m in members if role[m] != "O"]

# Step 2: Find members with lowest credits
min_credits = min(credits[m] for m in active_members)
candidates = [m for m in active_members if credits[m] == min_credits]

# Step 3: If tie, use rotation from last driver
if len(candidates) > 1:
    last_driver = find_last_driver(before_selected_day)
    next_in_rotation = member_after(last_driver, active_members)
    if next_in_rotation in candidates:
        return next_in_rotation

# Step 4: Return first candidate
return candidates[0]
```

### 4. Carpool Switching

- User selects carpool from navbar dropdown
- Sets `session['carpool_id']` and `session['carpool_name']`
- All pages filter data by current carpool
- Context header shows active carpool name

### 5. User Management

- Usernames are case-insensitive for lookup
- Passwords hashed with SHA-256 (consider upgrading to bcrypt/PBKDF2)
- Admin status required for:
  - Creating/deleting users
  - Creating/deleting carpools
  - Managing memberships
  - Viewing audit logs
  - Accessing diagnostics

### 6. Data Integrity

- Deleting a user cascades to:
  - `user_prefs`
  - `user_carpool_prefs`
  - `carpool_memberships`
  - `entries` (where user_id matches)
  
- Deleting a carpool cascades to:
  - `carpool_memberships`
  - `user_carpool_prefs`
  - `entries` (where carpool_id matches)

---

## Page Descriptions

### Schedule (Main Page)
**Route**: `/today`  
**Access**: All logged-in users

- View/edit roles for any date
- Date picker for selecting day
- Shows current carpool context
- Displays member roles and credits
- Smart driver suggestion callout
- Mobile-friendly date input

### History
**Route**: `/history`  
**Access**: Regular users (non-admins)

- View past carpool schedules
- Filter by date range
- Shows roles in table format
- Carpool context displayed
- Link to member stats

### Account
**Route**: `/account`  
**Access**: All logged-in users

- Change password
- Set fuel preferences (gas price, MPG)
- Set miles per ride for each carpool
- View estimated gas savings
- Summary of rides taken

### Admin Dashboard
**Route**: `/admin`  
**Access**: Admins only

Links to:
- User management
- Carpool management
- Membership management
- Audit logs
- System diagnostics

### Admin > Users
**Route**: `/admin/users`  
**Access**: Admins only

- Create new users
- Reset passwords
- Toggle admin status
- Delete users (with confirmation)

### Admin > Carpools
**Route**: `/carpools/admin`  
**Access**: Admins only

- Create new carpools
- Delete carpools (with confirmation)
- View all carpools

### Admin > Memberships
**Route**: `/carpools/memberships`  
**Access**: Admins only

- Add users to carpools
- Set member keys and display names
- Toggle active status
- View all memberships

### Admin > Audit
**Route**: `/admin/audit`  
**Access**: Admins only

- View all entry changes
- Filter by carpool, member, role, date range
- See who made changes and when
- Delete individual entries
- Search functionality

### Admin > Diagnostics
**Route**: `/admin/diag`  
**Access**: Admins only

- Database file information
- Entry counts and statistics
- Date range coverage
- Entries per year breakdown

---

## Session Variables

- `user_id`: Current user's ID
- `username`: Current user's username
- `is_admin`: Boolean (1 or 0) for admin status
- `carpool_id`: Currently selected carpool ID
- `carpool_name`: Currently selected carpool name

---

## Migration from Legacy

The app supports migration from a legacy single-carpool database:

### Legacy Schema
```sql
-- Old structure
members (key, name, active)
entries (day, member_key, role, update_user, update_ts, update_date)
```

### Migration Scripts

**`migrate_legacy.py`**: Incremental migration
- Adds entries to existing `np_data.db`
- Maps legacy member keys to new users
- Creates/uses target carpool
- Preserves existing data

**`migrate_legacy_fresh.py`**: Fresh start (recommended for production)
- Deletes existing `np_data.db`
- Creates fresh v3 schema
- Creates users with default passwords
- Migrates all legacy entries
- Clean production deployment

---

## Security Considerations

1. **Password Hashing**: Currently SHA-256 (consider upgrading to bcrypt)
2. **Session Management**: Flask sessions with secret key
3. **SQL Injection**: Protected via parameterized queries
4. **Admin Access**: Route-level guards with `@login_required` and admin checks
5. **CSRF**: Consider adding Flask-WTF for CSRF protection

---

## Future Enhancements

- Email notifications for schedule changes
- Mobile app (React Native or Flutter)
- Calendar integration (Google Calendar, iCal)
- Stronger password hashing (bcrypt/PBKDF2)
- Two-factor authentication
- Export to CSV/Excel
- Recurring schedule templates
- Push notifications
