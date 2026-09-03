$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$DistRoot = Join-Path $PSScriptRoot "dist"
$BuildRoot = Join-Path $PSScriptRoot "build"
$SpecRoot = Join-Path $PSScriptRoot "spec"
$FlaUInspect = Join-Path $ProjectRoot "tools\FlaUInspect"
$FlaUIBridge = Join-Path $ProjectRoot "tools\FlaUIBridge\publish"
$WebExtension = Join-Path $ProjectRoot "web-extension"
$BrandAssets = Join-Path $ProjectRoot "assets"
$AppIcon = Join-Path $BrandAssets "softauto.ico"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Project Python was not found: $Python"
}
if (-not (Test-Path -LiteralPath (Join-Path $FlaUInspect "FlaUInspect.exe") -PathType Leaf)) {
    throw "FlaUInspect bundle was not found: $FlaUInspect"
}
if (-not (Test-Path -LiteralPath (Join-Path $FlaUIBridge "FlaUIBridge.exe") -PathType Leaf)) {
    throw "FlaUI bridge bundle was not found: $FlaUIBridge"
}
if (-not (Test-Path -LiteralPath (Join-Path $WebExtension "manifest.json") -PathType Leaf)) {
    throw "Chrome extension bundle was not found: $WebExtension"
}
if (-not (Test-Path -LiteralPath $AppIcon -PathType Leaf)) {
    throw "Application icon was not found: $AppIcon"
}

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name SoftAuto `
    --icon $AppIcon `
    --paths (Join-Path $ProjectRoot "src") `
    --distpath $DistRoot `
    --workpath (Join-Path $BuildRoot "gui") `
    --specpath $SpecRoot `
    --add-data "$FlaUInspect;tools\FlaUInspect" `
    --add-data "$FlaUIBridge;tools\FlaUIBridge" `
    --add-data "$WebExtension;web-extension" `
    --add-data "$BrandAssets;assets" `
    --collect-all uiautomation `
    --collect-all comtypes `
    --collect-all pynput `
    (Join-Path $PSScriptRoot "gui_entry.py")

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --console `
    --name SoftAutoMCP `
    --icon $AppIcon `
    --paths (Join-Path $ProjectRoot "src") `
    --distpath $DistRoot `
    --workpath (Join-Path $BuildRoot "mcp") `
    --specpath $SpecRoot `
    --collect-all mcp `
    --collect-all uiautomation `
    --collect-all comtypes `
    (Join-Path $PSScriptRoot "mcp_entry.py")

$IsccCandidates = @(
    (Join-Path ${env:LOCALAPPDATA} "Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
)
$Iscc = $IsccCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $Iscc) {
    throw "Inno Setup 6 compiler was not found. Install JRSoftware.InnoSetup first."
}

& $Iscc (Join-Path $PSScriptRoot "SoftAuto.iss")

$BuiltInstaller = Join-Path $PSScriptRoot "installer-dist\Lingheyi-SoftAuto-Setup-0.5.6.exe"
$Deliverable = Join-Path (Split-Path $ProjectRoot -Parent) "Lingheyi-SoftAuto-Setup-0.5.6.exe"
Copy-Item -LiteralPath $BuiltInstaller -Destination $Deliverable -Force
Get-Item -LiteralPath $Deliverable
