param([string]$Root = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath $Root).Path
# Update existing panels without rebuilding or replacing the application package.
$ae = Join-Path $env:APPDATA 'Adobe\CEP\extensions\com.neotrix.prism.ae'
if (Test-Path -LiteralPath $ae) {
    foreach ($name in @('main.js','index.html')) {
        Copy-Item -LiteralPath (Join-Path $Root "integrations\aftereffects\$name") -Destination (Join-Path $ae $name) -Force
    }
    Write-Output 'Updated installed After Effects comments entry point.'
}
$blender = Join-Path $env:APPDATA 'Blender Foundation\Blender\5.2\scripts\addons\neotrix_prism_blender'
if (Test-Path -LiteralPath $blender) {
    Copy-Item -LiteralPath (Join-Path $Root 'integrations\blender\neotrix_prism\__init__.py') -Destination (Join-Path $blender '__init__.py') -Force
    Write-Output 'Updated installed Blender Prism comments entry point.'
}
$fusionText = (Get-Content -LiteralPath (Join-Path $Root 'integrations\fusion\Neotrix File Comments.py') -Raw).Replace('NEOTRIXROOT', $Root)
foreach ($relative in @('Blackmagic Design\Fusion\Scripts\Comp','Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Comp')) {
    $folder = Join-Path $env:APPDATA $relative
    New-Item -ItemType Directory -Path $folder -Force | Out-Null
    [IO.File]::WriteAllText((Join-Path $folder 'Neotrix File Comments.py'), $fusionText, [Text.UTF8Encoding]::new($false))
}
Write-Output 'Installed Fusion and Resolve Fusion file-comment companion scripts.'
