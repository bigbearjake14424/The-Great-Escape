# The Great Escape

## A Note from the Developer

Yes, I know this project is over-engineered. I used this project to help me learn to code in Python. I had a stroke in 2014 that makes learning new things tougher. The use of AI to help me learn makes it easier.

I set up ChatGPT to help explain starting points, answer beginner questions, review ideas, and help me understand why the code works. Please use the software and give me feedback. I will always welcome collaboration.

If you are an experienced developer and notice something that could be improved, please do not assume I already know the “right” way to do it. Tell me why your approach is better. One of the main goals of this project is to learn and become a better programmer.

Thank you for taking a look at **The Great Escape**!

**Current version: 1.6.0**

The Great Escape (from data loss...) is a cross-platform desktop backup utility built with Python, Tkinter, and TTK. It creates one compressed `.tar.xz` archive and distributes the finished archive to enabled local folders and rclone remotes.

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

## AI Assistance and Disclosure

This project was developed with substantial assistance from OpenAI's ChatGPT as a learning, design, debugging, and documentation aid.

ChatGPT was used to help:

- Explain Python concepts and provide starting points.
- Answer beginner questions without judgment.
- Explore application architecture and feature design.
- Learn Tkinter and TTK development.
- Improve cross-platform compatibility.
- Refactor the application into smaller, maintainable modules.
- Review, troubleshoot, and revise code.
- Draft and improve project documentation.

Development sessions for this project have used OpenAI GPT-5-series reasoning models, including **GPT-5.4 Thinking**, **GPT-5.5 Thinking**, and **GPT-5.6 Thinking**. Model availability and names may change as OpenAI updates its services.

AI-generated suggestions can contain mistakes. The project maintainer remains responsible for selecting features, reviewing changes, testing the application, accepting contributions, and deciding what is included in a release.

### Official AI Links

- [Try ChatGPT](https://chatgpt.com/)
- [Learn more about OpenAI](https://openai.com/)

## Built With

- [Python](https://www.python.org/)
- Tkinter and TTK
- SQLite
- MySQL and MariaDB client tools
- GNU tar and xz
- [rclone](https://rclone.org/)
- [OpenAI ChatGPT](https://chatgpt.com/)

## Contributing and Feedback

Please use the software and share feedback, bug reports, suggestions, and improvements. Collaboration is always welcome.

When proposing a change, explanations are especially valuable. Describing why a different design or coding approach is better helps make this repository a more useful learning project.

Contributions are accepted under the same **GNU General Public License version 3 only** terms that apply to the project. Contributors should preserve applicable copyright, license, and attribution notices and clearly identify modified files where required.

## License

Copyright © 2026 Jacob Stallings.

The Great Escape is free software licensed under the **GNU General Public License, version 3 only (`GPL-3.0-only`)**. You may use, study, modify, and redistribute it under those terms. Distributed modified versions must remain under GPLv3 and must make the corresponding source available as required by the license.

See [`LICENSE`](LICENSE) for the license terms and [`NOTICE`](NOTICE) for project attribution information.
