# BeamMPY roadmap

Agreed 2026-11-13: free, self-hosted Python/Flask panel with Vue 3, TypeScript,
Vite, Pinia, Vue Router, and locally bundled M3E. One administrator manages
multiple local BeamMP instances on Windows and supported Linux distributions.
Release users need Python, not Node. Planned panel shutdown stops owned servers.
Project license: MIT (confirmed by the owner during implementation).

## Current delivery status

| Milestone | Status |
| --- | --- |
| 1. Foundations | Complete; migration, preservation, isolation and locking verified |
| 2. Vue migration | Complete; TypeScript, production build and browser scenarios verified |
| 3. Reliable management | Implemented; fixture integration and real Windows BeamMP verified; Linux execution pending |
| 4. Release readiness | Wheel/sdist built; clean install without Node verified; Linux release gate pending |

Do not call this a cross-platform release until the Linux workflow and real
BeamMP smoke check pass on a supported Linux host. The workflow is configured for
Windows and Ubuntu 24.04 with Python 3.11/3.13; it has not been run remotely.

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

## Remaining later work

General file management; backup/restore; monitoring/player tools; scheduling/updates;
additional users/permissions; remote hosts. No automatic server restarts are enabled.
