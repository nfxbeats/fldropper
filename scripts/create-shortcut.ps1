param(
    [string]$ShortcutPath
)

$ErrorActionPreference = 'Stop'
try {
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $target = Join-Path $projectRoot 'run.bat'
    $icon = Join-Path $projectRoot 'fldropper\assets\FL_Dropper.ico'
    foreach ($file in @($target, $icon)) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
            throw "Required shortcut file is missing: $file"
        }
    }
    if (-not $ShortcutPath) {
        $desktop = [Environment]::GetFolderPath('DesktopDirectory')
        if (-not $desktop) { throw 'Windows did not return a Desktop folder.' }
        $ShortcutPath = Join-Path $desktop 'FL Dropper.lnk'
    }
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $target
    $shortcut.Arguments = ''
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.IconLocation = "$icon,0"
    $shortcut.Description = 'Open FL Dropper'
    $shortcut.WindowStyle = 1
    $shortcut.Save()
    Write-Host "Shortcut created: $ShortcutPath"
} catch {
    Write-Error "Could not create the FL Dropper shortcut: $_"
    exit 1
}
