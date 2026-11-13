# Installation, updates and account recovery

BeamMPY needs Python 3.11 or newer. Release wheels include the interface and do
not need Node. Install Python yourself before running these scripts; on Linux,
your distribution may package venv/pip support separately (for example
python3-venv on Ubuntu). Run as your intended unprivileged panel account.

Use the BeamMPY wheel and matching installers ZIP from the release artifacts.
Extract the ZIP into a working directory; keep manage.py, beammpy.ps1 and
beammpy.sh together. Source archives also contain the same files under scripts/.
The ZIP contains scripts and these instructions, not Python or the wheel.
Paths with spaces are supported. The scripts install Python dependencies from
the configured pip index; outbound network access is needed unless you supply
an offline wheel directory with --wheelhouse.

## Windows

From PowerShell in the extracted installers directory:

```powershell
.\install.ps1 --wheel "C:\Downloads\beammpy-0.4.1-py3-none-any.whl" --install-dir "C:\BeamMPY\app" --data-dir "C:\BeamMPY\data"
& "C:\BeamMPY\app\beammpy.ps1" start
```

Python's Windows launcher (py -3) is used when available, otherwise python must
be on PATH. Set BEAMMPY_PYTHON to a specific Python executable if needed; the same
override is supported by the Linux scripts and the verification matrix.
If Windows marks downloaded scripts as blocked, inspect the trusted
release files and use Unblock-File on those scripts as appropriate to your local
PowerShell policy. The installer does not change execution policy.

## Linux

```sh
sh ./install.sh --wheel "$HOME/Downloads/beammpy-0.4.1-py3-none-any.whl" --install-dir "$HOME/BeamMPY/app" --data-dir "$HOME/BeamMPY/data"
sh "$HOME/BeamMPY/app/beammpy.sh" start
```

The shell scripts use python3. If this interpreter cannot create a virtual
environment, install the distribution's venv support first. Actual shell-script
installation/update, active-panel rejection and installed-launcher checks passed
on Ubuntu 24.04 with Python 3.11 and 3.13 in
[v0.3.2 CI](https://github.com/Bluemethyst/BeamMPY/actions/runs/43400444506).
Real Linux BeamMP execution remains a release gate; that run skipped the optional
real-binary smoke checks. Full authenticated player joins remain unverified.

## First account and routine access

Open http://127.0.0.1:8080 on the host and create the administrator. This setup
closes permanently once any account exists. Alternatively, before starting the
panel, use the installed launcher with create-admin --username YOUR_NAME. Its
password prompts are hidden; passwords are never command-line arguments.

The installed launcher is beammpy.ps1 on Windows and beammpy.sh on Linux. It
remembers the data directory; you do not need to repeat it. start accepts --host
and --port, defaults to loopback:8080, and stays in the foreground. Ctrl+C stops
the panel and its owned servers. The scripts do not add services, autostart,
firewall rules or public listeners. Follow README.md for an HTTPS proxy/LAN setup
after creating the administrator. Never run two panel processes on one data dir.

My account changes your password and signs out all sessions. Users lets the
administrator create members, set passwords, disable/delete members and
assign access to selected servers. New/reset members change their password at
first sign-in when Temporary password is checked. Uncheck it to set a password
without forcing a change. New passwords need at least eight characters. Deleting
a member signs out their sessions and retains servers/files; the administrator
cannot be deleted. Access changes revoke sessions. See ACCOUNTS_DEPLOYMENT.md for
the permission model; upload covers vehicle and map ZIPs in the same mod manager.
Member mod writes require private instance-local resource folders. Shared or
external resources remain available to the administrator through the existing
mod manager.

Version 0.4 adds Statistics on each server dashboard. CPU, memory and uptime are
for that BeamMP process only. Grant members View statistics separately in Users.
As administrator, stop a server and enable Collect player statistics on its
Statistics tab to install the optional bundled server plugin. Start the server
to collect online counts and successful joins; no client mod is needed. History
is retained for 30 days. See STATISTICS.md for resource restrictions and units.

## Forgotten passwords or usernames

Stop the panel first. From its installed application directory:

```powershell
.\beammpy.ps1 list-users
.\beammpy.ps1 reset-password --username YOUR_NAME
```

```sh
sh ./beammpy.sh list-users
sh ./beammpy.sh reset-password --username YOUR_NAME
```

The reset prompts for a new password twice and revokes sessions. Accounts,
permissions and servers remain intact. Resetting a disabled member locally does
not re-enable it. Members may ask the administrator for a temporary reset from
Users; the administrator uses local recovery when locked out. There is no email
reset endpoint. The login recovery dialog shows these same instructions.

Manual pip installations use beammpy list-users, beammpy create-admin or
beammpy reset-password, with --data-dir YOUR_DATA_DIRECTORY. The stopped-panel
lock applies to all local account maintenance.

## Updates

Download the new wheel and matching installers bundle. Stop the panel cleanly,
then copy the complete data directory and imported server directories to your
own backup location before updating. This remains a manual backup operation.

```powershell
.\update.ps1 --install-dir "C:\BeamMPY\app" --wheel "C:\Downloads\beammpy-NEW_VERSION-py3-none-any.whl"
& "C:\BeamMPY\app\beammpy.ps1" start
```

```sh
sh ./update.sh --install-dir "$HOME/BeamMPY/app" --wheel "$HOME/Downloads/beammpy-NEW_VERSION-py3-none-any.whl"
sh "$HOME/BeamMPY/app/beammpy.sh" start
```

Use the same install directory each time. Updates reuse its recorded data
directory and refuse an active panel. A fresh virtual environment is installed
and validated against disposable data; activation rechecks the panel lock. Failed
installation leaves the active environment selected. Existing environments are
retained; installation.json records active/previous paths and the data directory.
Only start the new panel when ready to apply database migrations. Do not switch
to an older environment after migration without also restoring its matching data
backup. The scripts never replace .env, account records or BeamMP installations,
and do not update BeamMP binaries.

To adopt a manual installation, stop it and use install with a separate empty
application directory and --data-dir pointing to its existing data. Imported
server directories retain their registered locations. Do not choose a data
directory inside the application directory or vice versa. Defaults are sibling
app and data directories under your home's BeamMPY folder.

For an interrupted installer, check that no installation process remains before
removing its .install.lock. Preserve installation.json and environments/; cleanup
of old environments is intentionally manual. A failed pip command may require
checking network access, Python compatibility, wheel completeness or disk space.
