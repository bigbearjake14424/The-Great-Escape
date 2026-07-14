# The Great Escape

**Current version: 1.1.0**

**The Great Escape** is a Linux desktop backup utility built with Python, Tkinter, and TTK. It creates one compressed `.tar.xz` archive and then distributes the completed archive to enabled local folders and rclone remotes.

The application is designed for Linux systems, including Raspberry Pi OS, and is especially well suited to a Raspberry Pi 5.

## Features

- Select individual files and complete folders.
- Enable or disable sources without removing them.
- Create one `.tar.xz` archive using GNU `tar` and multi-threaded `xz`.
- Choose maximum, high, or balanced compression.
- Configure the number of compression threads.
- Use four compression threads on a Raspberry Pi 5.
- Copy the completed archive to multiple local destinations.
- Upload the completed archive to multiple rclone remotes.
- Configure separate folders for each rclone destination.
- Verify archive integrity before distribution.
- Verify local copies by file size.
- Use temporary `.partial` files so incomplete copies do not appear finished.
- Cancel an active backup.
- Save application settings automatically.
- Keep timestamped activity logs.
- Check whether `tar`, `xz`, and `rclone` are installed.
- Open `rclone config` from the application.
- List configured rclone remotes.

## Requirements

- Linux or Raspberry Pi OS
- Python 3.10 or newer
- Tkinter
- GNU tar
- xz-utils
- rclone, only when cloud destinations are used

Install the required packages on Raspberry Pi OS, Debian, or Ubuntu:

```bash
sudo apt update
sudo apt install python3 python3-tk tar xz-utils rclone
```

`rclone` is optional when you only use local backup destinations.

## Download or clone

```bash
git clone https://github.com/bigbearjake14424/The-Great-Escape.git
cd The-Great-Escape
git switch main
```

## Run the application

```bash
python3 main.py
```

To run it directly:

```bash
chmod +x main.py
./main.py
```

## First use

1. Open **Sources**.
2. Add the files and folders you want to include.
3. Open **Destinations**.
4. Add one or more local destination folders and/or rclone destinations.
5. Review **Archive Options**.
6. Select **Start Backup**.

The application creates the compressed archive first. It only begins copying or uploading after archive creation completes successfully.

## Default folders

The default working archive directory is:

```text
~/Backups/The-Great-Escape
```

Settings are stored in:

```text
~/.config/the-great-escape/settings.json
```

Logs are stored in:

```text
~/.config/the-great-escape/logs/
```

Personal source and destination paths are not included in the repository. Each user configures their own paths through the GUI.

## Compression settings

- **Maximum:** `xz -9e`
- **High:** `xz -9`
- **Balanced:** `xz -6`

On a Raspberry Pi 5, four compression threads can be selected to use all four CPU cores:

```text
xz -9e -T4
```

Maximum compression can use substantial CPU time and memory. Balanced compression is generally faster when archive size is less important.

## Configure rclone

Run:

```bash
rclone config
```

You can also open the rclone configuration utility from **Tools → Open rclone Config** inside the application.

After creating a remote, add its name in the application's **Destinations** tab. For example:

```text
gdrive:Backups
```

The application supports multiple configured rclone destinations in the same backup job.

## Safety and reliability

- Test both backup creation and restoration before relying on any backup system.
- The application copies archives; it does not delete files from destination services.
- Local copies are written to temporary `.partial` files and renamed only after completion.
- Completed local copies are checked against the original archive size.
- Optional archive verification uses `tar -tJf` before distribution.
- Do not place the working archive directory inside a selected source folder.
- Keep at least one backup destination physically separate from the source computer.

## Project file

The application entry point is `main.py`.

```python
APP_VERSION = "1.1.0"
```

## Contributing

Bug reports, feature requests, and pull requests are welcome. Do not commit personal paths, credentials, rclone configuration files, generated archives, settings files, or logs.

## License

Released under the MIT License. See [LICENSE](LICENSE).
