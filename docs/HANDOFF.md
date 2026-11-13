# BeamMPY handoff

Updated 2026-11-14. Read ROADMAP.md before expanding scope.

## Owner-approved repository checkpoint

The owner reviewed the statistics UI and confirmed it looks good, then requested
committing and pushing the accumulated work. Reviewed the complete tracked and
untracked scope, main branch and origin destination. Remote main still matched
the preceding da15a09 checkpoint. Include statistics source/tests, compiled local
UI, Lua plugin, v0.4.1 metadata and documentation; runtime data, credentials,
environments, screenshots and dist/ artifacts remain excluded.

git diff --check passes. The same-session verification below remains current:
128 backend tests, TypeScript/build, eight browser scenarios and a clean v0.4.1
wheel install without Node. This repository checkpoint changes documentation only
and does not rerun application suites. No live runtime data was used.
Next: inspect Actions for the new push; real Linux BeamMP and authenticated player
joins remain separate open gates. No milestone has been marked complete.

## Current update: ten-second statistics detail, v0.4.1

The owner requested more frequent chart points than the default five-minute
aggregation. Statistics now defaults to Last hour and renders ten-second points,
with the existing five-second collection/refresh cadence. Longer ranges retain
their existing aggregation. Short-range tooltips/tables include seconds and the
interval label reads 10 sec rather than a fractional number of minutes.

Schema 5 adds statistics_recent, retaining ten-second summaries for 24 hours;
existing minute history remains available for 30 days in longer views. Both
resolutions are written in one transaction and each query reads only its intended
resolution, so joins are not double-counted. Detail is persisted across restarts,
pruned at startup/hourly and cascaded on server deletion. Existing users/hashes,
grants, minute history and managed plugin registrations survive migration. There
is no fabricated interpolation of old minute history into detailed points.

Windows verification: 128 backend tests pass, with two real-binary opt-in cases
skipped; TypeScript check/production build and all eight Playwright scenarios
pass. New tests verify distinct ten-second readings, persistence, unchanged long
rollups, retention/deletion and schema-4 history/plugin preservation. Browser
coverage verifies the default 10-sec label and switching between fine/coarse
ranges. The v0.4.1 wheel/source archive and installers ZIP are built; the clean
wheel check passes without Node, including the ten-second endpoint and bundled
UI/Lua plugin. git diff --check passes. Installer scripts are unchanged from the
preceding verified v0.4.0 run. Package/UI/CI paths are 0.4.1.
Lua telemetry and process/network controls
are unchanged, so the preceding official Windows plugin smoke remains historical
evidence; Linux and authenticated player joins were not rerun or claimed verified.

No live users.db, .env, server directories or credentials were read/changed and
the normal panel was not restarted. Restart the panel and refresh to use the
new default view. Detailed points begin with this version's collection; old
minute history is still available in longer ranges. Next: owner verification
of chart cadence and the existing Linux/real-player checks. No milestone was
marked complete and no commit/push was performed.

## Previous implementation: per-server statistics, v0.4.0

The owner approved statistics, explicitly scoped to each server's own Statistics
tab. Preserved the preceding documentation changes and implemented both resource
and aggregate player statistics. No host-wide totals or overview resource cards.

One panel collector samples only the owned BeamMP process every five seconds,
checking PID/creation time/executable and resetting CPU baselines on restart.
CPU 100% is one logical core; memory is process RSS in MiB. Collection works
without browsers or consoles. Schema 4 adds minute history and optional plugin
registrations while preserving account IDs/hashes, existing grants, directories
and TOML. Retention is 30 days with startup/hourly pruning; server deletion
cascades history. Queries are bounded; missing observations are null, with
explicit stopped/unavailable/stale states. Live bookkeeping is bounded.

The Statistics tab uses M3E cards/menu/checkbox and local SVG CPU/memory lines
and peak-online player bars, with averages/peaks, range selection, hover/keyboard
inspection and data tables. Mobile chart coordinates keep axis text readable.
Ranges: last hour, 24 hours, 7 days and 30 days. Poll generations prevent stale
range responses and unmounted-view updates. A separate statistics_view member
grant is enforced on every HTTP request. Existing grants are unchanged; creators
receive it on new servers. Statistics do not grant console access or use sockets.

Player collection is an explicit administrator/stopped-idle option, installing
only the bundled Lua plugin in verified private instance-local resources.
External/shared/linked/overlapping resources and existing/changed plugin files
are protected. Framed stdout snapshots contain counts and cumulative successful
joins; duplicate/out-of-order/old-process frames are ignored. Periodic snapshots
reconcile disconnects. No player identities, names, IPs or chat are stored, and
no client mod or network listener is needed. BeamMP's count may include syncing
clients. Repeat successful visits count as joins.

