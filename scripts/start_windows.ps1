<#
.SYNOPSIS
    Build (if needed) and run the FinAlly container. Idempotent: safe to re-run.
.PARAMETER Build
    Force a rebuild of the image even if it already exists.
#>
param(
    [switch]$Build
)

$ErrorActionPreference = 'Stop'

$ImageName = "finally"
$ContainerName = "finally"
$Port = 8000
$VolumeName = "finally-data"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Error "Docker is not installed. Install Docker Desktop from https://docker.com/products/docker-desktop and try again."
    exit 1
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker is installed but not running. Start Docker Desktop and try again."
    exit 1
}

docker image inspect $ImageName *> $null
$imageExists = ($LASTEXITCODE -eq 0)

if ($Build -or -not $imageExists) {
    Write-Host "Building $ImageName image..."
    docker build -t $ImageName .
    if ($LASTEXITCODE -ne 0) { Write-Error "Docker build failed."; exit 1 }
} else {
    Write-Host "Image $ImageName already exists (use -Build to force a rebuild)."
}

$existing = docker ps -a --format '{{.Names}}' | Where-Object { $_ -eq $ContainerName }
if ($existing) {
    Write-Host "Removing existing $ContainerName container..."
    docker rm -f $ContainerName *> $null
}

$envFilePath = Join-Path $ProjectRoot ".env"
$runArgs = @(
    "run", "-d",
    "--name", $ContainerName,
    "-p", "${Port}:8000",
    "-v", "${VolumeName}:/app/db"
)

if (Test-Path $envFilePath) {
    $runArgs += @("--env-file", $envFilePath)
} else {
    Write-Host "Note: no .env file found. The app will run with the built-in market simulator."
    Write-Host "      Chat needs LLM_MOCK=true or an OPENROUTER_API_KEY -- copy .env.example to .env to set these."
}

$runArgs += $ImageName

Write-Host "Starting $ContainerName container..."
docker @runArgs *> $null
if (-not $?) { Write-Error "Failed to start container."; exit 1 }

Write-Host "Waiting for FinAlly to become healthy..."
$timeoutSeconds = 60
$elapsed = 0
$healthy = $false
while ($elapsed -lt $timeoutSeconds) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$Port/api/health" -UseBasicParsing -TimeoutSec 3
        if ($response.StatusCode -eq 200) {
            $healthy = $true
            break
        }
    } catch {
        # Not ready yet; keep polling.
    }
    Start-Sleep -Seconds 1
    $elapsed += 1
}

if (-not $healthy) {
    Write-Error "FinAlly did not become healthy within $timeoutSeconds seconds. Check logs with: docker logs $ContainerName"
    exit 1
}

$url = "http://localhost:$Port"
Write-Host "FinAlly is running at $url"

try {
    Start-Process $url
} catch {
    # Best-effort browser launch; not fatal if it fails.
}
