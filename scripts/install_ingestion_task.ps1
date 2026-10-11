param([string]$PythonExe = (Get-Command python).Source)
$ErrorActionPreference = 'Stop'
$TaskName = 'AirGuard 2.0 Live Ingestion'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$IsolatedRuntime = Join-Path $ProjectRoot '.venv-live\Scripts\python.exe'
if (-not $PSBoundParameters.ContainsKey('PythonExe') -and (Test-Path -LiteralPath $IsolatedRuntime)) {
    $PythonExe = $IsolatedRuntime
}
$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument '-m src.ingestion.scheduled' -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddHours(1) -RepetitionInterval (New-TimeSpan -Hours 1)
$Principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 50) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$Existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Existing) {
    $OldAction = $Existing.Actions | Select-Object -First 1
    if ($OldAction.WorkingDirectory -ne $ProjectRoot -or $OldAction.Arguments -ne '-m src.ingestion.scheduled') {
        throw 'An unrelated task uses this name; refusing to replace it.'
    }
}
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description 'Fetch and validate CPCB, OpenAQ, NASA FIRMS and Open-Meteo into Supabase hourly. Credentials loaded from local .env.' -Force | Select-Object TaskName, State
Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object NextRunTime, LastRunTime, LastTaskResult
