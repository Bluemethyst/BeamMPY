# BeamMPY roadmap

Agreed 2026-11-13: free, self-hosted Python/Flask panel with Vue 3, TypeScript,
Vite, Pinia, Vue Router, and locally bundled M3E. One administrator manages
multiple local BeamMP instances and grants members access to selected servers.
Windows and supported Linux distributions are intended targets.
Release users need Python, not Node. Planned panel shutdown stops owned servers.
Project license: MIT (confirmed by the owner during implementation).

## Current delivery status

| Milestone | Status |
| --- | --- |
| 1. Foundations | Complete; migration, preservation, isolation and locking verified |
| 2. Vue migration | Complete; TypeScript, production build and browser scenarios verified |
| 3. Reliable management | Implemented; Windows/Ubuntu fixture integration and historical real Windows BeamMP verified; real Linux BeamMP pending |
| 4. Release readiness | Windows/Ubuntu packaging, clean install without Node and installer/update checks verified; real Linux BeamMP gate pending |

Do not call this a cross-platform release until the real Linux BeamMP smoke check
passes on a supported Linux host. The latest push passed the Windows and Ubuntu
24.04 workflow on Python 3.11/3.13; the optional real-binary step was skipped.
Full authenticated player joins remain separately unverified.

## CI review and recommended next scope (2026-11-14)

