# The Great Escape

**Current version: 1.2.0**

The Great Escape is a Linux desktop backup utility built with Python, Tkinter, and TTK. It creates one compressed `.tar.xz` archive and distributes the finished archive to enabled local folders and rclone remotes.

## Why the project is modular

The source is split into focused modules so individual features can be reviewed, tested, and committed independently. This also makes direct GitHub updates from connected development tools more reliable than maintaining one very large script.

## Features

- Select individual files and folders.
- Enable or disable configured sources and destinations.
- Create `.tar.xz` archives with multi-threaded xz compression.
- Use four compression threads on Raspberry Pi 5.
- Copy completed archives to multiple local destinations.
- Upload archives to multiple rclone remotes.
- Verify archives before distribution.
- Use `.partial` local files until copying completes.
- Keep only the newest five matching backup archives in each destination.
- Prune old archives from both local folders and rclone remotes after a successful transfer.
- Cancel an active backup.
- Save settings and timestamped logs under the user home directory.

## Destination retention

After a backup is copied or uploaded successfully, The Great Escape checks that destination and keeps the newest five archives created with the same filename prefix.

Only generated archive names matching this format are eligible for cleanup:

```text
prefix_YYYYMMDD_HHMMSS.tar.xz
```

Unrelated files, folders, partial files, and archives with a different prefix are not deleted. Retention cleanup failures are written to the activity log as warnings and do not remove the newly completed backup.

## Requirements

```bash
sudo apt update
sudo apt install python3 python3-tk tar xz-utils rclone
```

`rclone` is optional unless cloud destinations are enabled.

## Run

```bash
python3 main.py
```

## Project layout

```text
main.py
great_escape/
├── app.py
├── backup.py
├── config.py
├── messaging.py
├── models.py
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
