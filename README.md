# BeamMPY

Manage your local BeamMP servers from a browser. Create or import servers, use
live consoles, change maps and mods, view statistics, and give members access.

Current version: **0.4.1**.

## Install

Requires **Python 3.11+**. No Node.js or Git needed.

### Windows 11

Run in PowerShell with `py` or `python` available:

```powershell
iwr -useb https://raw.githubusercontent.com/Bluemethyst/BeamMPY/main/scripts/install.ps1 | iex
```

Choose an installation folder, then double-click **Start BeamMPY.bat** inside it.
Press **Ctrl+C** in the panel window to stop. It runs only when you start it.

### Ubuntu Server

Requires `python3-venv`, `curl`, `ca-certificates`, systemd and sudo/root access.
Run in an interactive terminal or SSH session:

```sh
curl -fsSL https://raw.githubusercontent.com/Bluemethyst/BeamMPY/main/scripts/install.sh | sh
```

The installer starts BeamMPY as a service and enables it at boot.
Choose **lan** during setup to connect from another device; open the URL it prints.

## First setup

1. Open the printed address, normally **http://127.0.0.1:8524** on the same computer.
2. Create your administrator account with a password of at least eight characters.
3. Get an [AuthKey from BeamMP](https://keymaster.beammp.com), then create or import a server.

## Everyday use

| Action | Windows | Ubuntu |
| --- | --- | --- |
| Start | Double-click **Start BeamMPY.bat** | `sudo systemctl start beammpy` |
| Stop | **Ctrl+C** in the panel window | `sudo systemctl stop beammpy` |
| Data | `data\` inside your chosen folder | `/var/lib/beammpy` by default |

## Update

An **Update available** icon beside the panel version opens manual instructions
when a newer version is found. Checks are cached and optional for offline use.

Stop BeamMPY and back up your data and any imported server folders. Run the
installer again and choose the **same installation folder**:

**Windows (PowerShell)**

```powershell
iwr -useb https://raw.githubusercontent.com/Bluemethyst/BeamMPY/main/scripts/install.ps1 | iex
```

**Ubuntu**

```sh
curl -fsSL https://raw.githubusercontent.com/Bluemethyst/BeamMPY/main/scripts/install.sh | sh
```

Existing accounts and server files are retained. Ubuntu restarts its service;
on Windows, open **Start BeamMPY.bat** again.

## Uninstall

**Ubuntu** (replace `/opt/beammpy` if you chose another installation folder):

```sh
sudo sh /opt/beammpy/uninstall.sh
```

This stops and removes the service and program, keeping your accounts and data.
To delete installer-managed data too, use `--purge-data` and confirm its full path.

**Windows:** stop the panel with **Ctrl+C**, copy `data\` and any imported server
folders you want to keep, then delete your installation folder (default:
`%LOCALAPPDATA%\BeamMPY`). There is no Windows service to remove.

## Guides

- [Installation](docs/INSTALLATION.md): prerequisites, LAN access, logs, updates, uninstall and password recovery.
- [Using the panel](docs/USAGE.md): servers, maps, mods, imports and troubleshooting.
- [Accounts and permissions](docs/ACCOUNTS_DEPLOYMENT.md) · [Statistics](docs/STATISTICS.md)
- [Development](docs/DEVELOPMENT.md) · [API](docs/API.md) · [Roadmap](docs/ROADMAP.md)
- [Verification status](docs/HANDOFF.md): Ubuntu service and real Linux BeamMP checks remain pending.

[MIT License](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md)