Verified on Windows/Python 3.13:

- Backend: 125 passed, two opt-in real-binary cases skipped. New tests cover
  ownership/restarts, collection/shutdown, migration preservation, rollups and
  retention, scoped/revoked access, plugin file protection, player frame handling
  and concurrent server creation.
- TypeScript check/production build and all eight Playwright scenarios pass.
  New browser coverage exercises collection without an open server view,
  fixture stdout/player events, ranges, tables, reload/stopped history, member
  restrictions/revocation, themes and 320/390px chart layouts. Screenshots in
  frontend/test-results/: desktop-statistics.png and mobile-statistics-dark.png.
  Visual inspection confirmed readable mobile axes.
- Fresh official Windows BeamMP v3.9.3: both opt-in cases passed with the bundled
  plugin's zero-player snapshots/process memory, IPv4-mapped/native IPv6 version
  acceptance, UDP ping, stdin help, restart and stop. These were disposable private
  loopback instances with throwaway keys, not authenticated game/player joins.
- Final wheel/sdist build and clean-wheel installation without Node pass,
  including UI/assets/licenses and enabling/removing the packaged Lua plugin.
  Verified the wheel's source/UI bytes match the checkout and source archives
  exclude runtime files. Windows v0.4.0 install/update/active-panel rejection and
  installed-launcher smoke checks pass with disposable data preserved byte-for-byte.
  Package/UI/CI paths are 0.4.0; the installers ZIP includes current STATISTICS.md.
  git diff --check passes. No live data was used for any of these checks.

Browser tests use a second disposable fixture on port 8792 to avoid the serial
account suite's login-attempt window; production throttling is unchanged. Normal
Windows permissions were needed for Playwright process teardown and networked
build/download checks. The Python fixture keeps early exits ahead of telemetry
imports; frame tests establish its real epoch before synthetic reload frames.

Updated STATISTICS.md, API/UI, roadmap and installation/account documentation.
No live users.db, .env, instances or credentials were read/changed; the normal
panel was not stopped/restarted. Apply by restarting the panel and refreshing
the browser. Resource data starts with the server; CPU needs two observations.
Enable Collect player statistics while stopped, then start that server. Existing
members need their View statistics checkbox selected explicitly.

Next: owner verification with actual player joins and the manual Linux official
BeamMP smoke workflow. Prior Linux CI evidence below is for v0.3.2, not this
uncommitted feature. Real Linux BeamMP and authenticated joins remain open gates;
no cross-platform milestone is marked complete. Other deferred features remain
deferred. No commit or push was performed.

## Previous discussion: proposed statistics feature

The owner asked what to build next and suggested joined-player statistics,
online-player bars and CPU/memory graphs. Reviewed process ownership/readers,
storage, grants and server tabs, plus the official BeamMP server API documentation.
The project already depends on psutil but has no metrics collector/history.
BeamMP documents player-count and join/disconnect APIs; a bundled optional Lua
telemetry plugin is proposed, not yet verified against a real binary.

Recorded a separate proposed scope in STATISTICS.md and linked it from ROADMAP:
resource CPU/resident-memory/uptime graphs first, then player counts/peaks/joins.
Suggested five-second live sampling, minute history retained for 30 days,
server-scoped statistics grants, explicit missing-data states and aggregate-only
player telemetry. Automatic plugin installation would be administrator-controlled,
stopped-only and limited to verified private instance resources.

No feature was implemented or approved in this discussion. Existing documentation
changes from the preceding CI review are preserved. No runtime data was accessed;
no application suites were rerun. Documentation validation: git diff --check.
Next: select the statistics scope, then implement resource collection/history and
the Statistics view before integrating player telemetry. Real Linux BeamMP and
authenticated player-join verification remain independent open checks.

## Current session: CI review and next-scope recommendation

The checkout was clean on main at `da15a09ec4374c229350cab93df816af44a36986`
(v0.3.2), matching the supplied checkpoint. Read the contributor guide, roadmap,
handoff, UI/API conventions, account/deployment scope, installation guide and
README before reviewing remote results.

