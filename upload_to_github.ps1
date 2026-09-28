# ==================== Upload to GitHub ====================
# Usage:
#   1. Create an empty repo on GitHub (without README)
#   2. Change $GITHUB_URL below to your repo URL
#   3. Run: .\upload_to_github.ps1

$GITHUB_URL = "https://github.com/flah231/health-dashboard.git"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Upload to GitHub" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

Set-Location $PSScriptRoot

if (-not (Test-Path ".git")) {
    Write-Host ""
    Write-Host "[1/6] Init git repo..." -ForegroundColor Yellow
    git init
    git branch -M main
} else {
    Write-Host ""
    Write-Host "[1/6] Git repo exists, skip init" -ForegroundColor Green
}

if (-not (git config user.name)) {
    $name = Read-Host "Enter git user name"
    git config user.name $name
}
if (-not (git config user.email)) {
    $email = Read-Host "Enter git email"
    git config user.email $email
}

Write-Host ""
Write-Host "[2/6] Staging files..." -ForegroundColor Yellow
git add .

Write-Host ""
Write-Host "[3/6] Check ignore rules..." -ForegroundColor Yellow
$ignored = git status --ignored --short | Select-String "^!!"
Write-Host "Ignored $($ignored.Count) files/dirs"

Write-Host ""
Write-Host "[4/6] Commit..." -ForegroundColor Yellow
$msg = Read-Host "Commit message (Enter for default)"
if (-not $msg) { $msg = "chore: initial commit" }
git commit -m $msg

Write-Host ""
Write-Host "[5/6] Configure remote..." -ForegroundColor Yellow
$existing = git remote get-url origin 2>$null
if ($existing) {
    git remote set-url origin $GITHUB_URL
    Write-Host "Updated origin URL"
} else {
    git remote add origin $GITHUB_URL
    Write-Host "Added origin"
}

Write-Host ""
Write-Host "[6/6] Push to GitHub..." -ForegroundColor Yellow
git push -u origin main

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Upload complete!" -ForegroundColor Green
Write-Host "  Visit: $GITHUB_URL" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green