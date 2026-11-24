# Installation, startup and uninstall

End users need Python 3.11+, outbound HTTPS to GitHub and the configured Python
package index, and disk space for the program and servers. Node.js and Git are
not needed: the public source archive includes the compiled interface. Python
build/dependency installation happens in private environments, without changing
the system Python packages. The installers never install/update BeamMP binaries.

## Ubuntu Server

Use Ubuntu with systemd (24.04 LTS supplies Python 3.12), an interactive SSH/local
terminal, and sudo/root access. Install prerequisites if missing:

```sh
sudo apt-get update
sudo apt-get install python3 python3-venv curl ca-certificates
```

Run this one-liner as your normal login account; sudo is requested as needed:

```sh
curl -fsSL https://raw.githubusercontent.com/Bluemethyst/BeamMPY/main/scripts/install.sh | sh
```

The shell reads the downloaded script from the pipe while interactive setup and
sudo read prompts from `/dev/tty`, so the download does not consume prompt input.
It is POSIX `sh`; Bash is not required. You can also download and inspect
`scripts/install.sh` before running it. Do not run unattended without a terminal.

Prompts cover the installation root (`/opt/beammpy`), data directory
(`/var/lib/beammpy`), local/LAN access, TCP port (8524) and service account
(`beammpy`). Program files and versioned private Python environments live under
`/opt/beammpy/app`; installer records and uninstall tools live in `/opt/beammpy`.
Keep data outside the installation root. Custom absolute paths, including spaces,
are supported; symlink paths and overlapping program/data paths are rejected.
An existing account can be reused if it has access to the data. New service
accounts have no login shell. The service runs unprivileged; program files are
root-owned and new data directories are private to the service account.

Installation starts `beammpy.service`, enables it at boot, and checks both
systemd state and the panel's HTTP API. It does not open firewall ports. The panel
starts with all managed BeamMP servers stopped.

### Headless and LAN access

The default **local** choice binds `127.0.0.1:8524`; only the server itself can
open that address. From another computer, use an SSH tunnel:

```sh
ssh -L 8524:127.0.0.1:8524 YOUR_USER@SERVER_IP
```

