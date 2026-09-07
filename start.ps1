$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python311 = "C:\Users\msemi\AppData\Local\Programs\Python\Python311\python.exe"
$runDir = Join-Path $env:LOCALAPPDATA "CodexRuns\transport_system_mvp"

if (-not (Test-Path $python311)) {
    throw "Python 3.11 was not found at $python311"
}

New-Item -ItemType Directory -Force $runDir | Out-Null

Copy-Item -Path (Join-Path $projectRoot "*") -Destination $runDir -Recurse -Force

Start-Process `
    -FilePath $python311 `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $runDir

Write-Host "Transportation system started."
Write-Host "API:  http://127.0.0.1:8000"
Write-Host "Docs: http://127.0.0.1:8000/docs"
