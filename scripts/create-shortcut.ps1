param([string]$Root = (Split-Path -Parent $PSScriptRoot), [string]$Destination = [Environment]::GetFolderPath('Desktop'))
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath $Root).Path
$target = Join-Path $Root 'Neotrix Prism.exe'
if (-not (Test-Path -LiteralPath $target)) { throw 'Extract the whole portable package before creating a shortcut.' }
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path $Destination 'Neotrix Prism.lnk'))
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = $Root
$shortcut.IconLocation = Join-Path $Root 'assets\neotrix.ico'
$shortcut.Description = 'Neotrix creative project workspace'
$shortcut.Save()
Write-Output 'Neotrix Prism shortcut created. No application integrations were changed.'
