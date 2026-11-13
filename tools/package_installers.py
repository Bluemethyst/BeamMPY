"""Bundle the small offline-bootstrap scripts beside the release wheel."""
from pathlib import Path
import tomllib
import zipfile


def main():
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    destination = root / "dist" / f"beammpy-{version}-installers.zip"
    destination.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted((root / "scripts").iterdir()):
            if source.is_file() and source.suffix in {".py", ".ps1", ".sh"}:
                archive.write(source, source.name)
        archive.write(root / "docs" / "INSTALLATION.md", "INSTALLATION.md")
        archive.write(root / "docs" / "ACCOUNTS_DEPLOYMENT.md", "ACCOUNTS_DEPLOYMENT.md")
        archive.write(root / "docs" / "STATISTICS.md", "STATISTICS.md")
    print(destination.name)


if __name__ == "__main__":
    main()
