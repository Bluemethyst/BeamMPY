# Explicit wheel arguments retain the original offline/manual installer.
# Keep installer settings local when downloaded through Invoke-Expression.
& {
    $ErrorActionPreference = 'Stop'
    if ($args.Count -gt 0) {
        & "$PSScriptRoot/beammpy.ps1" install @args
        exit $LASTEXITCODE
    }
    Write-Host 'BeamMPY installer' -ForegroundColor Cyan
    $pythonCommand = if ($env:BEAMMPY_PYTHON) { $env:BEAMMPY_PYTHON } elseif (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python' }
    # Keep this an array: an if-expression unwraps a single '-3' into a string,
    # and splatting that string can make py open its REPL instead of running -c.
    [string[]]$pythonArguments = @()
    if ($pythonCommand -eq 'py') { $pythonArguments = @('-3') }
    & $pythonCommand @pythonArguments -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11+ with the Python launcher or python on PATH.' }
    $work = $null
    try {
        if (Test-Path -LiteralPath "$PSScriptRoot/setup.py") {
            $sourceDirectory = Split-Path -Parent $PSScriptRoot
        } else {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Write-Host 'Downloading BeamMPY...'
            $work = Join-Path ([IO.Path]::GetTempPath()) ('beammpy-source-' + [guid]::NewGuid().ToString('N'))
            New-Item -ItemType Directory -Path $work | Out-Null
            $ProgressPreference = 'SilentlyContinue'
            Invoke-WebRequest -UseBasicParsing 'https://codeload.github.com/Bluemethyst/BeamMPY/zip/refs/heads/main' -OutFile "$work/source.zip"
            & $pythonCommand @pythonArguments -m zipfile -e "$work/source.zip" $work
            if ($LASTEXITCODE -ne 0) { throw 'Could not extract the BeamMPY download.' }
            $sourceDirectory = Join-Path $work 'BeamMPY-main'
        }
        & $pythonCommand @pythonArguments "$sourceDirectory/scripts/setup.py" windows --source $sourceDirectory
        if ($LASTEXITCODE -ne 0) { throw 'BeamMPY installation failed. Review the error above; existing data was retained.' }
    } finally {
        if ($work) {
            $resolvedWork = [IO.Path]::GetFullPath($work)
            $temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
            if ($resolvedWork.StartsWith($temporaryRoot, [StringComparison]::OrdinalIgnoreCase) -and (Split-Path -Leaf $resolvedWork) -like 'beammpy-source-*') {
                Remove-Item -LiteralPath $resolvedWork -Recurse -Force
            }
        }
    }
} @args
