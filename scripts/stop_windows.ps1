<#
.SYNOPSIS
    Stop and remove the FinAlly container. The finally-data volume is left intact,
    so portfolio/watchlist/chat history persists across restarts. Safe to re-run.
#>
$ErrorActionPreference = 'Stop'

$ContainerName = "finally"
$VolumeName = "finally-data"

$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Error "Docker is not installed."
    exit 1
}

$existing = docker ps -a --format '{{.Names}}' | Where-Object { $_ -eq $ContainerName }
if ($existing) {
    Write-Host "Stopping and removing $ContainerName container..."
    docker rm -f $ContainerName *> $null
    Write-Host "Container stopped."
} else {
    Write-Host "No $ContainerName container is running."
}

Write-Host "Data volume '$VolumeName' left intact. To delete it permanently: docker volume rm $VolumeName"
