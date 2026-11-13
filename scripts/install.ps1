# Run with Python 3.11+ installed. Pass --wheel, --install-dir and --data-dir.
$ErrorActionPreference = 'Stop'
& $PSScriptRoot/beammpy.ps1 install @args
exit $LASTEXITCODE
