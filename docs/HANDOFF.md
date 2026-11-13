# BeamMPY handoff

Updated 2026-11-13. Read ROADMAP.md before expanding scope.

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
`python tools/verify_distribution.py dist/beammpy-0.2.1-py3-none-any.whl`.
Official real smoke: `python tools/run_real_smoke.py` (downloads an official binary
and uses only temporary private instances). For a supplied binary, set
BEAMMPY_SMOKE_BINARY and run tests/test_real_beammp.py explicitly.

Next: run the configured Linux CI and real BeamMP smoke gate once a supported
host/repository is available. Windows implementation and package checks are done.
Mod/map management was subsequently authorised and implemented in v0.2 above;
remaining backlog items still require a separate specification.

## Resolved prototype defects

The old console command handler was empty and stdin was disconnected; streaming
only began on browser connect. Executable paths/existence checks and blocking
readline handling were unreliable. Setup rewrote .env; database connections leaked;
socket origins were unrestricted; requests was an undeclared dependency. These
paths were replaced rather than retained alongside the new instance APIs.
