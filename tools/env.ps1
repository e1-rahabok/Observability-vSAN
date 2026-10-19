# Loads lab connection values from a git-ignored .secrets/<name>.env into this PowerShell session.
# Usage (from the repo root):  . tools/env.ps1           # .secrets/lab.env  (lab without vSAN)
#                              . tools/env.ps1 live      # .secrets/live.env (vCenter with vSAN clusters)
param([string]$Name = 'lab')
Get-Content (Join-Path $PSScriptRoot "..\.secrets\$Name.env") | Where-Object { $_ -match '^\s*[^#].*=' } | ForEach-Object {
    $name, $value = $_ -split '=', 2
    Set-Item -Path "Env:$($name.Trim())" -Value $value.Trim()
}