Then open `http://127.0.0.1:8524` on that computer. Choose **lan** during
installation to bind `0.0.0.0` instead. The installer prints local and detected
IPv4 interface URLs, for example `http://192.168.1.20:8524`. Use the address of
an interface reachable from your device; `0.0.0.0` is never a browser destination.
If needed, allow the panel TCP port from your trusted LAN in your firewall.
Create the first administrator promptly on a trusted network. For internet
access use the [HTTPS reverse proxy settings](USAGE.md#deployment).

### Service operations

```sh
sudo systemctl status beammpy --no-pager
sudo journalctl -u beammpy -f
sudo systemctl restart beammpy
sudo systemctl stop beammpy
sudo systemctl start beammpy
sudo systemctl is-enabled beammpy
```

Stop waits for the panel to stop its owned servers. Do not start a second panel
on the same data directory. Change bind/port by rerunning the installer with the
same root; it defaults to the saved values and retains the saved data directory.

### Repair a failed service installation

An earlier installer quoted `WorkingDirectory=` incorrectly, causing
`Unit beammpy.service has a bad unit file setting` after package installation.
For the default data path, repair the installed service without reinstalling:

```sh
sudo sed -i 's|^WorkingDirectory=.*|WorkingDirectory=/var/lib/beammpy|' /etc/systemd/system/beammpy.service
sudo systemctl daemon-reload
sudo systemctl restart beammpy
sudo systemctl status beammpy --no-pager
```

Substitute your data path if you changed it. Accounts and server files are
untouched. Once the corrected installer is published, rerunning it with the
same root also repairs this failed installation. New service files are checked
with `systemd-analyze verify` before being installed or enabled.

The older installer could also leave root-owned build files in its temporary
download folder, causing cleanup permission errors. Builds now use a separate
temporary copy and avoid writing Python caches into the download. An older
failed run's temporary folder may remain; this does not affect panel data.

### Uninstall

For the default root (substitute your chosen path):

```sh
sudo sh /opt/beammpy/uninstall.sh
```

This stops and disables the service, removes its unit and installed program
files/environments, and reloads systemd. It **keeps** the Linux service account,
panel accounts, configuration, local server data and imported server directories.
Reinstalling with the same data directory reuses that data; preserve its ownership.

To also remove installer-created data, explicitly request the separate option:

```sh
sudo sh /opt/beammpy/uninstall.sh --purge-data
```

You must type the exact full data path to confirm permanent deletion. Purge
requires the installer's matching data marker; pre-existing/adopted data cannot
be purged by this command. It removes everything under that data path, including
accounts and local instances. Imported directories outside it and the Linux
account remain. If already uninstalled, retained data must be removed manually
or after reinstalling; the uninstall program itself was removed.

## Windows 11

Install Python 3.11+ with the Python launcher (`py -3`) or `python` on PATH.
Run in Windows PowerShell as the user who will run the panel; administrator
rights are unnecessary for a user-writable installation root.

```powershell
iwr -useb https://raw.githubusercontent.com/Bluemethyst/BeamMPY/main/scripts/install.ps1 | iex
```

The installer runs in the current PowerShell window, with its own local settings;
it does not change machine/user execution policy. It downloads the source,
installs BeamMPY and writes the launcher. Python runs the installation steps
without opening its interactive shell. Alternatively download and inspect
`scripts/install.ps1` and run it according to your local policy.
`BEAMMPY_PYTHON` can select a specific Python executable.

Choose an installation root, such as `C:\Users\YOU\BeamMPY Panel` (default
`%LOCALAPPDATA%\BeamMPY`). The installer keeps these paths under it:

| Path under root | Contents |
| --- | --- |
| `Start BeamMPY.bat` | Double-clickable foreground launcher |
| `app\environments\` | Private Python environments and installed program/UI |
| `app\installation.json` | Active/previous environment and launch settings |
| `data\` | Accounts, panel configuration and managed server directories |
| `setup.json`, `setup.py` | Installer records/maintenance tools |

Choose local access (default) or LAN, and port 8524 unless another program uses
it. No Windows service, scheduled task, shortcut in Startup, or automatic launch
is installed. After installation, double-click **Start BeamMPY.bat**. It uses
its own directory and private environment, so it also works from another working
directory, for example in PowerShell:

```powershell
& 'C:\Users\YOU\BeamMPY Panel\Start BeamMPY.bat'
```

Open the printed URL, normally `http://127.0.0.1:8524`. For LAN mode, open
`http://SERVER_LAN_IP:8524` from another device and permit that TCP port from the
trusted LAN if Windows Firewall requires it. Press **Ctrl+C** in the panel's
console to stop the panel and its owned servers; answer the batch-termination
prompt if Windows displays it. Wait for shutdown before closing the window.

### Remove Windows installation

Stop the panel first. Keep or copy `data\` and any externally imported server
folders you want to retain. Remove `app\`, `Start BeamMPY.bat`, `setup.json`,
`setup.py` and installer `__pycache__` to leave `data\` in place;
or move `data\` somewhere safe and delete the entire installation root using
File Explorer. Deleting the root without saving data permanently removes those
accounts and local instances. There is no service/startup entry to remove.
To reuse retained data after removing program files, install into a new empty
root, then (with the panel stopped) replace its empty `data\` with the retained
folder. Keep your existing Python installation while using its private environments.

## First administrator and recovery

On first access, create the sole administrator with a password of at least eight
characters. Setup is available only while the database has no accounts. Existing
users, password hashes, grants, server files, TOML and `.env` are preserved on
reruns. The data directory holds `users.db`, `panel.secret`, `.panel.lock` and
`instances/`; imported folders remain at their original locations. Never delete
the lock while the panel runs.

For first setup without a browser or forgotten usernames/passwords, stop the
panel (Ubuntu: `sudo systemctl stop beammpy`) and run the installed launcher:

```sh
sudo -u beammpy sh /opt/beammpy/app/beammpy.sh list-users
sudo -u beammpy sh /opt/beammpy/app/beammpy.sh reset-password --username YOUR_NAME
# Only before any account exists:
sudo -u beammpy sh /opt/beammpy/app/beammpy.sh create-admin --username YOUR_NAME
sudo systemctl start beammpy
```

```powershell
& 'C:\Users\YOU\BeamMPY Panel\app\beammpy.ps1' list-users
& 'C:\Users\YOU\BeamMPY Panel\app\beammpy.ps1' reset-password --username YOUR_NAME
# Only before any account exists:
& 'C:\Users\YOU\BeamMPY Panel\app\beammpy.ps1' create-admin --username YOUR_NAME
```

Password prompts are hidden and revoke existing sessions on reset. Local
maintenance refuses an active panel. There is no email reset or public
registration. My account changes your own password; Users manages member
accounts and per-server permissions. See [ACCOUNTS_DEPLOYMENT.md](ACCOUNTS_DEPLOYMENT.md)
and [STATISTICS.md](STATISTICS.md) for account and statistics behavior.

## Reruns and updates

The **Update available** icon beside the navigation footer's version opens an
M3E dialog with the installed/available panel versions and a copyable command.
The command is selected by the panel host's OS, not your browser's OS; Windows
uses the PowerShell installer above and Ubuntu uses the shell installer above.
The dialog never executes it or restarts anything. Manual wheel installations
should use the explicit wheel update commands below instead of adopting a new root.

Checks contact only the fixed public [version manifest](https://raw.githubusercontent.com/Bluemethyst/BeamMPY/main/beammpy/version.json)
over HTTPS, after a signed-in user opens the panel. They run in the background,
with connection/read timeouts, a body deadline/size limit, no redirects and strict
JSON/SemVer validation. Results are shared across users in this panel process:
success is cached for six hours, failure for one hour. Browsers quietly refresh
the result every five minutes while visible; no check blocks startup, login or
server management. Offline or malformed responses hide the notice, with no popup
or error notification. The installed version comes from the panel's bundled
manifest, not a managed BeamMP server. Build metadata does not affect ordering.

Stop/backup first: copy the complete stopped data directory and external imported
server directories to your backup location. Rerun the one-liner and select the
**same installation root**. Managed installs retain their recorded data path,
reuse accounts/data, and activate a new private environment only after its
disposable validation passes. Old environments are retained. Ubuntu stops an
existing service during activation and starts it afterward; Windows refuses
updates while its panel runs. Initial source-build failures leave a running
Ubuntu service alone. An interrupted install can be rerun with the same root.

Do not downgrade after database migration without restoring the matching old
data backup too. The scripts do not back up data or update BeamMP binaries.
For an interrupted installer, verify no installer is running before removing
the root/app `.install.lock`. Unrecognized nonempty roots are refused.

### Explicit wheels / existing manual installations

The original wheel-based scripts remain supported, including offline dependency
wheels. They create no service and start in the foreground; program and data
must be separate directories. Use the wheel plus matching installers ZIP (or
the `scripts/` directory from source); keep the scripts together:

```powershell
.\install.ps1 --wheel 'C:\Downloads\beammpy-0.5.0-py3-none-any.whl' --install-dir 'C:\BeamMPY\app' --data-dir 'C:\BeamMPY\data'
& 'C:\BeamMPY\app\beammpy.ps1' start
# Stop and back up before updating:
.\update.ps1 --wheel 'C:\Downloads\beammpy-NEW_VERSION-py3-none-any.whl' --install-dir 'C:\BeamMPY\app'
```

```sh
sh ./install.sh --wheel /path/beammpy-0.5.0-py3-none-any.whl --install-dir "$HOME/BeamMPY/app" --data-dir "$HOME/BeamMPY/data"
sh "$HOME/BeamMPY/app/beammpy.sh" start
# Stop and back up before updating:
sh ./update.sh --wheel /path/beammpy-NEW_VERSION-py3-none-any.whl --install-dir "$HOME/BeamMPY/app"
```

Add `--wheelhouse /path/to/dependency-wheels` to install/update offline. To adopt
an existing manual installation, use these explicit commands with a **new empty
program directory** and the existing stopped data path. The interactive root
installer does not silently adopt an unrelated nonempty directory. No existing
manual installation or imported server is moved or removed.

## Public downloads and publication

Checked anonymously on 2026-11-24: the [GitHub Releases API](https://api.github.com/repos/Bluemethyst/BeamMPY/releases)
returns `[]`; no public wheel/installers release exists. The [public source ZIP](https://codeload.github.com/Bluemethyst/BeamMPY/zip/refs/heads/main)
and [raw shell installer](https://raw.githubusercontent.com/Bluemethyst/BeamMPY/main/scripts/install.sh)
return HTTP 200. The source ZIP includes `beammpy/web/index.html` and bundled
assets, so the interactive installers build/install the Python package from
that source without Node. They do not use a nonexistent `releases/latest` URL
or authenticated/expiring Actions artifact links. Downloads follow current
`main`; these commands are not version-pinned.

The latest anonymous check on 2026-11-24 confirms both installers and `setup.py`
return HTTP 200 and match the local corrected copies, including the Windows
launcher and Ubuntu service quoting/temporary-file fixes. The ZIP is 6,338,469
bytes and contains the compiled UI. Actual corrected Ubuntu service/boot/uninstall
validation still requires a disposable Linux systemd host; publication alone
does not verify it.

**Update checker publication required:** the canonical `beammpy/version.json`
currently returns HTTP 404 on public main. Publish it at the URL above together
with the checker, synchronized metadata and rebuilt `beammpy/web/` assets on
`main`. Until then a new checker fails quietly without an update notice. Keep
the public manifest at the version the same source ZIP actually installs; do not
advance it ahead of the matching package/UI. No GitHub Release assets are needed
for this source route. Nothing was pushed or published in this session.

If distributing wheels instead, publish `beammpy-VERSION-py3-none-any.whl` and
the matching `beammpy-VERSION-installers.zip` from `tools/package_installers.py`
to a public GitHub Release first. Actions artifacts are verification outputs,
not the public download source. See HANDOFF.md for checks actually run and the
remaining Ubuntu service verification.
