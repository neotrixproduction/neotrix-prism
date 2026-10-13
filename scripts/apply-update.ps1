param([Parameter(Mandatory=$true)][string]$Job)
$ErrorActionPreference = 'Stop'
$jobData = Get-Content -LiteralPath $Job -Raw -Encoding UTF8 | ConvertFrom-Json
$rootPath = [IO.Path]::GetFullPath($jobData.root).TrimEnd('\')
$stagePath = [IO.Path]::GetFullPath($jobData.stage).TrimEnd('\')
$payloadPath = [IO.Path]::GetFullPath($jobData.payload).TrimEnd('\')
$backupPath = [IO.Path]::GetFullPath($jobData.backup).TrimEnd('\')
$parentPath = Split-Path -Parent $rootPath
function Report($state, $message) {
    @{state=$state;message=$message;version=$jobData.version;backup=$backupPath} |
        ConvertTo-Json | Set-Content -LiteralPath $jobData.status -Encoding utf8
}
function Restart-App {
    if ($jobData.restart) {
        Start-Process -FilePath (Join-Path $rootPath 'Neotrix Prism.exe') -WorkingDirectory $rootPath -WindowStyle Hidden
    }
}
$movedOld = $false
$movedNew = $false
$lockStream = $null
try {
    # Validate every resolved target before any directory move or cleanup.
    if ((Split-Path -Parent $stagePath) -ne $parentPath -or
        (Split-Path -Leaf $stagePath) -notlike '.neotrix-update-*' -or
        -not $payloadPath.StartsWith($stagePath + '\', [StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path -Parent $backupPath) -ne $parentPath -or
        (Split-Path -Leaf $backupPath) -notlike ((Split-Path -Leaf $rootPath)+'.previous-*') -or
        (Test-Path -LiteralPath $backupPath)) { throw 'Invalid update paths.' }
    foreach ($target in @($rootPath,$stagePath,$payloadPath)) {
        if ((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked installations are not supported.' }
    }
    $manifest=Get-Content -LiteralPath (Join-Path $payloadPath 'portable.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.product -ne 'Neotrix.Prism' -or $manifest.version -ne $jobData.version) { throw 'Invalid update manifest.' }
    $installed=Get-Content -LiteralPath (Join-Path $rootPath 'portable.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($installed.product -ne 'Neotrix.Prism' -or (Test-Path -LiteralPath (Join-Path $rootPath '.git'))) { throw 'This is not an updateable portable installation.' }
    $lockPath=Join-Path $parentPath ((Split-Path -Leaf $rootPath)+'.update.lock')
    $lockStream=[IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    Report 'waiting' 'Waiting for Neotrix Prism to close.'
    $deadline=(Get-Date).AddSeconds(120)
    foreach ($processId in $jobData.wait_pids) {
        while (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
            if ((Get-Date) -gt $deadline) { throw 'The app did not close. Update cancelled.' }
            Start-Sleep -Milliseconds 250
        }
    }
    $otherInstances=@(Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe' OR Name='Neotrix Prism.exe'" |
        Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($rootPath+'\',[StringComparison]::OrdinalIgnoreCase) })
    if ($otherInstances.Count) { throw 'Another Neotrix instance or runtime process is using this installation. Close it and retry the update.' }
    Move-Item -LiteralPath $rootPath -Destination $backupPath
    $movedOld=$true
    Move-Item -LiteralPath $payloadPath -Destination $rootPath
    $movedNew=$true
    $check=Start-Process -FilePath (Join-Path $rootPath 'Neotrix Prism.exe') -ArgumentList '--self-test' -WorkingDirectory $rootPath -WindowStyle Hidden -PassThru
    if (-not $check.WaitForExit(60000)) {
        # Only the updater's own isolated runtime check is stopped on timeout.
        & taskkill.exe /PID $check.Id /T /F | Out-Null
        throw 'The new runtime check timed out. Restoring the previous version.'
    }
    $check.Refresh()
    if ($check.ExitCode -ne 0) { throw 'The new app failed its runtime check. Restoring the previous version.' }
    Report 'complete' 'Update installed. The previous version is retained for rollback.'
} catch {
    $reason=$_.Exception.Message
    if ($movedNew) {
        try { Move-Item -LiteralPath $rootPath -Destination $payloadPath; $movedNew=$false } catch {}
    }
    if ($movedOld -and -not (Test-Path -LiteralPath $rootPath)) {
        try { Move-Item -LiteralPath $backupPath -Destination $rootPath; $movedOld=$false } catch { $reason+=' Rollback needs attention: '+$_.Exception.Message }
    }
    Report 'failed' $reason
} finally {
    if ($lockStream) { $lockStream.Dispose() }
}
if (Test-Path -LiteralPath (Join-Path $rootPath 'Neotrix Prism.exe')) {
    try { Restart-App } catch { Report 'failed' ('App installed; could not restart: '+$_.Exception.Message) }
}
# Cleanup is optional after commit, and cannot trigger rollback of a running app.
if ($movedNew) { try { Remove-Item -LiteralPath $stagePath -Recurse -Force } catch {} }
