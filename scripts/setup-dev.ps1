[CmdletBinding()]
param(
    [switch]$Dev,
    [string]$PythonExecutable
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$virtualEnvironment = Join-Path $projectRoot '.venv'
$virtualPython = Join-Path $virtualEnvironment 'Scripts\python.exe'
$lockName = if ($Dev) { 'requirements-dev.lock.txt' } else { 'requirements.lock.txt' }
$lockPath = Join-Path $projectRoot $lockName
$modelPath = Join-Path $projectRoot 'assets\models\hand_landmarker.task'
$modelReadme = Join-Path $projectRoot 'assets\models\README.md'

function Invoke-CheckedNative {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "El proceso terminó con código $LASTEXITCODE`: $Executable"
    }
}

function Test-PythonTarget {
    param([string]$Executable, [string[]]$PrefixArguments = @())
    $checkCode = "import struct, sys; assert sys.version_info[:2] == (3, 12) and struct.calcsize('P') == 8, 'Se requiere Python 3.12 de 64 bits'; print(sys.version.split()[0] + ' x64')"
    Invoke-CheckedNative -Executable $Executable -Arguments ($PrefixArguments + @('-c', $checkCode))
}

try {
    if (-not [System.Environment]::Is64BitOperatingSystem -or $env:OS -ne 'Windows_NT') {
        throw 'Este entorno de desarrollo requiere Windows de 64 bits.'
    }
    foreach ($requiredPath in @($lockPath, $modelPath, $modelReadme)) {
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw "Falta un archivo del proyecto: $requiredPath. Obtén una copia completa antes de continuar."
        }
    }
    $modelHash = (Get-FileHash -LiteralPath $modelPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $modelMetadata = Get-Content -LiteralPath $modelReadme -Raw
    $recordedHashes = @([regex]::Matches($modelMetadata, '(?i)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])') | ForEach-Object { $_.Value.ToLowerInvariant() })
    if ($recordedHashes -notcontains $modelHash) {
        throw 'La integridad del modelo no coincide con assets/models/README.md. No se instalarán dependencias.'
    }

    if (Test-Path -LiteralPath $virtualEnvironment) {
        if (-not (Test-Path -LiteralPath $virtualPython -PathType Leaf)) {
            throw 'Ya existe .venv pero no contiene Python. Consérvalo o renómbralo antes de preparar uno nuevo.'
        }
        Test-PythonTarget -Executable $virtualPython
    }
    else {
        $pythonArguments = @()
        if ($PythonExecutable) {
            $pythonCommand = (Get-Command $PythonExecutable -ErrorAction Stop).Source
        }
        else {
            $launcher = Get-Command 'py.exe' -ErrorAction SilentlyContinue
            if ($launcher) {
                $pythonCommand = $launcher.Source
                $pythonArguments = @('-3.12')
            }
            else {
                $pythonCommand = (Get-Command 'python.exe' -ErrorAction Stop).Source
            }
        }
        Test-PythonTarget -Executable $pythonCommand -PrefixArguments $pythonArguments
        Invoke-CheckedNative -Executable $pythonCommand -Arguments ($pythonArguments + @('-m', 'venv', $virtualEnvironment))
        Test-PythonTarget -Executable $virtualPython
    }

    Invoke-CheckedNative -Executable $virtualPython -Arguments @('-m', 'pip', '--disable-pip-version-check', 'install', '--require-hashes', '--only-binary=:all:', '-r', $lockPath)
    Invoke-CheckedNative -Executable $virtualPython -Arguments @('-m', 'pip', 'check')
    Invoke-CheckedNative -Executable $virtualPython -Arguments @((Join-Path $PSScriptRoot 'diagnose.py'))
    Write-Host "Entorno preparado en $virtualEnvironment" -ForegroundColor Green
    Write-Host 'Puedes iniciar el programa con INICIAR_CONTROL.vbs; inicia pausado para calibrarlo.'
    Write-Host 'El antiguo directorio venv se ha conservado sin utilizarlo.'
}
catch {
    Write-Error "No se pudo preparar el entorno: $($_.Exception.Message)"
    exit 1
}
