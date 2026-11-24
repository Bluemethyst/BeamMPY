# Development and verification

Run these commands from the repository root. Python 3.11+ is required.
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
See [UI conventions](UI.md) before adding screens or controls.

Run `python -m pytest`, `npm --prefix frontend run check`, and
`npm --prefix frontend run build`. For browser tests install Playwright Chromium
with `npm --prefix frontend exec -- playwright install chromium`, then run
`npm --prefix frontend run test:e2e`. Tests use temporary data and fixture processes.

For frontend hot reload run `beammpy serve` and, in another terminal,
`npm --prefix frontend run dev`. Vite proxies API and Socket.IO calls to Flask.
Build wheels with `python -m build` after building the UI. Do not include runtime
data in wheels. See [verification status](HANDOFF.md) for outstanding real BeamMP/platform checks.

