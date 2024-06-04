import argparse
import csv
import api as API
import os
import sys
from pythonping import ping

def ping_check_success(host: str) -> bool:
    """
    Ping given IP address. try twice and 1s timeout.

    @params:
        host   - Required  : IP address of the device (Str)

    @return:
        boolean            : True if response received otherwise false.
    """
    try:
        response = ping(host, count=2, timeout=1)

        for res in response._responses:
            if (res.success):
                return True
        return False
    
    except Exception as e:
        print(f"Error occurred while pinging {host}: {str(e)}")
        return False

if __name__ == '__main__':
    # Create an argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv_file', type=str, help='Path to the CSV file' , required=True)
    parser.add_argument('--disable', help='Disables default application', default=False, action='store_true')

    # Parse the command line arguments
    args = parser.parse_args()

    csv_file = args.csv_file
    disable_Default_Application = args.disable

    if not os.path.isfile(csv_file):
        print(f"Error: {csv_file} does not exist. Create a file with the following columns: ipaddress, password.")
        sys.exit(1)

    with open(csv_file, 'r') as file:
        reader = csv.DictReader(file)
        for i,row in enumerate(reader):
            ipaddress = row.get('ipaddress')
            password = row.get('password')
            try:
                print(f'Checking {ipaddress}...')
                if ping_check_success(ipaddress):
                    status = API.set_settings(password, f'http://{ipaddress}', disable_Default_Application)
                else:
                    print(f'Error: {ipaddress} is not reachable. Please check the connection.')
                    status = False
                
                with open('status.csv', 'a+') as output:
                    output.seek(0)
                    data = output.read(100)

                    if i == 0 and len(data) == 0:
                        output.write('ipaddress,status,disable_Default_Application\n')
                    
                    output.write(f'{ipaddress},{status},{disable_Default_Application}\n')

            except Exception as e:
                print(f"An error occurred: {str(e)}")
                continue


