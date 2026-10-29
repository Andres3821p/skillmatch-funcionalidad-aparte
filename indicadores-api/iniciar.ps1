# Arranca el servicio de indicadores en Windows con datos de DEMOSTRACION.
# Uso (desde la carpeta indicadores-api):   .\iniciar.ps1
# Para usar tu MongoDB real:  $env:MONGODB_URI = "mongodb+srv://..." ; .\iniciar.ps1 -Real
param([switch]$Real)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { $null }
if (-not $py) { Write-Host "No se encontro Python. Instalalo desde https://www.python.org/downloads/ marcando 'Add python.exe to PATH'." -ForegroundColor Red; exit 1 }

if (-not (Test-Path ".venv")) { & $py -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -q -r requirements-dev.txt

if ($Real) {
    if (-not $env:MONGODB_URI) { Write-Host 'Define primero: $env:MONGODB_URI = "mongodb+srv://..."' -ForegroundColor Red; exit 1 }
    Remove-Item Env:MODO_DEMO -ErrorAction SilentlyContinue
} else {
    $env:MODO_DEMO = "1"
}
Write-Host "Servicio en http://localhost:8000/api/indicadores/salud  (Ctrl+C para detener)" -ForegroundColor Green
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
