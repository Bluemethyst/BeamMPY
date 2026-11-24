"""Synchronize/check release metadata against beammpy/version.json.

Edit the manifest only after version approval, then run --sync and rebuild the UI.
Default verification includes the build's version stamp; --source-only is for
prebuild checks. Historical handoff/roadmap version records are deliberately kept.
"""
import argparse
import json
from pathlib import Path
import re
import runpy
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def current_version(root=ROOT):
    # Load the dependency-free parser without importing the Flask application.
    parser = runpy.run_path(str(ROOT / 'beammpy/versioning.py'))['manifest_version']
    return parser((root / 'beammpy/version.json').read_bytes())


def release_wheel(root=ROOT):
    from packaging.version import Version
    return root / 'dist' / f'beammpy-{Version(current_version(root))}-py3-none-any.whl'


def verify(root=ROOT, *, sync=False, source_only=False):
    version = current_version(root)
    errors = []

    def text_file(name, pattern, replacement):
        path = root / name
        text = path.read_text(encoding='utf-8')
        if len(re.findall(pattern, text)) == 0:
            errors.append(f'{name}: missing version reference')
            return
        expected = re.sub(pattern, lambda _: replacement, text)
        if text != expected:
            if sync:
                path.write_text(expected, encoding='utf-8', newline='\n')
            else:
                errors.append(f'{name}: version differs from manifest ({version})')

    text_file('pyproject.toml', r'(?m)^version = "[^"]+"$', f'version = "{version}"')
    text_file('README.md', r'Current version: \*\*[^*]+\*\*\.', f'Current version: **{version}**.')
    text_file('docs/INSTALLATION.md', r'beammpy-[0-9][0-9A-Za-z.+-]*-py3-none-any\.whl', f'beammpy-{version}-py3-none-any.whl')
    for name in ('frontend/package.json', 'frontend/package-lock.json'):
        path = root / name
        data = json.loads(path.read_text(encoding='utf-8'))
        entries = [data] + ([data['packages']['']] if 'packages' in data else [])
        if any(entry['version'] != version for entry in entries):
            if sync:
                for entry in entries:
                    entry['version'] = version
                path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8', newline='\n')
            else:
                errors.append(f'{name}: version differs from manifest ({version})')
    project = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))
    if 'version.json' not in project['tool']['setuptools']['package-data']['beammpy']:
        errors.append('The distribution must include the canonical manifest')
    app = (root / 'frontend/src/App.vue').read_text(encoding='utf-8')
    if "import { version } from '../../beammpy/version.json'" not in app or 'v{{ version }}' not in app:
        errors.append('The footer must derive its version from the canonical manifest')
    workflow = (root / '.github/workflows/checks.yml').read_text(encoding='utf-8')
    if re.search(r'beammpy-\d[^\s]*\.whl', workflow):
        errors.append('CI must derive wheel paths from the canonical manifest')
    if not source_only:
        stamp = root / 'beammpy/web/version.json'
        if not stamp.is_file() or json.loads(stamp.read_text(encoding='utf-8')) != {'version': version}:
            errors.append('Bundled UI version is stale or missing: rebuild frontend')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sync', action='store_true', help='Synchronize metadata to the already approved manifest version')
    parser.add_argument('--source-only', action='store_true')
    parser.add_argument('--wheel', action='store_true', help='Print the canonical release wheel path')
    args = parser.parse_args()
    if args.wheel:
        print(release_wheel())
        return
    errors = verify(sync=args.sync, source_only=args.source_only)
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'Version metadata agrees with manifest: {current_version()}')


if __name__ == '__main__':
    main()
