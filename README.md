# BeamMPY

Manage your local BeamMP servers from a browser. Create or import servers, use
live consoles, change maps and mods, view statistics, and give members access.

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

Keep a backup of your data before updating. Ubuntu uninstall keeps data by default;
on Windows, save `data\` before deleting the installation folder.

## Guides

- [Installation](docs/INSTALLATION.md): prerequisites, LAN access, logs, updates, uninstall and password recovery.
- [Using the panel](docs/USAGE.md): servers, maps, mods, imports and troubleshooting.
- [Accounts and permissions](docs/ACCOUNTS_DEPLOYMENT.md) · [Statistics](docs/STATISTICS.md)
- [Development](docs/DEVELOPMENT.md) · [API](docs/API.md) · [Roadmap](docs/ROADMAP.md)
- [Verification status](docs/HANDOFF.md): Ubuntu service and real Linux BeamMP checks remain pending.

[MIT License](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md)
