[CmdletBinding()]
param(
    [ValidateRange(1, 90)][int]$Days = 14,
    [ValidateRange(1, 2000)][int]$MaxEvents = 200
)

# Local evidence only. No elevation, external tools, repairs, uploads or GUI.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$script:sections = [ordered]@{}
$script:since = (Get-Date).AddDays(-$Days)

function Get-Key([string]$Value) {
    if (-not $Value) { return $null }
    $hash = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $hash.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Value.ToUpperInvariant()))
        return (([BitConverter]::ToString($bytes) -replace '-', '').Substring(0, 16).ToLowerInvariant())
    } finally { $hash.Dispose() }
}

function Safe-Text([object]$Value) {
    $text = [string]$Value
    if ($env:USERPROFILE) { $text = $text.Replace($env:USERPROFILE, '<user>') }
    if ($env:USERNAME -and $env:USERNAME.Length -gt 2) {
        $text = [regex]::Replace($text, '(?i)(?<![A-Za-z0-9])' + [regex]::Escape($env:USERNAME) + '(?![A-Za-z0-9])', '<user>')
    }
    if ($env:COMPUTERNAME) { $text = $text.Replace($env:COMPUTERNAME, '<computer>') }
    return $text
}

function Invoke-Section([string]$Name, [scriptblock]$Query) {
    try {
        $items = @(& $Query)
        $script:sections[$Name] = [ordered]@{ status = 'ok'; reason = ''; data = $items }
    } catch {
        $script:sections[$Name] = [ordered]@{
            status = 'not_verified'; reason = (Safe-Text $_.Exception.Message); data = @()
        }
    }
}

function Event-Data($Event) {
    [xml]$xml = $Event.ToXml()
    $values = @{}
    foreach ($item in @($xml.Event.EventData.Data)) {
        if ($null -ne $item -and $item.Name) { $values[[string]$item.Name] = [string]$item.'#text' }
    }
    # Some Diagnostics-Performance builds use a named UserData element.
    foreach ($node in @($xml.SelectNodes('//*[local-name()="UserData"]/*/*'))) {
        if ($null -ne $node -and -not $values.ContainsKey($node.LocalName)) {
            $values[$node.LocalName] = [string]$node.InnerText
        }
    }
    return $values
}

function Get-Events($Filter, [int]$Limit) {
    try { return @(Get-WinEvent -FilterHashtable $Filter -MaxEvents $Limit -ErrorAction Stop) }
    catch {
        if ($_.FullyQualifiedErrorId -match 'NoMatchingEventsFound') { return @() }
        throw
    }
}

function Number-OrNull($Value) {
    if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) { return $null }
    $number = 0L
    if ([long]::TryParse([string]$Value, [ref]$number)) { return $number }
    return $null
}

function Convert-Event($Event) {
    $values = Event-Data $Event
    $selected = [ordered]@{}
    foreach ($name in @('BugcheckCode', 'BugcheckParameter1', 'BugcheckParameter2', 'BugcheckParameter3',
                        'BugcheckParameter4', 'SleepInProgress', 'PowerButtonTimestamp')) {
        if ($values.ContainsKey($name)) { $selected[$name] = Safe-Text $values[$name] }
    }
    $code = Number-OrNull $values['BugcheckCode']
    if ($null -eq $code -and $Event.ProviderName -eq 'Microsoft-Windows-WER-SystemErrorReporting') {
        # Provider param1 is the bugcheck description on common localized builds.
        foreach ($v in @($values['param1'], $values['BugcheckCode'])) {
            if ($v -match '0x([0-9a-fA-F]+)') { $code = [Convert]::ToInt64($Matches[1], 16); break }
        }
    }
    return [ordered]@{
        log = $Event.LogName; provider = $Event.ProviderName; id = [int]$Event.Id
        record_id = $Event.RecordId; time = $Event.TimeCreated.ToUniversalTime().ToString('o')
        level = $Event.Level; bugcheck_code = $code; data = $selected
    }
}