Inspected [Checks run 43400444506](https://github.com/Bluemethyst/BeamMPY/actions/runs/43400444506),
triggered by that push on 2026-11-13, including all four job step summaries and
full logs through the GitHub connector. Windows and Ubuntu 24.04 both passed on
Python 3.11 and 3.13. Every job records:

- 102 backend tests passed; two opt-in real-binary cases skipped.
- TypeScript checking (included in build), production build and seven Playwright
  scenarios passed.
- Wheel/sdist and installers ZIP built; clean-wheel UI/assets/licenses, accounts,
  management API and CLI checks passed with Node absent from PATH.
- Actual platform install/update, active-panel rejection and installed launcher
  checks passed; disposable data was preserved byte-for-byte.

The optional official BeamMP smoke step was skipped in all four jobs because this
was a push run. Ubuntu fixture, package and shell-script execution are now
verified; real Linux BeamMP and full authenticated player joins remain open.
No failing checks or confirmed product regressions were found in this review.
No milestone was marked complete. Earlier sections below retain historical
verification statements; this section supersedes their unrun-CI/Linux-script status.

Updated ROADMAP.md, README.md, INSTALLATION.md and ACCOUNTS_DEPLOYMENT.md to reflect
the inspected evidence. This session changes documentation only. Local application
suites were not rerun; `git diff --check` passes. No live runtime files or
credentials were read or modified, and no panel or server was restarted.

Recommended next task: finish real BeamMP release validation with the existing
manual Checks workflow and `real_beammp=true`. Run the Windows/Ubuntu Python
3.11/3.13 matrix and require both loopback address families to pass startup,
version acceptance, UDP ping, stdin help, restart/version acceptance and stop.
Record exact run/binary/platform versions and fix only confirmed failures before
updating milestone status. This workflow was not dispatched in this session.
Real player authentication remains a separate check with a real client and
credentials. No new feature scope was selected or implemented; the deferred
features remain deferred. See ROADMAP.md for the reviewable acceptance checks.

## Repository checkpoint

The owner approved committing and pushing the accumulated v0.3.0–v0.3.2 work.
Reviewed the tracked/untracked scope and origin/main destination. Source, tests,
compiled UI, deployment scripts and documentation are included; runtime data,
credentials, environments, screenshots and dist/ artifacts remain excluded.
git diff --check passes. The same-session Windows verification below remains
current; this checkpoint changes documentation only and does not rerun suites.
Next: the owner's next requested scope, with Linux execution and authenticated
player joins still separate gates. No live runtime data was changed.

## Current fix: logout loading race, v0.3.2

The owner reported logout leaving Connecting to BeamMPY indefinitely until a
reload. Reproduced against the compiled v0.3.1 UI with a real disposable console:
hold /api/servers across logout, wait for the login form, then release a 401.
api.ts notified global expiry for this old request; expire() set ready=false,
but replacing the already-current /login route skipped its session guard. The
URL was correct while the login form disappeared. The browser test failed at
the login-heading assertion and showed the owner's loading screen.

api.ts now captures each fetch/upload's CSRF token and reports expiry only if
that token is still current. main.ts ignores expiry when already signed out and
forces genuine expiry through the route guard even when /login is current.
Session reads track a generation so an old /auth/session response cannot replace
a later login/logout/password result or its CSRF token. Authentication actions
and expiry invalidate earlier reads. Console continuations check whether their
view is still mounted before reconnecting. Revoked-session redirects still run
when applying the anonymous session has already unmounted the console.

The real-console regression additionally holds a disconnect-triggered session
refresh across logout, then delivers the old anonymous snapshot. It asserts the
login form stays visible and the next credential submission retains logout's
fresh CSRF token. Two isolated browser response-order tests cover delayed 401s
after logout and after a subsequent sign-in, without consuming real backend login
attempts. Existing session-revocation and account workflows remain covered.

Backend: 102 passed, 2 real-binary opt-in cases skipped. TypeScript/production
build and all seven browser scenarios pass on Windows. The regression failed
before the fix and passes afterwards, including token preservation and genuine
session revocation. The wheel/source archive and installers ZIP are built in
dist/. A clean wheel install passes bundled UI/assets/licenses, account and
management API checks, and CLI with Node absent from PATH. git diff --check
passes. Installer scripts are unchanged; Linux and player-join checks were not
rerun or claimed verified in this UI session.
Package/UI/CI paths are 0.3.2. No backend authentication rules, account hashes,
database schema, BeamMP startup/bind repair or runtime data were changed.

The preceding uncommitted work is preserved. Tests use disposable data only; the
normal panel was not stopped or restarted. Refresh once to load the new bundled
UI; later logouts should show a usable login form without reloading. Next: owner
verification and the next requested scope; Linux execution and authenticated
player joins remain separate gates. General file management stays deferred.

## Previous refinements: accounts, v0.3.1

The owner requested optional temporary passwords, My account spacing fixes, M3E
cards around users, member deletion (never the administrator), and eight-character
password minimums. Preserved the preceding uncommitted implementation and docs.

Creation and password reset now accept temporary (boolean, default true) and
expose a Temporary password checkbox. Checked requires a change at sign-in;
unchecked permits direct use and clears any prior forced-change requirement.
Both forms and all new-password UI/backend/CLI validation use a minimum of eight
characters, with no required character classes. The 1,024-character upper limit
and null rejection remain. Existing hashes and login compatibility are preserved.

DELETE /api/users/:id requires administrator authentication, CSRF and current
username confirmation. It removes the member's sessions and cascading grants,
disconnects consoles, and keeps all server registrations/directories/files. The
administrator is protected in the API and has no delete action. The UI uses the
shared M3E confirmation dialog with cancellation/focus restoration and a warning
that account deletion cannot be undone.

Each user is an actual M3E filled card with responsive action layout. My account
uses a single 16px field gap without the previous additive 20px field margin;
buttons retain intrinsic widths. User-card actions have their own flex layout,
avoiding the mobile page-header rule that squeezed button labels into columns.
Generated UI remains local and uses M3E/public tokens. Version metadata, UI and
CI artifact paths are 0.3.1; schema remains 3 with no migration needed.

Verified Windows backend: 102 passed, 2 real-binary opt-in cases skipped.
TypeScript/production build and all five browser scenarios pass. New tests cover
eight-character setup/change/member/reset/CLI passwords, seven-character rejection, boolean flag validation,
both directions of temporary status changes, deletion authorization/confirmation,
immediate HTTP/socket revocation and preservation of member-created servers.
Browser assertions cover both checkbox states on creation/reset, direct sign-in
after a permanent reset, admin protection, confirmed/cancelled deletion and focus
restoration, active-session revocation on deletion, 16px account field spacing,
intrinsic button width and 320/390px layouts. Screenshots in frontend/test-results/
include desktop-account.png, mobile-account.png, desktop-user-cards.png and
mobile-user-cards.png. The v0.3.1 wheel, source archive and installers ZIP are
built in dist/. A clean wheel install passes bundled assets/licenses, eight-letter
passwords, account creation/deletion/revocation, existing management APIs and CLI
checks with Node absent from PATH. git diff --check passes. The deployment scripts
themselves are unchanged from the preceding Windows-verified version; Linux
execution and real player joins were not rerun or claimed verified.

No live users.db, .env, server directories or credentials were read or modified
for testing. The normal panel was not restarted. Apply by restarting the panel,
then refreshing the browser. Next external gate remains Linux CI/script/BeamMP
execution; full authenticated player joins remain separate. General file
management remains deferred.

## Previous work: accounts and deployment, v0.3.0

The owner deferred general file management and requested setup/login/logout,
password recovery, Windows/Linux install/update scripts and additional users.
They explicitly chose selected-server permissions with optional server creation.
The separate scope is ACCOUNTS_DEPLOYMENT.md. Prior file-management review notes
and FILE_MANAGEMENT.md are historical, deferred proposals; do not implement them
as the next task. Existing uncommitted documentation was retained and updated.

Implemented My account (change password/sign out all devices), administrator-only
Users (create members, edit access, disable and reset temporary passwords), and a
login recovery dialog. Temporary-password users must change their password before
server access. Keep one administrator. Members have selected-server power, maps,
mod toggling/upload, configuration, console view/commands; commands require viewing
and can stop a server independently of the power checkbox. Creation is a separate
global flag and grants the new server to its creator. Imports, server deletion,
executable reinstallation and user administration remain admin-only. API and
Socket.IO both enforce authorization, independent of UI visibility. Directory
paths are omitted from member snapshots and all socket broadcasts. Account access
changes, password changes/resets and disabling revoke HTTP and console sessions.
Member mod writes require private instance-local resources. Shared/external roots
or overlaps with another instance remain administrator-managed; unreadable other
resource configurations fail closed for member writes. Regression checks cover
both an assigned server pointing at another root and another server consuming its
root. Existing administrator behavior and installations are preserved.

Schema 3 adds flags and per-server grants without changing existing user IDs,
password hashes, server directories or TOML. The oldest legacy account becomes
administrator; other historical accounts start without assignments. Local CLI
commands create-admin, list-users and reset-password take the stopped-panel lock
before prompting. Recovery preserves grants and does not re-enable disabled users.
The existing :: default and atomic legacy wildcard repair are unchanged.

scripts/ contains Windows PowerShell and Linux sh install/update/launch wrappers
and the standard-library manage.py bootstrap. Release wheels install into private,
versioned virtual environments. Program and data paths must be separate. Updates
probe the existing panel lock before installation and recheck it at activation;
validation uses disposable data, not the user's DB. Failed environments are
cleaned up, first installs remain retryable, and previous environments are retained.
Installed launchers remember the data location and support local account commands.
BEAMMPY_PYTHON can select a specific interpreter. No Node, OS services, firewall
changes or BeamMP binary updates are introduced. INSTALLATION.md documents usage,
manual backups before migration and recovery limitations. package_installers.py
bundles scripts/docs alongside wheels. CI now exercises platform script workflows.

Verification on Windows/Python 3.13: **93 backend tests pass, 2 real-binary opt-in
cases skipped**; TypeScript/production build and **all 5 browser scenarios pass**.
New coverage includes legacy multi-user preservation, forced password changes,
HTTP/socket access isolation, allowed and denied actions, current-map protection,
session revocation/reset/disable, local setup/recovery, active locks and installer
failure cleanup. Browser coverage adds recovery dialog focus/timing, temporary
passwords, map-only member access, rejected direct power calls, reset/disable,
sign-out-all and the 320px M3E permissions dialog. Screenshot:
frontend/test-results/mobile-user-permissions.png. Real PowerShell install/update,
active-panel rejection and installed-launcher checks passed using paths with
spaces and disposable data; users.db, .env, config and owner files were preserved
byte-for-byte. The v0.3.0 wheel/source archive and installers ZIP are built in
dist/. A clean wheel install verifies bundled UI/assets/licenses, accounts and
temporary-password restrictions, authentication, maps, mods, deletion and CLI
with Node absent from PATH. The final script smoke also passed with an explicit
BEAMMPY_PYTHON override. Shell scripts have LF endings; their execution is still
unverified on Linux. git diff --check passes.

Version metadata, UI footer and CI wheel path are 0.3.0. No production data or
credentials were used, and the normal panel was not stopped, started or migrated.
Restart the panel after upgrading to load routes/schema changes, then refresh
the browser. Next: run Ubuntu CI and the Linux installer/BeamMP checks on a real
Linux host; full authenticated player joins remain an independent gate. No Linux
support or cross-platform milestone is marked verified by this session.

## Earlier review: deferred file management proposal

Read AGENTS.md, ROADMAP.md, this handoff, UI.md, API.md and README.md before
reviewing the implementation. Git status was clean at session start on main;
HEAD was fba3b17. No existing changes needed preservation. Application behavior,
compiled assets, runtime data and version 0.2.3 are unchanged in this session.

Reviewed authenticated API/CSRF integration, per-instance idle and power locks,
atomic configuration writes, resource resolution, mod/map guards, archive/upload
limits, deletion ownership checks, Vue routing/M3E adapters and disposable tests.
Important distinction: existing mod management supports external ResourceFolder
paths; that resolver is not sufficient containment for a general file manager.
Generic access to Client or .beammpy-disabled could bypass the current-map guard.
New file access needs explicit ancestor/link/ownership and credential protection,
including Windows junctions and hard links, plus download response handling.

Recommended a Files tab initially confined to instance-local ResourceFolder/Server
with browse, upload/download, create folders, rename files and delete files/empty
folders. All changes require a stopped idle instance. No overwrites, raw text
editing, recursive deletion, external/shared resources or new hosting features.
The reviewable proposal and acceptance checks are in FILE_MANAGEMENT.md; ROADMAP
links it as proposed work. The owner requested a scope proposal before coding;
implementation has not started. Next: agree this boundary, then implement the
dedicated file service/API and M3E Files view with the listed isolation tests.

Verification for this documentation-only session: source/test inspection and
`git diff --check`; no application suites or platform smoke checks were rerun.
The prior 68-backend-test, four-browser-scenario and clean-wheel evidence remains
historical evidence below. Linux execution and authenticated player joins remain
open gates. No milestone has been marked complete.

## Current UI refinements: v0.2.3

The owner requested the linked M3E tabs, correct left alignment, no redundant
Workspace heading, yellow P/blue Y Python branding, removal of the configuration
map dropdown, and a palette menu beside logout. All are implemented. ServerTabs
already used actual M3E elements; it now uses primary tabs and sets the public
scrollable edge-padding token to zero, removing the 52px inset. Keyboard manual
activation, tab panels and guarded navigation remain covered by browser tests.
Removed the topbar titles and overview/sidebar Workspace labels; All servers.
remains the page heading. Branding colours are fixed independently of themes.

MapPicker and the unused UiSelect adapter are retired. Settings save excludes
Map, so saving unrelated settings cannot overwrite map-manager changes. Maps
remain available exclusively through their manager tab.

AppearanceMenu uses real M3E menu/submenu radio items and a M3E custom-colour
dialog. It includes light/dark/system, Blue/Purple/Teal/Green/Amber/Rose, a hex
field plus native colour picker, Vibrant/Tonal spot/Expressive/Neutral/Monochrome
styles, and reset. appearance.ts generates full light/dark roles in the browser
using M3E createTheme. Validated preferences persist locally and follow OS changes
in system mode; malformed preferences safely fall back. The default build-time
blue stylesheet still provides the initial theme. All assets remain local.

Verification: TypeScript/production build and all 4 Playwright scenarios pass.
New checks cover tab/content alignment, logo colours, removed controls and Map
omission on save, preset/custom palette generation, invalid hex and cancellation,
reload persistence, system appearance changes, reset and 320/390px layouts/menus.
Screenshots are in frontend/test-results/, including mobile-appearance.png and
mobile-teal.png. This session changes UI and docs; the preceding join fix remains
in the workspace. Refresh the browser after building. No production instances or
credentials were used for these tests; full game-join/Linux gates remain as below.

The v0.2.3 wheel and source archive are built in dist/. A clean wheel install
verifies the bundled UI/assets/licenses and API/CLI checks with Node absent from
PATH. Package versions, the UI footer and the CI wheel path agree.

## Current fix: client identification / bad address cast, v0.2.2

The owner reported all joins failing with code C `bad address cast` and Socket
Closed Code 3 while a standalone server worked. Read-only inspection confirmed
the managed v3.9.3 instance used IP=0.0.0.0, which came from the panel's default.
BeamMP itself defaults to ::, disables V6ONLY for TCP/UDP, and calls to_v6() on
the incoming peer before version/auth handling. An IPv4 listener triggers the
exception. Sources: https://github.com/BeamMP/BeamMP-Server/blob/v3.9.3/src/Settings.cpp
and https://github.com/BeamMP/BeamMP-Server/blob/v3.9.3/src/TNetwork.cpp.

Corrected the new-instance and missing-IP defaults to ::. At the next start,
legacy 0.0.0.0 is atomically repaired to :: only after dual-stack port checks
pass and while the instance is stopped; the console explains the repair. TOML
comments, keys and other sections survive. Explicit interface binds are not
rewritten; IPv4-only binds receive a console warning and settings guidance.
Preflight TCP/UDP probes now disable IPV6_V6ONLY too, catching occupied IPv4 ports.

Verification: 68 backend tests pass; 2 real-binary cases are opt-in in the normal
run. Regression checks cover defaults, stopped-only/idempotent repair, comments
and AuthKey preservation, failed atomic writes, specific-interface preservation,
and TCP/UDP IPv4 conflicts. The fresh official Windows v3.9.3 smoke run passes
both IPv4-mapped and native IPv6 loopback tests: code C + framed version packet
accepted (A), UDP ping replied (P), stdin help, restart + handshake, and stop.
This tests identification, not a full authenticated game/player join. The
earlier smoke run only tested power/console and had missed this networking bug.
Smoke tests now wait for BeamMP's own startup summary before version negotiation.
TypeScript/build and all 3 browser scenarios pass. Browser creation now chooses
an available disposable port so the tests do not collide with an active server
on the normal 30814 port. The v0.2.2 wheel/source archive are built in dist/.
A clean wheel installation also passes bundled assets/licenses, authentication,
maps/mods/deletion and CLI checks with Node absent from PATH.

Automatic approval review rejected selecting a test executable via the live DB;
the reproduction and verification instead downloaded a fresh official binary
and used temporary loopback-only installations with throwaway keys. No production
files were written and the user's running instance was not stopped or restarted.

Apply: restart the panel to load the fix, then start the managed instance. The
legacy wildcard will be repaired automatically. Immediate workaround with the
current panel: stop the instance, set Configuration > Bind IP to ::, save and
start. Next: have the owner retry a real game join; Linux smoke remains pending.

## Repository setup

The owner added the Git repository on main with origin pointing to
https://github.com/Bluemethyst/BeamMPY.git and requested the initial commit.
The snapshot includes source, compiled local UI assets/licenses, tests, docs,
packaging and CI. Runtime data, credentials, dependencies, build artifacts and
local VS Code/MCP settings are excluded through .gitignore. Verification from
the implementation session is recorded below; commit preparation changes only
ignore rules and these notes.

## Current follow-up: M3E UI correction, v0.2.1

The owner pointed out that the UI barely used M3E and requested it for essentially
all components. The original integration bundled the library but overrode its
appearance and used bespoke forms, dialogs, navigation and notifications. This
is now corrected across setup/login, overview, console, settings, maps and mods.

Actual M3E elements provide text fields, checkboxes, dialogs, menus, tabs/panels,
drawers, icons, progress/loading and queued snackbars. Buttons, switches, radios,
cards, lists, surfaces and badges use its CSS DOM contracts. The package does not
provide a dedicated select or switch custom element; supported CSS controls and
radio menus cover those cases. The old style.css and SVG icon set are removed.
layout.css arranges the screens and terminal content, and public component tokens
handle destructive red and responsive field widths. See docs/UI.md and AGENTS.md.

The generated blue theme uses M3E createTheme with the vibrant palette and
expressive motion. Theme generation runs at dev/build time, with light/dark/system
selection still saved locally. Material Symbols and its Apache license are bundled
alongside the existing local fonts and notices. Release users still need no Node.

Integration details: M3E text fields supply aria-required but not native required;
UiField restores required/min/max/minlength validation, normalises boolean and
numeric custom-element properties, and keeps masks, autocomplete and native form
submission. M3E owns modal focus management, keyboard menus/tabs and snackbar
timing. Guarded routing still asks before discarding configuration changes.

Verification: **62 pytest checks pass, 1 opt-in real-binary test skipped**;
TypeScript and production build pass. All **3 expanded Playwright scenarios pass**
against Waitress and disposable fixtures. Added checks cover required/length/range
validation, checkbox reveal, stopped-only controls, switch persistence, keyboard
tabs and map menus, drawer focus trapping/restoration, themes, and 320/390 px
configuration overflow. Screenshots of desktop/mobile, dark theme, navigation,
maps/mods and configuration are in frontend/test-results/. No backend behavior or
production data was changed. The owner may still be using the normal panel.

The v0.2.1 wheel and source archive are in dist/. A clean Python environment
installed the wheel and verified bundled UI/assets/licenses (including Material
Symbols), authentication, maps, mods, deletion and CLI with Node absent from PATH.
Runtime data was excluded. The UI and package versions and CI wheel path agree.

Refresh the browser to load the newly compiled assets. The prior Linux execution
and real BeamMP release gates remain open; this UI session does not change their
status. Next: preserve these M3E conventions for new screens, and run the Linux
release checks on a supported host when available.

## Current follow-up: v0.2.0

The owner explicitly authorised these additions while Linux release validation
remains open. Implemented red stopped-only server deletion at the bottom of
configuration, unnumbered headings, required AuthKey on creation/start, stock and
custom map management, client ZIP mod upload/enable/disable, and browser ZIP plus
host-local folder/ZIP server imports. Configuration has a map dropdown as well.

Deletion requires the server name and defaults to retaining files. Permanent
file removal is a separate checkbox; data roots, nested instances and other
instances' resource locations are protected. Schema 2 adds ignored-import paths
so deleting a legacy instance does not resurrect it on restart. Manual re-import
is allowed. Existing user records/hashes and server registrations are preserved.

Archive imports reject traversal, links, encryption, duplicate names and unsafe
paths, and clean up partial extraction. Source ZIPs remain unchanged. Safe bundled
relative ResourceFolder paths survive; stale absolute/external paths become local
Resources. Uploads default to 2 GiB per ZIP (BEAMMPY_UPLOAD_LIMIT); archives are
limited to 20,000 entries/8 GiB expanded. Waitress and Flask use matching upload
limits. Mods live in configured ResourceFolder/Client; disabled ZIPs move outside
Client to .beammpy-disabled. The current map's mod cannot be disabled accidentally.

Verification: **62 backend tests pass, 1 real-binary opt-in test is skipped in the
default run**. All three browser scenarios pass, including ZIP
upload/import, map selection, mod toggles, and both deletion choices in disposable
directories. The official BeamMP v3.9.3 Windows start/help/restart/stop smoke test
also passed with AuthKey enforcement. TypeScript and the v0.2 frontend build pass.
The v0.2 wheel/source archives are built. A clean Python environment installed the
wheel and passed bundled UI/assets/licenses, authentication, maps, mods, deletion
and CLI checks with Node absent from PATH. Runtime data is excluded from packages.
Mod uploads also reject ZIPs containing server configuration/panel data, keeping
accidentally selected server backups out of client-distributed mods.

Restart the running panel to load new routes and migrate the database, then refresh
the browser. Tests never target the user's existing users.db or server directory;
their timestamps may change as the owner uses the normal panel.

The sections below record the original v0.1 baseline and its verification.

## Current state

The first-release implementation is present. Foundations and Vue migration are
verified on Windows. Core management is verified with disposable processes and
real Windows BeamMP. Linux execution remains a release gate. No remote CI has
been run. Git metadata and an upstream URL were subsequently added by the owner;
see Repository setup above.

## Implemented

- Flask app factory, separate auth/API/process/configuration/installation services,
  versioned SQLite migration, scoped connections, per-instance registry, idempotent
  registration of legacy server/ in place, and singleton data-directory lock.
- Session-cookie authentication with database-derived initial setup, CSRF checks,
  login throttling, JSON error codes, token rotation/revocation, and offline CLI
  password reset. Existing account hashes are retained; .env is never rewritten.
- Vue 3/TypeScript/Vite, Router and Pinia; locally bundled M3E; responsive overview,
  setup/login, consoles, typed settings, confirmations, notifications, search,
  light/dark/system themes, and mobile keyboard navigation. Old MDUI code removed.
- Official stable release installer with platform matching, progress, bounded
  download, atomic executable placement, cancellation, and retry. Absolute-path
  import never rewrites existing instance files.
- Per-instance power locks, absolute paths/cwd, stdin commands without a shell,
  independent bounded readers, 1,000-line replay, AuthKey/ANSI redaction, authenticated
  instance rooms, active operation recovery on reload, and logout revocation.
- Atomic stopped-only TOML editing preserving comments, unknown/plugin content
  and omitted AuthKeys; typed validation and port conflict checks.
- Graceful shutdown followed by terminate/kill escalation; ownership identity
  journaling and crash cleanup. Windows uses the acquired Popen handle when
  terminating a live owned root; descendants are also cleaned up. Startup leaves
  servers stopped. Shutdown attempts every instance even if one fails.
- Python CLI, threaded Waitress/Socket.IO polling deployment, built frontend in
  wheel, source manifest, third-party licenses, MIT project license, and optional
  real-binary smoke tooling. API reference: docs/API.md; operations: README.md.

## Verified

- `python -m pytest -q`: **37 passed, 1 intentionally skipped**. The skipped test
  requires explicit opt-in to a real BeamMP binary. Tests use temporary databases,
  directories and subprocesses, never the existing installation.
- `npm --prefix frontend run build`: TypeScript and production build pass. All
  frontend assets and fonts are local; the build copies full dependency notices.
- Playwright: **2 end-to-end scenarios pass**, covering setup/login/logout,
  creation/install, start/stop/restart, console stdin/output/reconnect history,
  stopped-only settings and persistence, unsaved-navigation confirmation, import
  validation and successful import, mobile layout/themes/keyboard navigation,
  and expired HTTP and console sessions.
- The supplied Windows BeamMP executable passed isolated start/help/restart/stop
  checks, including fallback shutdown. No existing AuthKey/config was used.
- The actual installer downloaded official **BeamMP v3.9.3** and its Windows
  executable passed the same private, loopback-only smoke test with a throwaway
  AuthKey (6.70 seconds). Release asset names were checked against the official
  API and match the Windows/Ubuntu/Debian architecture selector.
- `pip check`: no broken requirements. MIT-licensed wheel and source archive
  build successfully. The wheel was installed into a clean Python environment;
  API, bundled UI/assets/licenses and CLI passed with Node absent from PATH.
  Runtime data/binaries are excluded from the package. Artifacts are in dist/.
- Existing users.db, .env and server/ServerConfig.toml retain their original
  modification times. The normal panel was not launched against production data.

## Environment findings and remaining release checks

- This host is Windows / Python 3.13 / Node 22.14. No installed WSL or Docker is
  available, so Linux behavior cannot be claimed verified here.
- `.github/workflows/checks.yml` configures Windows/Ubuntu 24.04 and Python
  3.11/3.13 tests, browser checks, packaging and clean-wheel verification. Manual
  workflow dispatch can enable official real BeamMP smoke testing.
- Windows sandboxed Playwright could run scenarios but could not complete its
  process-tree teardown. Running with normal Windows permissions completed
  successfully. No product workaround was introduced for that limit.
- Sandboxed pytest temp/cache directories can be inaccessible to normal Windows
  processes. The official smoke runner therefore creates its own fresh basetemp
  and disables pytest's shared cache.
- Public game connectivity, real player joins, and external HTTPS proxy setup
  are not covered by loopback smoke tests. Read the documented deployment steps.

## Commands and next action

Use the project virtual environment. Backend: `python -m pytest`. UI:
`npm --prefix frontend run build`. Browser: `npm --prefix frontend run test:e2e`.
Package: `python -m build`, then
`python tools/verify_distribution.py dist/beammpy-0.4.1-py3-none-any.whl`.
Official real smoke: `python tools/run_real_smoke.py` (downloads an official binary
and uses only temporary private instances). For a supplied binary, set
BEAMMPY_SMOKE_BINARY and run tests/test_real_beammp.py explicitly.

Next: run the existing manual CI workflow with `real_beammp=true` to verify real
Linux BeamMP (and refresh Windows binary evidence). The latest push has already
passed Windows/Ubuntu fixture, browser, package and installer checks; see the
current-session review above. Full authenticated player joins remain separate.
Mod/map management was subsequently authorised and implemented in v0.2 above;
remaining backlog items still require a separate specification.

## Resolved prototype defects

The old console command handler was empty and stdin was disconnected; streaming
only began on browser connect. Executable paths/existence checks and blocking
readline handling were unreliable. Setup rewrote .env; database connections leaked;
socket origins were unrestricted; requests was an undeclared dependency. These
paths were replaced rather than retained alongside the new instance APIs.
