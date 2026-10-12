param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$BlenderVersion = '5.2',
    [switch]$SkipPhotoshop,
    [switch]$SkipAfterEffects,
    [switch]$SkipBlender
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath $Root).Path
$packages = Join-Path $Root 'integration-packages'
if (-not (Test-Path -LiteralPath $packages)) { throw 'Build the integration packages first.' }
$results = @()
if (-not $SkipBlender) {
    $target = Join-Path $env:APPDATA "Blender Foundation\Blender\$BlenderVersion\scripts\addons\neotrix_prism_blender"
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    Copy-Item -Path (Join-Path $packages 'neotrix_prism_blender\*') -Destination $target -Recurse -Force
    [IO.File]::WriteAllText((Join-Path $target 'installation.json'), (@{root=$Root} | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
    $results += 'Blender: installed separately. Enable Neotrix Prism in Blender Preferences > Add-ons.'
}
if (-not $SkipAfterEffects) {
    $target = Join-Path $env:APPDATA 'Adobe\CEP\extensions\com.neotrix.prism.ae'
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    Copy-Item -Path (Join-Path $packages 'aftereffects\*') -Destination $target -Recurse -Force
    [IO.File]::WriteAllText((Join-Path $target 'installation.json'), (@{root=$Root} | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
    # This independently authored CEP extension is unsigned; enable local extensions.
    foreach ($version in @('11','12')) {
        $key = "HKCU:\Software\Adobe\CSXS.$version"
        New-Item -Path $key -Force | Out-Null
        New-ItemProperty -Path $key -Name 'PlayerDebugMode' -Value '1' -PropertyType String -Force | Out-Null
    }
    $results += 'After Effects: installed separately. Restart AE and open Window > Extensions > Neotrix Prism.'
}
if (-not $SkipPhotoshop) {
    $fallback = Join-Path $packages 'photoshop\Neotrix Prism.jsx'
    $fallbackText = (Get-Content -LiteralPath $fallback -Raw).Replace('NEOTRIXROOT', $Root.Replace('\','/'))
    [IO.File]::WriteAllText($fallback, $fallbackText, [Text.UTF8Encoding]::new($false))
    $psFolders = Get-ChildItem -LiteralPath 'C:\Program Files\Adobe' -Directory -Filter 'Adobe Photoshop*' -ErrorAction SilentlyContinue
    foreach ($psFolder in $psFolders) {
        $scriptsFolder = Join-Path $psFolder.FullName 'Presets\Scripts'
        if (Test-Path -LiteralPath $scriptsFolder) {
            try {
                [IO.File]::WriteAllText((Join-Path $scriptsFolder 'Neotrix Prism.jsx'), $fallbackText, [Text.UTF8Encoding]::new($false))
                $results += 'Photoshop companion: File > Scripts > Neotrix Prism after restart.'
            } catch {
                $results += 'Photoshop companion: use File > Scripts > Browse and select integration-packages\photoshop\Neotrix Prism.jsx.'
            }
        }
    }
    $upi = 'C:\Program Files\Common Files\Adobe\Adobe Desktop Common\RemoteComponents\UPI\UnifiedPluginInstallerAgent.exe'
    if (-not (Test-Path -LiteralPath $upi)) {
        $upi = 'C:\Program Files\Common Files\Adobe\Adobe Desktop Common\RemoteComponents\UPI\UnifiedPluginInstallerAgent\UnifiedPluginInstallerAgent.exe'
    }
    if (Test-Path -LiteralPath $upi) {
        $plugin = Join-Path $packages 'NeotrixPrismPhotoshop.ccx'
        $process = Start-Process -FilePath $upi -ArgumentList @('/install', ('"' + $plugin + '"')) -WindowStyle Hidden -Wait -PassThru
        if ($process.ExitCode -ne 0) {
            $results += "Photoshop: UPI returned $($process.ExitCode). Load integration-packages\photoshop\manifest.json with Adobe UXP Developer Tool."
        } else {
            $results += 'Photoshop: installed separately. Restart Photoshop and open Plugins > Neotrix Prism.'
        }
    } else {
        $results += 'Photoshop: Creative Cloud UPI was not found. Install the CCX using Creative Cloud or load the manifest with UXP Developer Tool.'
    }
}
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Neotrix Prism.lnk'))
$shortcut.TargetPath = Join-Path $Root 'runtime\pythonw.exe'
$shortcut.Arguments = '"' + (Join-Path $Root 'launch.py') + '"'
$shortcut.WorkingDirectory = $Root
$shortcut.Description = 'Neotrix creative project workspace'
$shortcut.IconLocation = Join-Path $Root 'assets\neotrix.ico'
$shortcut.Save()
$results += 'Neotrix Prism desktop shortcut created.'
$results
$results | Set-Content -LiteralPath (Join-Path $Root 'integration-install.log')