Reviewed [Checks run 43400444506](https://github.com/Bluemethyst/BeamMPY/actions/runs/43400444506)
for the latest push, `da15a09ec4374c229350cab93df816af44a36986` (v0.3.2).
All four jobs passed. Each log confirms 102 backend tests passed with two
real-binary cases skipped, TypeScript/production build passed, seven browser
scenarios passed, wheel/sdist and installers ZIP built, clean-wheel checks passed
without Node, and actual platform install/update/active-panel rejection/installed
launcher checks passed with disposable data preserved byte-for-byte. No failing
checks or confirmed product regressions were found in this review. These are
remote results for that commit, not newly rerun local suites.

Recommended next scope: finish real BeamMP release validation using the existing
Checks workflow's manual `real_beammp=true` input. This recommendation has not
started a new feature or dispatched a workflow. Acceptance for that work:

- Run the official-binary smoke checks on Ubuntu 24.04 and Windows in the existing
  Python 3.11/3.13 matrix, using disposable private loopback instances only.
- Require both IPv4-mapped and native IPv6 cases to pass startup, version
  acceptance, UDP ping, stdin help, restart/version acceptance and shutdown.
- Fix confirmed failures within that scope, rerun affected checks, and record
  run links, OS/Python and BeamMP versions before changing milestone status.

The smoke tests use throwaway keys and do not authenticate a game client. A full
player join still needs separate evidence with a real client and credentials.
General file management, backups/restores, monitoring/player tools, scheduling,
BeamMP updates and remote hosts remain deferred.

## Ordered milestones

1. **Foundations:** app factory, separated auth/API/services, scoped database
   connections, versioned migrations, per-instance registry, idempotent import of
   the legacy server directory in place. Existing accounts and data unchanged.
2. **Vue migration:** setup/login, server overview, console, settings, responsive
   navigation, notifications/confirmations, accessible forms, blue accent and
   system/light/dark themes. Remove MDUI after parity.
3. **Reliable management:** official release installation with progress/retry,
   import, instance-scoped power operations, stdin commands, independent output
   readers and 1,000-line history, typed TOML editing preserving unknown content,
   port validation, shutdown escalation, singleton lock and orphan reconciliation.
4. **Release readiness:** Python CLI/package containing built UI, threaded
   Waitress and Socket.IO polling, localhost default, installation/upgrade/data
   backup/proxy/reset documentation, Windows/Ubuntu automation and real BeamMP
   smoke tests on both platforms.

## Acceptance

- Existing hashes and server contents survive migration; repeat startup does not
  duplicate imports. Two instances operate independently.
- Setup closes after account creation. APIs return JSON 401/409 errors; writes
  require CSRF and consoles authenticate and isolate subscriptions/commands.
- Installation errors can be retried. Power operations serialize per instance.
- Console starts with the process, works without a browser, replays on reconnect,
  and never crosses server boundaries. Logout revokes console access.
- Configuration preserves secrets/unknown sections/comments and writes atomically
  while stopped. Port conflicts and invalid settings are explained.
- Planned shutdown stops owned servers; crash leftovers are identified by PID,
  creation time and executable. Startup leaves all instances stopped.
- Clean release works without Node. Browser and process integration tests pass;
  actual BeamMP smoke tests are required before claiming platform support.

## Current follow-up (owner requested 2026-11-13)

Implemented in v0.2.0: red server deletion at the bottom of configuration, unnumbered
configuration headings, required AuthKey during creation and before starting,
stock/custom map selection and ZIP mod upload/enable/disable, and support for
browser ZIP uploads plus host-local folders/ZIPs for importing servers. This work
is explicitly authorised while the Linux release-validation gate remains open.
Deletion requires a stopped instance and a name confirmation; deleting files is
an explicit additional choice. Tests use disposable installations. Schema 2 keeps
deleted legacy instances from being automatically re-imported. Windows backend
and browser checks pass. The v0.2 wheel and source archive are built, and a clean
installation without Node passes authentication, maps, mods, deletion and UI checks.

## Current UI correction (owner requested 2026-11-13)

Replace the partial M3E adoption with the library's actual components and DOM
contracts throughout: text fields, checks/switches/radios, menus, dialogs,
navigation, tabs, cards/lists/badges, icons, progress and snackbars. Generate the
blue light/dark theme with M3E tokens. Retain application layout and console
rendering, but remove bespoke CSS that overrides component shapes and controls.
Verify existing forms, validation, guarded navigation and management workflows.

Implemented in v0.2.1. The original partial adoption is replaced throughout all
screens. Native form validation is preserved by the Vue text-field adapter;
keyboard navigation, focus restoration, switches, menus and narrow configuration
layouts are covered by the expanded browser scenarios. See UI.md for conventions.

## Client connection correction (v0.2.2)

v0.2.2 corrects the IPv4-only bind default that broke BeamMP 3.9.x joins.
New instances use `::`; old wildcard configurations are repaired on start while
stopped. Port probes match BeamMP's TCP/UDP dual-stack settings. The real Windows
smoke check now exercises code C/version acceptance and UDP ping on IPv4/IPv6
loopback, including a version handshake after restart. Full game/player joins
still require a real client and credentials; Linux execution remains pending.

## UI refinements (v0.2.3)

Implemented the owner's next UI requests: M3E primary scrollable tabs aligned
to the content edge, simplified All servers heading/header, Python-yellow P and
Python-blue Y in the logo, map selection exclusively in the Maps tab, and a
palette icon beside logout. Appearance uses M3E's runtime theme generator with
light/dark/system modes, six preset colours, custom colour selection, five
palette styles and reset. Preferences persist in this browser. Four browser
scenarios and the production TypeScript/build verify these changes.

## Accounts and deployment (v0.3.0)

The owner deferred file management and requested account/setup/recovery work,
Windows/Linux installation and updates, plus members with permissions on selected
servers and optional server creation. The separate agreed scope is recorded in
[ACCOUNTS_DEPLOYMENT.md](ACCOUNTS_DEPLOYMENT.md). Implementation adds My account,
administrator-managed users, temporary-password changes, per-server HTTP/console
authorization, local username discovery/administrator creation, and release-wheel
install/update/launch scripts with isolated environments and separate data.

Initial Windows verification is recorded in HANDOFF.md. The CI review above now
verifies Ubuntu script execution too; real Linux BeamMP remains an open gate.
No cross-platform milestone is marked complete.
Member mod writes are confined to private instance-local resources so grants
cannot mutate another server's shared resources; the owner retains existing
shared/external mod management. Windows has 93 passing backend tests, five
browser scenarios and clean-wheel/script-install checks.
See [INSTALLATION.md](INSTALLATION.md) for installation, update and recovery.

## Account refinements (v0.3.1)

Owner-requested corrections: optional Temporary password checkboxes on member
creation/reset, confirmed member deletion with administrator protection, M3E
cards for each user, corrected My account spacing and intrinsic-width buttons,
and a consistent eight-character minimum for new passwords in setup, member
management, self-service changes and the local CLI. Existing passwords/hashes
remain valid. Deletion removes sessions/grants and retains servers/files. The
temporary checkbox is checked by default; unchecking clears forced-change status.

Windows verification: 102 backend tests, TypeScript/build, all five browser
scenarios and a clean wheel install without Node pass. Details are in HANDOFF.md.
Linux execution and full authenticated player joins remain independent gates.

## Logout race correction (v0.3.2)

Reproduced the owner's indefinite Connecting screen by holding a server poll
across logout and delivering its 401 after the login page appeared. Late requests
can no longer expire a different session: fetch/upload requests retain the CSRF
token with which they started, expiry handling is idempotent when already signed
out, and genuine expiry runs the session guard even on the same login route.
Pending session refreshes cannot overwrite later authentication/logout results;
unmounted console views cannot reconnect from delayed callbacks. Backend auth,
CSRF enforcement and data remain unchanged. Windows TypeScript/build, all seven
browser scenarios and 102 backend tests pass. Verification is recorded in HANDOFF.

## Per-server statistics (v0.4.0)

The owner approved the statistics scope on 2026-11-14 and clarified that each
server's Statistics tab must show only its own usage. Implemented owned-process
CPU/resident-memory/uptime, per-server persisted minute history for 30 days,
resource line graphs and peak-online player bars, range menus and data tables.
Player collection is an explicit administrator/stopped-server option installing
only the bundled plugin in verified private resources. Successful joins include
repeat visits; no player identities or chat are retained. A new statistics_view
grant is independent of console access and preserves existing member grants.
Schema 4 adds only statistics tables; account hashes, existing grants and TOML
are preserved. See [STATISTICS.md](STATISTICS.md) for behavior and setup and
HANDOFF.md for verified results. Real Linux BeamMP and authenticated player joins
remain open gates; no cross-platform milestone is marked complete.

Windows verification: 125 backend tests, TypeScript/build, eight browser scenarios,
both official BeamMP v3.9.3 loopback/plugin cases, final clean-wheel install without
Node and Windows installer/update checks pass. Existing live data was not used.

## Statistics detail (v0.4.1)

The owner requested chart points roughly every ten seconds. Statistics now
defaults to Last hour with ten-second points and five-second refreshes; longer
ranges stay aggregated. Schema 5 adds bounded persisted ten-second detail (24-hour
retention) while preserving existing minute history, accounts, grants and player
plugin registrations. Minute history remains available for 30 days in longer
views; no detailed observations are fabricated for time before the update.
Tooltips/tables include seconds and interval labels use seconds for this view.
Windows verification: 128 backend tests, TypeScript/build, all eight browser
scenarios and clean-wheel installation without Node pass. Verified results and
the next task are recorded in HANDOFF.md.

## Remaining later work

General file management (historical proposal in FILE_MANAGEMENT.md); backup/restore;
host monitoring, player profiles/moderation and alerts; scheduling/BeamMP updates;
remote hosts. No automatic server restarts are enabled.
