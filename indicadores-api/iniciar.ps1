# Arranca el servicio de indicadores en Windows y abre la pagina en http://localhost:8000
#
# Uso (desde la carpeta indicadores-api):
#   .\iniciar.ps1           datos EN VIVO de la API publica de SkillMatch (necesita internet)
#   .\iniciar.ps1 -Demo     datos de demostracion inventados (sin internet)
#   .\iniciar.ps1 -Mongo    tu MongoDB: antes define  $env:MONGODB_URI = "mongodb+srv://..."
param([switch]$Demo, [switch]$Mongo)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { $null }
if (-not $py) { Write-Host "No se encontro Python. Instalalo desde https://www.python.org/downloads/ marcando 'Add python.exe to PATH'." -ForegroundColor Red; exit 1 }

if (-not (Test-Path ".venv")) {
    Write-Host "Creando el entorno de Python (solo la primera vez)..." -ForegroundColor Cyan
    & $py -m venv .venv
}
Write-Host "Instalando lo necesario (la primera vez tarda unos minutos)..." -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pip install -q --disable-pip-version-check -r requirements-dev.txt

Remove-Item Env:MODO_DEMO -ErrorAction SilentlyContinue
Remove-Item Env:FUENTE -ErrorAction SilentlyContinue
if ($Demo) {
    $env:FUENTE = "demo"
} elseif ($Mongo) {
    if (-not $env:MONGODB_URI) { Write-Host 'Define primero: $env:MONGODB_URI = "mongodb+srv://..."' -ForegroundColor Red; exit 1 }
    $env:FUENTE = "mongo"
} else {
    $env:FUENTE = "api"
}
Write-Host ""
Write-Host "Fuente de datos: $($env:FUENTE)" -ForegroundColor Green
Write-Host "Abre en tu navegador:  http://localhost:8000      (Ctrl+C para detener)" -ForegroundColor Green
Write-Host ""
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
