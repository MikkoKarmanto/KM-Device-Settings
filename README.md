# KM Device Settings

This tool enables or disables the device default OpenApi startup application on Konica Minolta MFPs. It now includes a graphical user interface (GUI) in addition to the original console workflow.

The application currently uses application ID 3 when enabling the default application. For SafeQ 6, this is the SafeQ Print application. If other applications are installed on the device, this ID may differ (not configurable at the moment).

## GUI usage (Windows)

You can run the GUI with Python:

```powershell
pwsh
python .\ui_app.py
```

### In the GUI you can

- Enter one device at a time (IP address + admin password) and click Add.
- Import many devices from a CSV file (see schema below).
- Choose whether to Disable default application (checked = disable, unchecked = enable/restore).
- Start the operation, monitor per-device status, and cancel if needed.

Results are written to `status.csv` in the app folder (same format as the console version).

## Console usage

| Flag         | parameter        | Description                                                                    |
| ------------ | ---------------- | ------------------------------------------------------------------------------ |
| `--csv_file` | `[path to file]` | Path to the CSV file containing the IP addresses and passwords of the devices. |
| `--disable`  |                  | Removes the default OpenApi application setting.                               |

**Disable (remove default app):**

```powershell
pwsh
python .\Main.py --csv_file .\DeviceList.csv --disable
```

**Enable (restore default app):**

```powershell
pwsh
python .\Main.py --csv_file .\DeviceList.csv
```

## CSV structure

The expected CSV has a header row and two columns: `ipaddress,password`

```csv
ipaddress,password
192.168.1.10,AdminPasswordOfDevice
192.168.1.11,AnotherPassword
```

### Notes

- The GUI and console both accept this same CSV schema.
- The tool will attempt a quick ping check before calling the device API.