Invoke-Section 'system' {
    $os = Get-CimInstance Win32_OperatingSystem
    $pc = Get-CimInstance Win32_ComputerSystem
    $bios = Get-CimInstance Win32_BIOS
    [ordered]@{
        os = $os.Caption; version = $os.Version; build = $os.BuildNumber
        manufacturer = $pc.Manufacturer; model = $pc.Model
        bios_version = ($bios.SMBIOSBIOSVersion); bios_date = ([string]$bios.ReleaseDate)
        last_boot = $os.LastBootUpTime.ToUniversalTime().ToString('o')
        total_memory_kb = $os.TotalVisibleMemorySize; free_memory_kb = $os.FreePhysicalMemory
    }
}

Invoke-Section 'devices' {
    $script:presenceKnown = $false
    $script:presentKeys = @{}
    try {
        foreach ($device in @(Get-PnpDevice -PresentOnly -ErrorAction Stop)) {
            $script:presentKeys[[string]$device.InstanceId] = $true
        }
        $script:presenceKnown = $true
    } catch { $script:presenceReason = Safe-Text $_.Exception.Message }
    foreach ($device in @(Get-CimInstance Win32_PnPEntity)) {
        $present = $null
        if ($script:presenceKnown) { $present = $script:presentKeys.ContainsKey([string]$device.PNPDeviceID) }
        elseif ($null -ne $device.Present) { $present = [bool]$device.Present }
        [ordered]@{
            device_key = Get-Key $device.PNPDeviceID; name = Safe-Text $device.Name
            class = $device.PNPClass; present = $present
            problem_code = $device.ConfigManagerErrorCode; status = $device.Status
        }
    }
}
if ($script:sections['devices'].status -eq 'ok' -and -not $script:presenceKnown) {
    $script:sections['devices'].status = 'partial'
    $script:sections['devices'].reason = 'PnP presence query unavailable; WMI presence used when available. ' + $script:presenceReason
}

Invoke-Section 'drivers' {
    foreach ($driver in @(Get-CimInstance Win32_PnPSignedDriver)) {
        [ordered]@{
            device_key = Get-Key $driver.DeviceID; device_name = Safe-Text $driver.DeviceName
            version = $driver.DriverVersion; provider = $driver.DriverProviderName
            date = [string]$driver.DriverDate; inf = $driver.InfName; signed = $driver.IsSigned
            driver_file = [System.IO.Path]::GetFileName([string]$driver.DriverName)
        }
    }
}

Invoke-Section 'gpu' {
    foreach ($item in @(Get-CimInstance Win32_VideoController)) {
        [ordered]@{ name = $item.Name; version = $item.DriverVersion; date = [string]$item.DriverDate; status = $item.Status }
    }
}
Invoke-Section 'audio' {
    foreach ($item in @(Get-PnpDevice -Class AudioEndpoint, MEDIA -ErrorAction Stop)) {
        [ordered]@{ name = Safe-Text $item.FriendlyName; class = $item.Class; status = $item.Status; device_key = Get-Key $item.InstanceId }
    }
}
Invoke-Section 'usb' {
    foreach ($item in @(Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPClass -eq 'USB' })) {
        [ordered]@{ name = Safe-Text $item.Name; status = $item.Status; problem_code = $item.ConfigManagerErrorCode; device_key = Get-Key $item.PNPDeviceID }
    }
}
Invoke-Section 'network' {
    foreach ($item in @(Get-NetAdapter -IncludeHidden -ErrorAction Stop)) {
        [ordered]@{ name = Safe-Text $item.Name; description = $item.InterfaceDescription; status = [string]$item.Status
            version = $item.DriverVersion; driver_file = [System.IO.Path]::GetFileName([string]$item.DriverFileName) }
    }
}
Invoke-Section 'disks' {
    foreach ($item in @(Get-PhysicalDisk -ErrorAction Stop)) {
        [ordered]@{ name = $item.FriendlyName; media_type = [string]$item.MediaType; health = [string]$item.HealthStatus
            operational = (@($item.OperationalStatus) -join ','); bytes = $item.Size }
    }
}
Invoke-Section 'disk_reliability' {
    foreach ($disk in @(Get-PhysicalDisk -ErrorAction Stop)) {
        foreach ($item in @(Get-StorageReliabilityCounter -PhysicalDisk $disk -ErrorAction Stop)) {
            [ordered]@{ name = $disk.FriendlyName; temperature = $item.Temperature; wear = $item.Wear
                power_on_hours = $item.PowerOnHours; read_errors_uncorrected = $item.ReadErrorsUncorrected
                write_errors_uncorrected = $item.WriteErrorsUncorrected }
        }
    }
}
Invoke-Section 'battery' {
    foreach ($item in @(Get-CimInstance Win32_Battery)) {
        [ordered]@{ name = $item.Name; charge_percent = $item.EstimatedChargeRemaining; status = $item.BatteryStatus }
    }
}
Invoke-Section 'resource' {
    $os = Get-CimInstance Win32_OperatingSystem
    $memory = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
    $cpu = Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'"
    [ordered]@{ total_memory_kb = $os.TotalVisibleMemorySize; free_memory_kb = $os.FreePhysicalMemory
        commit_percent = $memory.PercentCommittedBytesInUse; cpu_percent = $cpu.PercentProcessorTime }
}

