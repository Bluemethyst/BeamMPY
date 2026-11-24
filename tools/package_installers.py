"""Bundle the small offline-bootstrap scripts beside the release wheel."""
from pathlib import Path
import zipfile
from version import current_version


def main():
    root = Path(__file__).resolve().parents[1]
    version = current_version(root)
    destination = root / "dist" / f"beammpy-{version}-installers.zip"
    destination.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted((root / "scripts").iterdir()):
            if source.is_file() and source.suffix in {".py", ".ps1", ".sh"}:
                archive.write(source, source.name)
        archive.write(root / "docs" / "INSTALLATION.md", "INSTALLATION.md")
        archive.write(root / "docs" / "USAGE.md", "USAGE.md")
        archive.write(root / "docs" / "ACCOUNTS_DEPLOYMENT.md", "ACCOUNTS_DEPLOYMENT.md")
        archive.write(root / "docs" / "STATISTICS.md", "STATISTICS.md")
    print(destination.name)


if __name__ == "__main__":
    main()
