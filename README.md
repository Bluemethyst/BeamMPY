# BeamMPY

A self-hosted Flask and Vue panel for multiple local BeamMP servers. The first
release provides administrator login, server installation/import, power controls,
live consoles, configuration editing, map selection and mod management. Version
0.3 adds member accounts, per-server permissions, account recovery and deployment
scripts. See [the roadmap](docs/ROADMAP.md) and
[current verification status](docs/HANDOFF.md).
The instance-scoped HTTP and console interfaces are documented in [API.md](docs/API.md).

Version 0.4 adds a Statistics tab to each server: process CPU, resident memory,
uptime and optional aggregate player activity, with 30 days of history. These are
the selected server's measurements, not system-wide usage. See
[statistics](docs/STATISTICS.md) for collection, permissions and player setup.

## Quick start

Install Python 3.11 or newer first. Ubuntu Server also needs `python3-venv`,
`curl`, `ca-certificates`, systemd and sudo/root access (Ubuntu 24.04 LTS supplies
a suitable Python). Windows 11 needs the Python launcher (`py -3`) or `python`
on PATH. No Git or Node.js is needed. These interactive installers download the
public source archive with its compiled UI and create a private Python environment.

**Publication pending:** push the installer changes in this checkout to `main`
before sharing these commands. No GitHub Release assets are required. See
[download status and publication checklist](docs/INSTALLATION.md#public-downloads-and-publication).

**Ubuntu Server (POSIX sh, in an interactive terminal)**

```sh
(f=$(mktemp) && trap 'rm -f "$f"' 0 && curl -fsSL https://raw.githubusercontent.com/Bluemethyst/BeamMPY/main/scripts/install.sh -o "$f" && sh "$f")
```

Choose the installation/data paths, unprivileged service account, access mode
and port. Defaults: `/opt/beammpy/app`, `/var/lib/beammpy`, account `beammpy`,
local access, port 8524. The installer starts the systemd service and enables it
at boot. For a headless machine, choose **lan** to connect from another device;
the installer prints its LAN addresses. Local mode prints SSH tunnel instructions.

**Windows 11 (Windows PowerShell)**

```powershell
& { $f = Join-Path $env:TEMP ('beammpy-' + [guid]::NewGuid() + '.ps1'); try { Invoke-WebRequest -UseBasicParsing https://raw.githubusercontent.com/Bluemethyst/BeamMPY/main/scripts/install.ps1 -OutFile $f; powershell.exe -NoProfile -ExecutionPolicy Bypass -File $f } finally { Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue } }
```

Choose a root directory (default `%LOCALAPPDATA%\BeamMPY`; spaces supported).
Program/environment files go under `app\`, panel data under `data\`.
Double-click **Start BeamMPY.bat** in that root to start the panel in the
foreground; press `Ctrl+C` to stop. Windows installs no service or automatic startup.
The command uses an execution-policy override only for its installer process.

Open the printed URL (normally [http://127.0.0.1:8524](http://127.0.0.1:8524))
and create the first administrator with an eight-character-or-longer password.
Initial setup closes when an account exists. Reruns reuse the recorded data;
stop/backup first. See [installation, service commands, uninstall, updates and
account recovery](docs/INSTALLATION.md). Real Linux BeamMP execution and full
authenticated player joins remain unverified.

## Data and upgrades

For manual CLI launches, the data directory defaults to the current directory
(or `BEAMMPY_DATA_DIR`). The installers record the explicit data paths described
above. Data contains `users.db`, `panel.secret`, `.panel.lock`, and `instances/`. An existing
`server/` folder is registered in place on first startup. Existing account hashes
and configuration/resources are preserved. Imported directories remain where they
are. Never put runtime data inside the installed Python package.

Before upgrades, stop the panel, copy the entire data directory and any imported
server directories to a safe location, then install the new wheel. Database
migrations run on startup. Restore the saved data and old package together to
roll back. Do not copy an active SQLite database as a backup.

Version 0.3 upgrades the database to schema 3 without changing existing user IDs,
password hashes or server records. The oldest existing account becomes the sole
administrator; any other historical accounts need explicit server assignments.

Version 0.4 migrates to schema 4, adding statistics history and optional plugin
registrations while preserving existing users, hashes, grants and server files.
Older panel versions cannot open the upgraded database; keep the complete
pre-upgrade backup when planning a rollback.

Version 0.4.1 adds ten-second chart detail and defaults Statistics to Last hour.
Schema 5 keeps existing minute history and plugin registrations while adding the
finer observations. Detailed points start collecting after the updated panel starts.

Restart the panel after updating the source;
refreshing the browser alone does not load the new backend routes.

```text
beammpy reset-password --data-dir /path/to/data --username admin
```

Stop the panel before resetting a password. Reset prompts locally and revokes sessions. Initial setup is available
only while the database has no accounts. The panel never rewrites `.env`.

Use `beammpy list-users --data-dir /path/to/data` to recover a forgotten username,
or `beammpy create-admin --data-dir /path/to/data --username admin` for first setup
without a browser. Local account commands require a stopped panel. **My account**
changes your password or signs out all devices. **Users**, available to the
administrator, creates/disables/deletes members, sets passwords and assigns
per-server power, map, mod upload/toggle, configuration and console permissions.
Server creation is a separate optional grant. New servers are assigned to their
creator. New/reset members must choose their own password when **Temporary
password** is checked (the default); uncheck it for a password they can use
directly. New passwords require a minimum of eight characters. Deleting a member
removes its sessions and grants while preserving its servers and files. The
administrator cannot be deleted.
Access changes revoke sessions. Imports, deletion, executable reinstallation and
user administration stay administrator-only. Console commands can stop a server
and should be granted with care. There is no public registration or email reset.

## Maps, mods, imports and deletion

- Creating a server requires an AuthKey from [BeamMP Keymaster](https://keymaster.beammp.com).
  The panel also refuses to start an imported or existing server without a key.
  Keys remain masked in API responses and configuration forms.
- Open **Maps** to choose a named stock map or a custom map discovered inside a
  mod ZIP. Map selection lives in this tab. Stop the instance before
  changing its map; the selection takes effect on the next start.
- Open **Mods** to upload ZIPs or enable/disable them. Disabling moves a ZIP out
  of the configured ResourceFolder's Client directory into `.beammpy-disabled`.
  Files are retained, existing uploads are never overwritten, and the current
  map's providing mod cannot be disabled until a different map is selected.
  ZIPs containing server configuration or panel data are rejected as client mods.
- **Import server** accepts a browser-uploaded ZIP, a host-local ZIP path, or an
  existing host-local folder. A ZIP must contain one ServerConfig.toml beside a
  compatible executable, optionally inside a wrapping folder. ZIP imports create
  a new instance; the original ZIP is untouched. Safe relative ResourceFolder
  paths are preserved; old absolute/external paths are reset to local Resources.
  Folder imports remain in place. Archived files are not executed by importing.
- **Delete server** is red and appears at the bottom of configuration. The server
  must be stopped, and its name must be typed exactly. Files remain unless the
  additional permanent-deletion checkbox is selected. Permanent deletion removes
  only the verified instance directory, never external resource locations, and
  refuses directories overlapping panel data or another instance's files/resources.
  Removed legacy instances stay removed across restarts; manual re-import is allowed.

Uploads default to 2 GiB per ZIP; set `BEAMMPY_UPLOAD_LIMIT` to a byte count before
starting the panel to change that limit. ZIPs are limited to 20,000 entries and
8 GiB of expanded data. Traversal paths, links, encrypted entries and duplicates
are rejected. Configure your reverse proxy's body-size limit and upload timeout
accordingly (large imports may need several minutes).

## Deployment

`beammpy serve --host 0.0.0.0 --port 8524 --data-dir /path/to/data` enables LAN
access. Run as a dedicated unprivileged user with read/write access to instance
directories and execute permission for the BeamMP binaries. A single Waitress
process serves Flask and Socket.IO polling; do not start multiple WSGI workers or
enable a development reloader against the same data directory.

The panel defaults to `127.0.0.1:8524`. Add `--port 8525` to the launch command
if that port is in use. When switching from `8080`, update any reverse proxy
upstream to match or keep the old port with `--port 8080`.

For internet access, place an HTTPS reverse proxy in front of the localhost
listener. Forward `/`, `/api/`, and `/socket.io/` to the same backend, preserve
Host, disable buffering for `/socket.io/`, and allow at least a 60-second proxy
timeout. Set `BEAMMPY_PUBLIC_ORIGIN=https://panel.example.com` and
`BEAMMPY_SECURE_COOKIES=1`. Only configure trusted proxy headers when your backend
cannot be reached directly. There is no public registration after first setup.

Planned shutdown sends `exit` to each owned server, then escalates after a timeout.
Servers are not automatically restarted when the panel starts. Crash leftovers
are reconciled using recorded process identity; unrelated processes are not killed.

## Troubleshooting

- A lock error means another panel uses that data directory. Stop it first; do
  not delete a lock file while another process is running.
- Installation requires outbound HTTPS to GitHub. Only matching official stable
  Windows/Linux assets are installed; unsupported distributions can import a
  compatible installation. Linux builds may require system libraries.
- Windows BeamMP binaries also need the Microsoft Visual C++ runtime; install the
  prerequisite linked in the [official server setup guide](https://docs.beammp.com/server/create-a-server/)
  if the executable cannot start on a fresh machine.
- BeamMP servers need an AuthKey from https://keymaster.beammp.com and
  appropriate TCP/UDP forwarding. The panel does not open firewalls or obtain keys.
- Configuration edits require a stopped instance. Keep each instance's port
  unique. Configuration secrets are never included in ordinary API responses.
- If joining reports `bad address cast` or `Socket Closed Code 3`, stop the
  instance, set **Configuration → Bind IP** to `::`, save and start it again.
  BeamMP 3.9.x casts incoming addresses to IPv6; an IPv4-only bind such as
  `0.0.0.0` can start successfully but reject every join. Version 0.2.2 uses
  BeamMP's dual-stack `::` default and repairs the old `0.0.0.0` wildcard on the
  next instance start, preserving TOML comments, AuthKeys and other settings.
  This repair enables both IPv4 and IPv6 listeners. It does not change specific
  interface addresses. Use `::1` for local-only IPv6, or `::ffff:127.0.0.1` for
  local-only IPv4. Restart the panel after upgrading to load this fix.
- A missing UI message means the source checkout needs `npm --prefix frontend ci`
  followed by `npm --prefix frontend run build`.

## Development and verification

Building the frontend from source requires Node 22.12+. From the checkout, set
up the development environment in PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[test]"
npm --prefix frontend ci
npm --prefix frontend run build
```

On Linux use `python3` to create the virtual environment and `.venv/bin/python`
to install the project.

The interface uses locally bundled [M3E](https://m3e.kyralabs.dev/) components,
icons and fonts throughout. Fields, navigation, tabs, menus, dialogs, switches,
cards, progress indicators and snackbars share its generated blue light/dark
theme. The palette icon beside logout opens appearance settings: light/dark/system,
six preset colours or a custom colour, palette styles and reset. M3E generates
the complete palette immediately; your choice is saved in this browser. No CDN
is required.
See [UI conventions](docs/UI.md) before adding screens or controls.

Run `python -m pytest`, `npm --prefix frontend run check`, and
`npm --prefix frontend run build`. For browser tests install Playwright Chromium
with `npm --prefix frontend exec -- playwright install chromium`, then run
`npm --prefix frontend run test:e2e`. Tests use temporary data and fixture processes.

For frontend hot reload run `beammpy serve` and, in another terminal,
`npm --prefix frontend run dev`. Vite proxies API and Socket.IO calls to Flask.
Build wheels with `python -m build` after building the UI. Do not include runtime
data in wheels. See `docs/HANDOFF.md` for outstanding real BeamMP/platform checks.

BeamMPY is available under the [MIT License](LICENSE). See
[third-party notices](THIRD_PARTY_NOTICES.md) for bundled dependencies.