Invoke-Section 'startup' {
    foreach ($item in @(Get-CimInstance Win32_StartupCommand)) {
        # Intentionally omit command arguments and user identities.
        [ordered]@{ name = Safe-Text $item.Name; location = Safe-Text $item.Location; source = 'Win32_StartupCommand' }
    }
    foreach ($path in @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Run',
                        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run',
                        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run')) {
        if (Test-Path -LiteralPath $path) {
            $key = Get-Item -LiteralPath $path
            foreach ($name in @($key.GetValueNames())) {
                [ordered]@{ name = Safe-Text $name; location = $path; source = 'Registry Run (name only)' }
            }
        }
    }
}
Invoke-Section 'services' {
    foreach ($item in @(Get-CimInstance Win32_Service -Filter "StartMode='Auto'")) {
        [ordered]@{ name = $item.Name; display_name = Safe-Text $item.DisplayName; state = $item.State; start_mode = $item.StartMode }
    }
}
Invoke-Section 'tasks' {
    foreach ($task in @(Get-ScheduledTask -ErrorAction Stop)) {
        if ([string]$task.State -eq 'Disabled') { continue }
        $triggers = @($task.Triggers | ForEach-Object { $_.CimClass.CimClassName })
        if (($triggers -join ' ') -match 'LogonTrigger|BootTrigger') {
            [ordered]@{ name = Safe-Text $task.TaskName; state = [string]$task.State; triggers = $triggers }
        }
    }
}

