# KM Device Settings

This application can remove and add default startup applications for MFP devices from the OpenApi menu. The application currently uses application ID 3 for addition. For SafeQ 6, this is the SafeQ Print application. If there are other applications installed on the device, this ID may be different. Currently, the ID cannot be specified.

| Flag        | parameter       | Description                                                                    |
|-------------|-----------------|--------------------------------------------------------------------------------|
| `--csv_file`| `[path to file]`| Path to the CSV file containing the IP addresses and passwords of the devices. |
| `--disable` |                 | Removes the default OpenApi application setting.                               |

## Usage

**Removal:**

````cmd
.\KM-Device-Settings.exe --csv_file DeviceList.csv --disable
````

**Restore:**

````cmd
.\KM-Device-Settings.exe --csv_file DeviceList.csv
````

## CSV structure

>ipaddress,password
>192.168.1.10,AdminPasswordOfDevice
