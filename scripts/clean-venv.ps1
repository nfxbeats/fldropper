param([Parameter(Mandatory = $true)][string]$ProjectRoot)
$ErrorActionPreference = 'Stop'
try {
    $project = (Resolve-Path -LiteralPath $ProjectRoot).ProviderPath
    $target = [IO.Path]::GetFullPath((Join-Path $project '.venv'))
    if ([IO.Path]::GetDirectoryName($target) -ne $project.TrimEnd('\') -or [IO.Path]::GetFileName($target) -ne '.venv') {
        throw 'Refusing cleanup outside the project .venv.'
    }
    if (-not (Test-Path -LiteralPath $target)) { exit 0 }
    $item = Get-Item -LiteralPath $target -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'The .venv is a link or junction. Remove the link manually before rerunning setup.'
    }
    if ($item.PSIsContainer) {
        # Do not traverse or delete through links in a damaged environment.
        $pending = New-Object 'System.Collections.Generic.Stack[string]'
        $pending.Push($target)
        while ($pending.Count -gt 0) {
            foreach ($child in Get-ChildItem -LiteralPath $pending.Pop() -Force) {
                if ($child.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                    throw 'The .venv contains a link or junction. Move it aside manually before rerunning setup.'
                }
                if ($child.PSIsContainer) { $pending.Push($child.FullName) }
            }
        }
    }
    Write-Host "Removing unusable environment: $target"
    Remove-Item -LiteralPath $target -Recurse -Force
} catch {
    Write-Host "Could not clean .venv: $($_.Exception.Message)"
    Write-Host 'Close FL Dropper and any programs using .venv, then retry.'
    exit 1
}
