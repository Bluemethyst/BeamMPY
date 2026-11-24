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

## Version metadata

`beammpy/version.json` is the canonical SemVer version for the Python package,
frontend footer and public update checker. It ships in the wheel/sdist. After
implementing and validating behavior changes, ask the owner to choose none,
patch, minor or major; never bump automatically. After approval, edit only the
manifest, run `python tools/version.py --sync --source-only`, rebuild the UI,
then run `python tools/version.py`. Sync updates pyproject, README, frontend
package/both lock entries and the installation guide's current wheel examples.
Use Python-compatible SemVer identifiers when publishing Python packages.

Frontend check/build run source consistency checks first. Full verification also
checks the bundled UI's generated version stamp; version changes require a UI
rebuild. CI runs the full check before and after building. Distribution tools
derive filenames from the manifest when no wheel argument is given:
`python tools/verify_distribution.py`, `python tools/verify_installers.py` and
`python tools/verify_setup.py`; explicit wheel paths remain supported.
`python tools/version.py --wheel` prints the expected wheel path. Historical
roadmap/handoff versions are records and are not rewritten by sync.

Publish the manifest and matching source/compiled UI together to public `main`.
The checker reads the anonymous raw GitHub URL documented in INSTALLATION.md;
it does not depend on Releases or authenticated Actions artifacts.

