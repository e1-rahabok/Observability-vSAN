# Loads lab connection values from the git-ignored .secrets/lab.env into this PowerShell session.
# Usage (from the repo root):  . tools/env.ps1 ; python tools/conds.py
Get-Content (Join-Path $PSScriptRoot '..\.secrets\lab.env') | Where-Object { $_ -match '^\s*[^#].*=' } | ForEach-Object {
    $name, $value = $_ -split '=', 2
    Set-Item -Path "Env:$($name.Trim())" -Value $value.Trim()
}
