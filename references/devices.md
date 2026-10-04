# Device, driver and hardware evidence

## Inventory and identity

Start with present PnP devices, numeric `ConfigManagerErrorCode`, signed drivers and the affected device class. Use hashed instance IDs in shared reports; keep exact hardware IDs local only when needed to select a supported OEM package. A display name is not sufficient to identify a driver package.

Common numeric codes guide the next question, not an automatic repair:

| Code | Evidence / next step |
| --- | --- |
| 0 | No reported PnP problem; does not rule out an intermittent fault |
| 10 | Device cannot start; correlate install, power, firmware and event evidence |
| 14 | Restart indicated; propose a restart only with authorization |
| 18 | Reinstallation indicated; verify the package and recovery route first |
| 22 | Device disabled; determine whether intentional before enabling |
| 28 | Drivers not installed; get the exact hardware ID and OEM package |
| 31 | Windows cannot load required drivers; inspect device stack and recent changes |
| 43 | Device reported a problem; can be software, firmware or hardware |
| 45 | Device disconnected; do not classify as active failure |
| 52 | Signature validation problem; do not disable signature enforcement |

If PnP presence and WMI information disagree, report the disagreement rather than guessing. Hardware health comes from a separate source; a device status does not establish electrical or thermal health.

## Targeted branches

- **GPU:** exact controller and driver version, display 4101 events, LiveKernelReports metadata, WHEA, workload and update timeline. Sensor data or a known crash pattern needs a separate verified source. `AdapterRAM` is often truncated; do not report it as authoritative modern VRAM.
- **Audio:** separate output endpoints from MEDIA-class driver devices. Check whether the expected endpoint exists and whether Bluetooth/HDMI/dock routing explains the symptom. Do not change default endpoints without consent.
- **USB/dock:** presence, error code, USB controller class, reconnect timeline and power transitions. An unknown device may need hardware IDs or physical cable/port testing; do not purge all disconnected devices.
- **Network:** link state, interface model, driver version and recent device events. Disconnected link is not necessarily a faulty driver. Correlate VPN, sleep/wake, OEM Wi-Fi and power policy. Do not collect network packet contents or Wi-Fi passwords.
- **Sleep/wake:** Power-Troubleshooter 1, Kernel-Power, BugCheck 0x9F/0x133 evidence. Use device stack/IRP details only when available; do not disable sleep, hibernation and Fast Startup together as a default workaround.
- **Storage:** Get-PhysicalDisk health and operational state, reliability counters if readable, disk/Ntfs/storport events. SMART unavailable is not SMART healthy. Ask about backup before invasive disk repair.
- **Firmware/TPM:** BIOS version, board model, TPM availability and BitLocker status. If a provisioning service repeatedly times out, verify exact OEM firmware/CSME advisories. Never clear TPM or change firmware as a shortcut.
- **Battery/temperature:** report only observed values. Battery charge is not battery wear. A battery report or already-authorized sensor tool can supply design/full-charge capacity and temperature; collection never installs one automatically.

## Known issues

`--advisories advisories.json` accepts a local, user-reviewed version advisory list (see schema). A match produces a **lead requiring vendor confirmation**, not proof of causality. Never infer reliability from a crowdsourced blacklist alone. Check source date, affected versions, architecture, hardware model and mitigations before recommending changes. The software does not download or execute advisory instructions.
