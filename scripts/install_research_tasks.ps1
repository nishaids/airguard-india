param([switch]$Uninstall)
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskPython = Join-Path $taskRoot '.venv-live\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Isolated AirGuard Python runtime missing' }
$definitions = @(
    @{Name='AirGuard Research Prefetch'; At='19:50'; Mode='--warm'},
    @{Name='AirGuard Research Issuance'; At='20:00'; Mode='--issue'},
    @{Name='AirGuard Research Verification'; At='07:00'; Mode='--verify'}
)
# Daily Windows triggers use local time; enforce the declared India protocol.
if ((Get-TimeZone).Id -ne 'India Standard Time') { throw 'Research tasks require the local India Standard Time zone' }
foreach ($definition in $definitions) {
    if ($Uninstall) { throw 'Removal requires an explicit user request; use Task Scheduler' }
    $taskAction = New-ScheduledTaskAction -Execute $taskPython -Argument ('"' + (Join-Path $taskRoot 'run_research_pipeline.py') + '" ' + $definition.Mode) -WorkingDirectory $taskRoot
    $taskTrigger = New-ScheduledTaskTrigger -Daily -At $definition.At
    $taskPrincipal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    $taskSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $definition.Name -Action $taskAction -Trigger $taskTrigger -Principal $taskPrincipal -Settings $taskSettings -Description 'Issue-time AirGuard research; awake logged-in user only; no secret in task arguments' -Force | Select-Object TaskName,State
}
