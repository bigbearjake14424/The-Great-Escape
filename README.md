# The Great Escape

**Current version: 1.4.0**

The Great Escape is a cross-platform desktop backup utility built with Python, Tkinter, and TTK. It creates one compressed `.tar.xz` archive and distributes the finished archive to enabled local folders and rclone remotes.

## Features

- Select individual files and folders.
- Enable or disable configured sources and destinations.
- Create `.tar.xz` archives with multi-threaded xz compression.
- Use four compression threads on Raspberry Pi 5.
- Create MySQL and MariaDB SQL dumps before building the archive.
- Back up one database or all databases from multiple configured servers.
- Include routines, events, triggers, and binary data in database dumps.
- Copy completed archives to multiple local destinations.
- Upload archives to multiple rclone remotes.
- Verify archives before distribution.
- Use `.partial` local files until copying completes.
- Keep only the newest five matching backup archives in each destination.
- Prune old archives from both local folders and rclone remotes after a successful transfer.
- Customize the TTK theme, fonts, font sizes, window colors, list colors, and accent color.
- Store backup and appearance preferences in one JSON settings file.
- Maximize the application for the available screen on Windows, macOS, Linux, and Raspberry Pi OS.
- Cancel an active backup using platform-appropriate process handling.

## MySQL and MariaDB dumps

Open **Databases → Manage MySQL / MariaDB Dumps…** to add database dump profiles.

Each profile supports:

- Profile name
- Host and port
- Database user
- One named database or all databases
- Automatic detection of `mariadb-dump` or `mysqldump`
- A specific executable name or full executable path
- A MySQL/MariaDB client defaults file
- Optional extra command-line arguments
- Enable or disable without removing the profile

Database dumps are created immediately before archive compression. The generated `.sql` files are placed inside a `database_dumps` folder in the tarball. Temporary uncompressed SQL files are removed automatically after archive creation.

### Password security

The application does **not** store database passwords in its JSON settings file. Store credentials in a MySQL/MariaDB client option file and select it in the profile's **Defaults file** field.

Example option file:

```ini
[client]
password=your_database_password
```

On Linux, protect the file:

```bash
chmod 600 ~/.my.cnf
```

The dump profile stores only the path to that file. Do not commit credential files to GitHub.

### Database client requirement

Install a compatible client utility on the computer running The Great Escape:

```bash
sudo apt install mariadb-client
```

Depending on the installation, the dump command may be named `mariadb-dump` or `mysqldump`. The **auto** setting checks for both.

## Appearance settings

Open **Appearance → Customize…** to change:

- Available TTK theme
- Font family
- Base font size
- Heading font size
- Treeview font size
- Button font size
- Window background
- Text color
- Entry and list background
- Accent and selection color
- Selected-text color

Use **Apply** to preview changes or **Save** to write them to:

```text
~/.config/the-great-escape/settings.json
```

Use **Appearance → Reset to Defaults** to restore the original appearance.

## Destination retention

After a backup is copied or uploaded successfully, The Great Escape checks that destination and keeps the newest five archives created with the same filename prefix.

Only generated archive names matching this format are eligible for cleanup:

```text
prefix_YYYYMMDD_HHMMSS.tar.xz
```

Unrelated files, folders, partial files, and archives with a different prefix are not deleted.

## Supported platforms

The Python application supports:

- Raspberry Pi OS and other Linux distributions
- Windows 10 and Windows 11
- macOS
- Python 3.10 and newer, including CPython virtual environments

The backup engine requires `tar` and `xz` to be installed and available in `PATH`. `rclone` is optional unless cloud destinations are enabled. `mariadb-dump` or `mysqldump` is required only when database dump profiles are enabled.

### Raspberry Pi OS, Debian, and Ubuntu

```bash
sudo apt update
sudo apt install python3 python3-tk tar xz-utils rclone mariadb-client
```

### Windows

Install Python with Tkinter, plus versions of GNU tar and xz that are available in `PATH`. Install rclone separately when cloud destinations are needed. Install MySQL Shell, MySQL Client, or MariaDB Client when database dumps are needed, and ensure the dump executable is available in `PATH` or select its full path in the profile.

### macOS

Python must include Tkinter. Install xz, rclone, and a MySQL or MariaDB client with your preferred package manager. macOS includes `tar`, although GNU tar may provide the most consistent behavior.

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
