$ErrorActionPreference = 'Stop'

$releaseUrl = $env:OPENCODE_PROJECT_RELEASE_URL
if ([string]::IsNullOrWhiteSpace($releaseUrl)) {
    $releaseUrl = 'https://github.com/jason23452/more-opnecode-server/releases/latest/download'
}

$installDirectory = $env:OPENCODE_PROJECT_INSTALL_DIR
if ([string]::IsNullOrWhiteSpace($installDirectory)) {
    $installDirectory = Join-Path $env:LOCALAPPDATA 'Programs\opencode-project'
}

$assetUrl = "$($releaseUrl.TrimEnd('/'))/opencode-project-windows-x64.exe"
$executablePath = Join-Path $installDirectory 'opencode-project.exe'
New-Item -ItemType Directory -Path $installDirectory -Force | Out-Null
Invoke-WebRequest -Uri $assetUrl -OutFile $executablePath

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$pathEntries = @($userPath -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
if ($pathEntries -notcontains $installDirectory) {
    $pathEntries += $installDirectory
    [Environment]::SetEnvironmentVariable('Path', ($pathEntries -join ';'), 'User')
}
if (($env:Path -split ';') -notcontains $installDirectory) {
    $env:Path = "$installDirectory;$env:Path"
}

Write-Output "Installed opencode-project to $executablePath"
