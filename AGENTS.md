# BeamMPY contributor and agent guide

Read `docs/ROADMAP.md` and `docs/HANDOFF.md` before changing behavior. Update the
handoff after each work session with verified results and the next task. Mark a
milestone complete only when its acceptance checks pass.

## Architecture and conventions

- Python 3.11+, Flask application factory, SQLite, Flask-Login, Flask-SocketIO.
- Vue 3 + TypeScript + Vite + Pinia + Vue Router; M3E CSS/custom elements.
- Use M3E for every supported UI control, including menus, dialogs and navigation.
  Use its custom elements or documented CSS DOM contracts, with public tokens for
  colours and sizing. Keep application CSS for layout and terminal content;
  do not add bespoke controls that mask the library. See docs/UI.md.
- One administrator with permission-limited members and multiple local servers;
  one panel process owns all children. Enforce member grants in HTTP and Socket.IO.
- Server IDs must scope every control, console subscription, and configuration.
- Never execute console input in a shell. Do not log AuthKeys or credentials.
- Preserve existing users, password hashes, server directories, and TOML content.
- Use disposable data directories and subprocess fixtures for tests. Never run
  tests against the checkout's users.db, .env, or existing server directory.
- Do not claim Linux or real BeamMP support verified without running those checks.

## Verification

- Backend: `python -m pytest`
- Frontend: `npm --prefix frontend run check` and `npm --prefix frontend run build`
- Browser: `npm --prefix frontend run test:e2e`
- Distribution: `python -m build`, then install the wheel in a clean environment.

Release packages must include the compiled UI and run without Node. Keep runtime
data out of distributions and source control. Deferred features require a separate
specification; do not expand the first release into a hosting platform.
