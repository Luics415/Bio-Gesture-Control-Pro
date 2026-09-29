[CmdletBinding()]
param(
    [switch]$InstallBuildTools,
    [switch]$CheckOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$buildPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

try {
    if (-not (Test-Path -LiteralPath $buildPython -PathType Leaf)) {
        throw 'Prepara primero el entorno de desarrollo .venv del proyecto.'
    }
    if ($InstallBuildTools) {
        & $buildPython -m pip --disable-pip-version-check install --index-url https://pypi.org/simple --require-hashes --only-binary=:all: -r (Join-Path $projectRoot 'requirements-build.lock.txt')
        if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las herramientas bloqueadas de empaquetado.' }
        & $buildPython -m pip --disable-pip-version-check install --index-url https://pypi.org/simple --no-deps --require-hashes --only-binary=:all: -r (Join-Path $projectRoot 'requirements-gaze.lock.txt')
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo instalar el complemento ocular bloqueado.' }
        & $buildPython -m pip check
        if ($LASTEXITCODE -ne 0) { throw 'Las dependencias de empaquetado no son coherentes.' }
    }
    $buildArguments = @((Join-Path $PSScriptRoot 'build_portable.py'))
    if ($CheckOnly) { $buildArguments += '--check' }
    & $buildPython @buildArguments
    if ($LASTEXITCODE -ne 0) { throw 'El empaquetado o su verificación no terminó correctamente.' }
}
catch {
    Write-Error "No se pudo preparar el portable: $($_.Exception.Message)"
    exit 1
}
