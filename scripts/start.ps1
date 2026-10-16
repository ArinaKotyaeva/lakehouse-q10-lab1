$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
docker compose up -d postgres minio lakekeeper trino
if ($LASTEXITCODE -ne 0) { throw 'Docker startup failed' }
python scripts/setup.py
if ($LASTEXITCODE -ne 0) { throw 'Warehouse initialization failed' }
