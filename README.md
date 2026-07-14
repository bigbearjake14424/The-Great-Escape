# The Great Escape

**Current version: 1.6.0**

The Great Escape (from dataloss...) is a cross-platform desktop backup utility built with Python, Tkinter, and TTK. It creates one compressed `.tar.xz` archive and distributes the finished archive to enabled local folders and rclone remotes.

## Features

- Select individual files and folders.
- Drag files and folders onto the Sources list when `tkinterdnd2` is installed.
- Drag folders onto the Local destinations list.
- Generate MySQL, MariaDB, and SQLite SQL dumps before archive creation.
- Configure multiple database profiles and enable or disable them independently.
- Create `.tar.xz` archives with multi-threaded xz compression.
- Use four compression threads on Raspberry Pi 5.
- Copy completed archives to multiple local destinations.
- Upload archives to multiple rclone remotes.
- Verify archives before distribution.
- Keep only the newest five matching backup archives in each destination.
- Customize TTK themes, fonts, font sizes, and GUI colors.
- Run in the background with an optional system tray icon.
- Start hidden in the system tray when requested.
- Run backups automatically on a daily or weekly schedule.
- Maximize the application on Windows, macOS, Linux, and Raspberry Pi OS.
- Load and apply backup, database, appearance, automation, and window settings at startup.
- Store settings in JSON.

## Menu layout

The main menu is ordered as:

```text
File | Tools | Appearance | Databases | Automation | Help
```

The **Sources** tab includes a database-backup note, a database profile button, and drag-and-drop guidance.

## Background mode and scheduling

Open **Automation → Schedule and Background…**.

Available settings include:

- Enable the system tray icon.
- Start the application hidden in the tray.
- Hide to the tray when the main window is closed.
- Enable automatic backups.
- Choose a daily or weekly schedule.
- Choose the weekday for weekly backups.
- Set the backup time using 24-hour `HH:MM` format.

The built-in scheduler runs while The Great Escape is running. For reliable scheduled backups, leave the application open or enable the tray icon and close-to-tray behavior.

The tray menu provides:

- Show The Great Escape
- Start Backup
- Exit

Tray support requires `pystray` and `Pillow`:

```bash
python -m pip install pystray Pillow
```

Or install all optional GUI integrations:

```bash
python -m pip install -r requirements-optional.txt
```

## Drag-and-drop

Cross-platform drag-and-drop is enabled when `tkinterdnd2` is installed:

```bash
python -m pip install tkinterdnd2
```

You can then:

- Drop files or folders onto the Sources list.
- Drop folders onto the Local destinations list.

rclone destinations still require normal rclone configuration because a remote path is not a local filesystem folder.

The app continues to work normally when `tkinterdnd2` is not installed; only drag-and-drop is disabled.

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

All saved settings are loaded and applied each time the program starts.

## Destination retention

After a successful transfer, each destination keeps the newest five archives matching:

```text
prefix_YYYYMMDD_HHMMSS.tar.xz
```

Unrelated files, folders, partial files, and archives with a different prefix are not deleted.

## Requirements

The Python application supports Python 3.10 or newer on Raspberry Pi OS, Linux, Windows 10/11, and macOS.

The archive engine requires `tar` and `xz` in `PATH`. `rclone` is optional. MySQL/MariaDB clients are required only for those dump profiles. SQLite support is included with Python.

Optional GUI packages:

- `pystray` and `Pillow` for system tray support
- `tkinterdnd2` for drag-and-drop

### Raspberry Pi OS, Debian, and Ubuntu

```bash
sudo apt update
sudo apt install python3 python3-tk tar xz-utils rclone mariadb-client
python3 -m pip install -r requirements-optional.txt
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
requirements-optional.txt
great_escape/
├── app.py
├── appearance.py
├── automation.py
├── backup.py
├── config.py
├── databases.py
├── dragdrop.py
├── messaging.py
├── models.py
├── platform_utils.py
├── processes.py
├── retention.py
├── settings.py
├── tools.py
├── ui.py
└── windowing.py
```

## Configuration

Settings: `~/.config/the-great-escape/settings.json`  
Logs: `~/.config/the-great-escape/logs/`  
Default archive directory: `~/Backups/The-Great-Escape/`

## License

MIT License. See `LICENSE`.
