# Stop the panel first; use the same --install-dir as installation.
$ErrorActionPreference = 'Stop'
& $PSScriptRoot/beammpy.ps1 update @args
exit $LASTEXITCODE
