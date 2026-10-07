# Redeploy from your Windows laptop (PowerShell 7+ or Windows PowerShell 5.1):
#   .\deploy\deploy.ps1
# ssh in -> git pull -> build images on the server -> compose up -d -> health check,
# then checks https://$Domain/health from here (DNS + NSG + TLS from the outside).
# Push your commits to GitHub first - the server pulls from origin, not from this laptop.
param(
    [string]$Domain  = 'personacr.northcentralus.cloudapp.azure.com',
    [string]$SshKey  = (Join-Path $HOME '.ssh\azure_personacr'),
    [string]$SshUser = 'azureuser',
    [string]$AppDir  = '~/PersonaCR',
    [string]$Branch  = 'main'
)

$ErrorActionPreference = 'Stop'
$sshHost = "$SshUser@$Domain"

Write-Host "==> Deploying origin/$Branch to $sshHost" -ForegroundColor Cyan
$remote = "set -e; cd $AppDir && git fetch --quiet origin && git checkout --quiet $Branch && git pull --ff-only origin $Branch && bash deploy/server-deploy.sh"
ssh -i $SshKey -o ServerAliveInterval=30 $sshHost $remote
if ($LASTEXITCODE -ne 0) {
    Write-Error "Remote deploy failed (exit $LASTEXITCODE) - see the output above."
    exit $LASTEXITCODE
}

Write-Host '==> External health check' -ForegroundColor Cyan
for ($i = 1; $i -le 12; $i++) {
    try {
        $health = Invoke-RestMethod -Uri "https://$Domain/health" -TimeoutSec 10
        Write-Host ($health | ConvertTo-Json -Compress)
        Write-Host "==> Live: https://$Domain" -ForegroundColor Green
        exit 0
    } catch {
        Start-Sleep -Seconds 5
    }
}
Write-Error "https://$Domain/health is not reachable from here. Check the Azure NSG allows 80/443."
exit 1
