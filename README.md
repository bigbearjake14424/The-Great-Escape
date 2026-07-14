# The Great Escape

**Current version: 1.5.0**

The Great Escape is a cross-platform desktop backup utility built with Python, Tkinter, and TTK. It creates one compressed `.tar.xz` archive and distributes the finished archive to enabled local folders and rclone remotes.

## Features

- Select individual files and folders.
- Generate MySQL, MariaDB, and SQLite SQL dumps before archive creation.
- Configure multiple database profiles and enable or disable them independently.
- Create `.tar.xz` archives with multi-threaded xz compression.
- Use four compression threads on Raspberry Pi 5.
- Copy completed archives to multiple local destinations.
- Upload archives to multiple rclone remotes.
- Verify archives before distribution.
- Keep only the newest five matching backup archives in each destination.
- Customize TTK themes, fonts, font sizes, and GUI colors.
- Maximize the application on Windows, macOS, Linux, and Raspberry Pi OS.
- Store backup, database, and appearance preferences in JSON.

## Menu layout

The main menu is ordered as:

```text
File | Tools | Appearance | Databases | Help
```

The **Sources** tab also includes a database-backup note and a button that opens the database profile manager.

## Database dumps

Open **Databases → Manage Database Dumps…**.

### MySQL and MariaDB

Profiles support:

- Host and port
- Username
- One database or all databases
- Automatic detection of `mariadb-dump` or `mysqldump`
- A specific executable or full executable path
- A protected MySQL/MariaDB defaults file
- Optional extra command-line arguments

The application uses options for consistent and complete dumps, including routines, events, triggers, transactions, and binary data.

Passwords are not stored in the JSON settings file. Store credentials in a protected client option file, for example:

```ini
[client]
password=your_database_password
```

On Linux:

```bash
chmod 600 ~/.my.cnf
```

### SQLite

SQLite support uses Python's built-in `sqlite3` module and does not require an external dump executable.

Select a `.db`, `.sqlite`, or `.sqlite3` file in the profile. Before compression, the application:

1. Opens the source database read-only.
2. Creates a consistent temporary snapshot with SQLite's backup API.
3. Exports the snapshot as a portable SQL dump.
4. Adds the SQL file under `database_dumps` in the tarball.
5. Removes the temporary snapshot and uncompressed dump after archive creation.

## Appearance settings

Open **Appearance → Customize…** to change the TTK theme, font family, widget font sizes, background colors, surface colors, and accent colors.

Settings are saved to:

```text
~/.config/the-great-escape/settings.json
```

## Destination retention

After a successful transfer, each destination keeps the newest five archives matching:

```text
prefix_YYYYMMDD_HHMMSS.tar.xz
```

Unrelated files, folders, partial files, and archives with a different prefix are not deleted.

## Requirements

The Python application supports Python 3.10 or newer on Raspberry Pi OS, Linux, Windows 10/11, and macOS.

The archive engine requires `tar` and `xz` in `PATH`. `rclone` is optional. MySQL/MariaDB clients are required only for those dump profiles. SQLite support is included with Python.

### Raspberry Pi OS, Debian, and Ubuntu

```bash
sudo apt update
sudo apt install python3 python3-tk tar xz-utils rclone mariadb-client
```

## Run

```bash
python3 main.py
```

On Windows:

```powershell
py main.py
```

## Project layout

```text
main.py
great_escape/
├── app.py
├── appearance.py
├── backup.py
├── config.py
├── databases.py
├── messaging.py
├── models.py
├── platform_utils.py
├── processes.py
├── retention.py
├── settings.py
├── tools.py
└── ui.py
```

## Configuration

Settings: `~/.config/the-great-escape/settings.json`  
Logs: `~/.config/the-great-escape/logs/`  
Default archive directory: `~/Backups/The-Great-Escape/`

## License

MIT License. See `LICENSE`.
