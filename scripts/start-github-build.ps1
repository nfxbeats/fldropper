param(
    [switch]$CheckOnly,
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    $result = & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Program $($Arguments -join ' ') failed (exit $LASTEXITCODE)."
    }
    return $result
}

Push-Location -LiteralPath $ProjectRoot
try {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw 'Install Git for Windows, then rerun build.bat.'
    }
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw 'Install GitHub CLI from https://cli.github.com and run gh auth login.'
    }
    & gh auth status *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Run gh auth login, then rerun build.bat.' }

    $versionFile = Join-Path $ProjectRoot 'fldropper/__init__.py'
    $match = [regex]::Match([IO.File]::ReadAllText($versionFile), '(?m)^__version__\s*=\s*["'']([^"'']+)["'']\s*$')
    if (-not $match.Success) { throw 'Cannot read __version__ from fldropper/__init__.py.' }
    $version = $match.Groups[1].Value
    $tag = "v$version"
    $null = Invoke-Checked git @('check-ref-format', "refs/tags/$tag")
    Write-Host "Build version: $version (tag $tag)"

    $branch = Invoke-Checked git @('symbolic-ref', '--quiet', '--short', 'HEAD')
    $dirty = Invoke-Checked git @('status', '--porcelain')
    if ($dirty) { throw 'Commit and push your changes first. GitHub Actions builds the pushed code.' }
    $repository = Invoke-Checked git @('remote', 'get-url', 'origin')
    $headCommit = Invoke-Checked git @('rev-parse', 'HEAD')
    Write-Host "Checking origin/$branch..."
    $null = Invoke-Checked git @('fetch', '--quiet', '--no-tags', 'origin', $branch)
    $remoteCommit = Invoke-Checked git @('rev-parse', 'FETCH_HEAD')
    if ($headCommit -ne $remoteCommit) {
        throw 'Local and GitHub commits differ. Synchronize your branch and push before building.'
    }

    & git show-ref --verify --quiet "refs/tags/$tag"
    $hasLocalTag = $LASTEXITCODE -eq 0
    if ($hasLocalTag) {
        $localTaggedCommit = Invoke-Checked git @('rev-parse', "refs/tags/$tag^{commit}")
        if ($localTaggedCommit -ne $headCommit) {
            throw "$tag already exists locally for different code. Increment __version__ before building a new release."
        }
    }
    $remoteTags = @(Invoke-Checked git @('ls-remote', '--tags', 'origin', "refs/tags/$tag", "refs/tags/$tag^{}"))
    $remoteTaggedCommit = $null
    $peeledCommit = $null
    foreach ($line in $remoteTags) {
        $parts = $line -split '\s+', 2
        if ($parts[1] -eq "refs/tags/$tag") { $remoteTaggedCommit = $parts[0] }
        if ($parts[1] -eq "refs/tags/$tag^{}") { $peeledCommit = $parts[0] }
    }
    if ($peeledCommit) { $remoteTaggedCommit = $peeledCommit }
    if ($remoteTaggedCommit -and $remoteTaggedCommit -ne $headCommit) {
        throw "$tag already exists on origin for different code. Increment __version__; existing release tags are never moved."
    }

    if ($CheckOnly) {
        Write-Host "Checks passed for $tag. No tag was created or pushed, and no workflow was started."
        exit 0
    }
    if ($remoteTaggedCommit) {
        Write-Host "Starting Build desktop apps on existing tag $tag..."
        $null = Invoke-Checked gh @('workflow', 'run', 'pyinstaller-build.yaml', '--repo', $repository, '--ref', $tag)
    } else {
        if (-not $hasLocalTag) {
            $null = Invoke-Checked git @('tag', '-a', $tag, '-m', "FL Dropper $version", $headCommit)
        }
        Write-Host "Pushing $tag to trigger Build desktop apps..."
        # The workflow's push.tags trigger starts the build. Do not also dispatch.
        $null = Invoke-Checked git @('push', 'origin', "refs/tags/${tag}:refs/tags/$tag")
    }
    Write-Host "Build requested for $tag. Windows and macOS ZIPs will appear in the workflow artifacts."
    & gh run list --repo $repository --workflow pyinstaller-build.yaml --branch $tag --limit 3
    if ($LASTEXITCODE -ne 0) { Write-Warning 'Build requested, but recent runs could not be listed.' }
    exit 0
} catch {
    Write-Host "Build failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    Pop-Location
}
