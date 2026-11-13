# Accounts and deployment scope

Requested 2026-11-13. File management is deferred. Keep one administrator and
allow administrator-created members with access to selected servers. Server
creation is an optional global permission. No public registration, email reset,
remote hosts, scheduling or automatic BeamMP updates are included.

The administrator manages member accounts, disables or deletes members, resets
passwords and assigns per-server checkboxes: power, map selection, mod toggling,
mod/map ZIP upload, configuration, console viewing and console commands. Console
commands are powerful and can stop a server independently of power permission.
Assigned servers are visible even with all action checkboxes off. Imports,
server deletion, executable reinstallation and account administration remain
administrator-only. Creators receive all member permissions on their new server.
Member mod writes require private instance-local resources; shared/external or
overlapping resource locations remain administrator-managed. Console commands
also require console viewing permission.

Version 0.4 adds a separate per-server View statistics grant for resource/player
graphs. Existing member grants remain unchanged until the administrator selects
that checkbox. New member-created servers include it in their initial grants.
It does not require console access; enabling the optional player plugin remains
an administrator-only stopped-server action. See STATISTICS.md.

First setup creates the administrator once. Existing account IDs/password hashes
survive migration; the oldest account becomes administrator and other historical
accounts receive no server access until assigned. Creation and reset include a
Temporary password checkbox (checked by default). Checked passwords must be
changed before managing servers; unchecked passwords permit direct sign-in and
clear any previous forced-change requirement. All new passwords require at least
eight characters with no additional character-class requirements. The 1,024
character maximum and null-character rejection remain.
All users can change their password using their current password and sign out
all sessions. Password/permission changes and disabling an account revoke its
HTTP and console sessions. API and Socket.IO enforce permissions independently
of the UI. The administrator cannot be disabled, deleted or demoted by this
interface. Deletion requires administrator authentication, CSRF and a confirmed
username, removes sessions/grants, and retains server registrations and files.

Provide local username discovery and offline password recovery with hidden
prompts and a stopped-panel lock. Recovery does not require knowing the old
password. Login explains the local recovery procedure without exposing host
paths or adding unauthenticated password-reset endpoints.

Windows PowerShell and Linux shell scripts install/update from a downloaded
release wheel into a private Python virtual environment, without Node. Program
files and data live in separate directories. Record the data location, refuse
updates while the panel is active, stage a new environment and validate it before
switching the launcher. Keep the previous environment for recovery. Installation
does not start a public listener, modify credentials, install system Python,
change firewall rules or install an OS service. Existing installations may use
their current data directory explicitly. Document manual start/stop and recovery.

Acceptance: disposable tests for legacy migration, setup closure, password/reset
revocation, disabled accounts, per-server/API/socket authorization and denied
cross-server operations; M3E account/admin browser workflows and narrow layouts;
installer failure/active-panel/data-preservation tests; backend, frontend, browser
and clean-wheel checks. Execute actual Windows script install/update checks.
Windows and Ubuntu 24.04 script/CI checks passed on Python 3.11 and 3.13 in
[v0.3.2 CI](https://github.com/Bluemethyst/BeamMPY/actions/runs/43400444506),
reviewed 2026-11-14. This verifies the account/deployment checks above; real Linux
BeamMP and full authenticated player joins remain separate unverified gates.
