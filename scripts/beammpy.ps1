$ErrorActionPreference = 'Stop'
if ($env:BEAMMPY_PYTHON) {
    & $env:BEAMMPY_PYTHON "$PSScriptRoot/manage.py" @args
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 "$PSScriptRoot/manage.py" @args
} else {
    & python "$PSScriptRoot/manage.py" @args
}
exit $LASTEXITCODE
