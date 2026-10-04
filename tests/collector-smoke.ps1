# Execute the collector against synthetic providers only: no PC inspection.
$ErrorActionPreference = 'Stop'
$env:COMPUTERNAME = 'SYNTHETIC-TEST'
$env:USERNAME = 'SyntheticUser'
$env:USERPROFILE = 'X:\Users\SyntheticUser'

function Get-CimInstance {
    [CmdletBinding()] param([Parameter(Position=0)][string]$ClassName, [string]$Namespace, [string]$Filter)
    switch ($ClassName) {
        'Win32_OperatingSystem' { [pscustomobject]@{ Caption='Synthetic Windows'; Version='10.0'; BuildNumber='demo'; LastBootUpTime=[datetime]'2026-10-04T09:00:00Z'; TotalVisibleMemorySize=16777216; FreePhysicalMemory=8388608 } }
        'Win32_ComputerSystem' { [pscustomobject]@{ Manufacturer='Synthetic OEM'; Model='Synthetic model' } }
        'Win32_BIOS' { [pscustomobject]@{ SMBIOSBIOSVersion='DEMO-1'; ReleaseDate='2026-01-01' } }
        'Win32_PnPEntity' { [pscustomobject]@{ PNPDeviceID='PCI\SYNTHETIC'; Name='Synthetic adapter'; PNPClass='Net'; Present=$true; ConfigManagerErrorCode=10; Status='Error' } }
        'Win32_PnPSignedDriver' { [pscustomobject]@{ DeviceID='PCI\SYNTHETIC'; DeviceName='Synthetic adapter'; DriverVersion='1.2.3.4'; DriverProviderName='Synthetic vendor'; DriverDate='2006-06-21'; InfName='oem1.inf'; IsSigned=$true; DriverName='synthetic.sys' } }
        'Win32_VideoController' { @() }
        'Win32_Battery' { [pscustomobject]@{ Name='Synthetic battery'; EstimatedChargeRemaining=80; BatteryStatus=2 } }
        'Win32_PerfFormattedData_PerfOS_Memory' { [pscustomobject]@{ PercentCommittedBytesInUse=45 } }
        'Win32_PerfFormattedData_PerfOS_Processor' { [pscustomobject]@{ PercentProcessorTime=10 } }
        'Win32_LogicalDisk' { [pscustomobject]@{ DeviceID='C:'; FileSystem='NTFS'; Size=1000000000000; FreeSpace=500000000000 } }
        'BatteryFullChargedCapacity' { [pscustomobject]@{ InstanceName='synthetic-battery'; FullChargedCapacity=45000 } }
        'BatteryStaticData' { [pscustomobject]@{ InstanceName='synthetic-battery'; DesignedCapacity=50000 } }
        'Win32_QuickFixEngineering' { [pscustomobject]@{ HotFixID='KB-DEMO'; InstalledOn='2026-10-01' } }
        'Win32_StartupCommand' { @() }
        'Win32_Service' { @() }
        default { throw ('Unexpected provider in test: ' + $ClassName) }
    }
}
function Get-PnpDevice {
    [CmdletBinding()] param([switch]$PresentOnly, [string[]]$Class)
    if ($PresentOnly) { [pscustomobject]@{ InstanceId='PCI\SYNTHETIC'; FriendlyName='Synthetic adapter'; Class='Net'; Status='Error' } }
}
function Get-NetAdapter { [CmdletBinding()] param([switch]$IncludeHidden); @() }
function Get-PhysicalDisk { [CmdletBinding()] param(); [pscustomobject]@{ FriendlyName='Synthetic SSD'; MediaType='SSD'; HealthStatus='Healthy'; OperationalStatus='OK'; Size=1000000000000 } }
function Get-StorageReliabilityCounter { [CmdletBinding()] param($PhysicalDisk); [pscustomobject]@{ Temperature=30; Wear=1; PowerOnHours=20; ReadErrorsUncorrected=0; WriteErrorsUncorrected=0 } }
function Get-ScheduledTask { [CmdletBinding()] param(); @() }
function Test-Path { [CmdletBinding()] param([string]$LiteralPath); $false }
function Get-MpComputerStatus { [CmdletBinding()] param(); [pscustomobject]@{ AntivirusEnabled=$true; RealTimeProtectionEnabled=$true } }
function Get-NetFirewallProfile { [CmdletBinding()] param(); @() }
function Get-BitLockerVolume { [CmdletBinding()] param(); throw 'Not available in synthetic fixture' }
function Get-Tpm { [CmdletBinding()] param(); [pscustomobject]@{ TpmPresent=$true; TpmReady=$true } }
function Confirm-SecureBootUEFI { [CmdletBinding()] param(); $true }

function Make-TestEvent([int]$Id, [string]$Provider, [string]$Log) {
    $item = [pscustomobject]@{ Id=$Id; ProviderName=$Provider; LogName=$Log; RecordId=$Id; Level=2; TimeCreated=[datetime]'2026-10-04T09:00:00Z' }
    $item | Add-Member -MemberType ScriptMethod -Name ToXml -Value {
        if ($this.Id -eq 100) {
            return '<Event><EventData><Data Name="BootTime">40000</Data><Data Name="MainPathBootTime">23000</Data><Data Name="BootPostBootTime">17000</Data></EventData></Event>'
        }
        if ($this.Id -eq 41) { return '<Event><EventData><Data Name="BugcheckCode">159</Data></EventData></Event>' }
        return '<Event><EventData><Data Name="param1">0x0000009f (synthetic)</Data></EventData></Event>'
    }
    return $item
}
function Get-WinEvent {
    [CmdletBinding()] param($FilterHashtable, [int]$MaxEvents)
    if ($FilterHashtable.LogName -eq 'System') {
        Make-TestEvent 1001 'Microsoft-Windows-WER-SystemErrorReporting' 'System'
        Make-TestEvent 41 'Microsoft-Windows-Kernel-Power' 'System'
    } elseif ($FilterHashtable.LogName -eq 'Microsoft-Windows-Diagnostics-Performance/Operational' -and $FilterHashtable.Id -eq 100) {
        Make-TestEvent 100 'Microsoft-Windows-Diagnostics-Performance' 'Microsoft-Windows-Diagnostics-Performance/Operational'
    }
}

$source = Join-Path (Split-Path $PSScriptRoot -Parent) 'scripts\collect-diagnostics.ps1'
$json = . $source -Days 1 -MaxEvents 5
$payload = $json | ConvertFrom-Json
$payload.synthetic = $true
$payload | ConvertTo-Json -Depth 12 -Compress