Invoke-Section 'events' {
    foreach ($event in @(Get-Events @{LogName = 'System'; Id = @(1, 17, 18, 19, 20, 41, 1001, 6008, 4101, 7000, 7009, 7011, 7023, 7031); StartTime = $script:since} $MaxEvents)) {
        Convert-Event $event
    }
    foreach ($event in @(Get-Events @{LogName = 'Application'; Id = @(1000, 1001, 1002); StartTime = $script:since} $MaxEvents)) {
        Convert-Event $event
    }
}
Invoke-Section 'driver_events' {
    foreach ($event in @(Get-Events @{LogName = 'Microsoft-Windows-Kernel-PnP/Configuration'; Id = @(400, 410, 411, 420, 430); StartTime = $script:since} $MaxEvents)) {
        $values = Event-Data $event
        $identity = $values['DeviceInstanceId']
        if (-not $identity) { $identity = $values['DeviceId'] }
        [ordered]@{ id = $event.Id; record_id = $event.RecordId; time = $event.TimeCreated.ToUniversalTime().ToString('o')
            provider = $event.ProviderName; device_key = Get-Key $identity
            inf = [System.IO.Path]::GetFileName([string]$values['DriverName'])
            version = $values['DriverVersion']; source = 'Kernel-PnP configuration event (not driver file date)' }
    }
}
Invoke-Section 'boot' {
    foreach ($event in @(Get-Events @{LogName = 'Microsoft-Windows-Diagnostics-Performance/Operational'; Id = 100; StartTime = $script:since} 20)) {
        $values = Event-Data $event
        $bootTime = Number-OrNull $values['BootTime']
        if ($null -eq $bootTime) { $bootTime = Number-OrNull $values['BootDuration'] }
        [ordered]@{ record_id = $event.RecordId; time = $event.TimeCreated.ToUniversalTime().ToString('o')
            boot_ms = $bootTime; main_path_ms = Number-OrNull $values['MainPathBootTime']
            post_boot_ms = Number-OrNull $values['BootPostBootTime']; boot_start = $values['BootStartTime']
            is_degradation = $values['BootIsDegradation'] }
    }
}
Invoke-Section 'boot_components' {
    foreach ($event in @(Get-Events @{LogName = 'Microsoft-Windows-Diagnostics-Performance/Operational'; Id = @(101, 102, 103, 108, 110); StartTime = $script:since} $MaxEvents)) {
        $values = Event-Data $event
        [ordered]@{ id = $event.Id; record_id = $event.RecordId; time = $event.TimeCreated.ToUniversalTime().ToString('o')
            name = Safe-Text $values['Name']; friendly_name = Safe-Text $values['FriendlyName']
            duration_ms = Number-OrNull $values['TotalTime']; degradation_ms = Number-OrNull $values['DegradationTime'] }
    }
}
Invoke-Section 'dumps' {
    $paths = @(
        @{path = (Join-Path $env:SystemRoot 'Minidump'); kind = 'minidump'; recursive = $false},
        @{path = (Join-Path $env:SystemRoot 'LiveKernelReports'); kind = 'live'; recursive = $true}
    )
    foreach ($target in $paths) {
        if (Test-Path -LiteralPath $target.path) {
            $items = @(Get-ChildItem -LiteralPath $target.path -Filter '*.dmp' -File -Recurse:$target.recursive -ErrorAction Stop |
                Sort-Object LastWriteTime -Descending | Select-Object -First 30)
            foreach ($item in $items) {
                [ordered]@{ name = $item.Name; kind = $target.kind; bytes = $item.Length; modified = $item.LastWriteTimeUtc.ToString('o') }
            }
        }
    }
    $full = Join-Path $env:SystemRoot 'MEMORY.DMP'
    if (Test-Path -LiteralPath $full) {
        $item = Get-Item -LiteralPath $full
        [ordered]@{ name = $item.Name; kind = 'kernel'; bytes = $item.Length; modified = $item.LastWriteTimeUtc.ToString('o') }
    }
}
Invoke-Section 'security' {
    $results = @()
    $errors = @()
    try {
        $item = Get-MpComputerStatus -ErrorAction Stop
        $results += [ordered]@{ source = 'Defender'; antivirus_enabled = $item.AntivirusEnabled; realtime_enabled = $item.RealTimeProtectionEnabled }
    } catch { $errors += 'Defender: ' + (Safe-Text $_.Exception.Message) }
    try {
        foreach ($item in @(Get-NetFirewallProfile -ErrorAction Stop)) {
            $results += [ordered]@{ source = 'Firewall'; profile = [string]$item.Name; enabled = [bool]$item.Enabled }
        }
    } catch { $errors += 'Firewall: ' + (Safe-Text $_.Exception.Message) }
    try {
        foreach ($item in @(Get-BitLockerVolume -ErrorAction Stop)) {
            $results += [ordered]@{ source = 'BitLocker'; mount = $item.MountPoint; protection = [string]$item.ProtectionStatus }
        }
    } catch { $errors += 'BitLocker: ' + (Safe-Text $_.Exception.Message) }
    try {
        $item = Get-Tpm -ErrorAction Stop
        $results += [ordered]@{ source = 'TPM'; present = $item.TpmPresent; ready = $item.TpmReady }
    } catch { $errors += 'TPM: ' + (Safe-Text $_.Exception.Message) }
    try { $results += [ordered]@{ source = 'SecureBoot'; enabled = [bool](Confirm-SecureBootUEFI -ErrorAction Stop) } }
    catch { $errors += 'SecureBoot: ' + (Safe-Text $_.Exception.Message) }
    $script:securityErrors = $errors
    $results
}
if ($script:sections['security'].status -eq 'ok' -and $script:securityErrors.Count -gt 0) {
    $script:sections['security'].status = 'partial'
    $script:sections['security'].reason = $script:securityErrors -join ' | '
}

$snapshot = [ordered]@{
    schema_version = 1; captured_at = (Get-Date).ToUniversalTime().ToString('o')
    machine_id = Get-Key $env:COMPUTERNAME; synthetic = $false
    collection = [ordered]@{ days = $Days; max_events_per_log = $MaxEvents; shell = $PSVersionTable.PSVersion.ToString()
        elevation_requested = $false; redaction = 'Best-effort; review before sharing'; boot_mode = 'unknown' }
    sections = $script:sections
}
$snapshot | ConvertTo-Json -Depth 12 -Compress
