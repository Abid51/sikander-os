# Sikander OS — GitHub repo pe publish karna (404 fix)
# Pehli baar: browser se GitHub login; phir repo banegi aur code push ho jayega.

$ErrorActionPreference = "Stop"

$Gh = Join-Path ${env:ProgramFiles} "GitHub CLI\gh.exe"
if (-not (Test-Path $Gh)) {
    Write-Host "GitHub CLI nahi mila. Install karo:" -ForegroundColor Red
    Write-Host "  winget install GitHub.cli" -ForegroundColor Yellow
    exit 1
}

Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "`nChecking GitHub login..." -ForegroundColor Cyan
& $Gh auth status 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nAbhi logged in nahin ho. NEXT command khud run karo (browser khulega):" -ForegroundColor Yellow
    Write-Host "  & `"$Gh`" auth login" -ForegroundColor White
    Write-Host "`nLogin ke baad dubara ye script run karo:`n  .\scripts\github-pehla-push.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host "`nRepo 'sikander-os' GitHub par bana rahe + push kar rahe (Abid51)..." -ForegroundColor Cyan
# --source=. = isi folder se; --remote=origin = jo remote tumne pehle set kiya; --push = sab commits bhejo
& $Gh repo create sikander-os --public --source=. --remote=origin --push

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nHo gaya! URL: https://github.com/Abid51/sikander-os" -ForegroundColor Green
} else {
    Write-Host "`nDekho error upar." -ForegroundColor Red
    Write-Host "- Agar repo pehle se exist karti ho to sirf ye chala do:" -ForegroundColor Yellow
    Write-Host '  git push -u origin main' -ForegroundColor White
}
