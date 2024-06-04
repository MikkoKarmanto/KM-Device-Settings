import requests
from bs4 import BeautifulSoup
import time
import json

def set_settings(password, ip_address, disable_Default_Application, verify_certificate=False):
    session_token = None
    headers = {
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'accept-language': 'fi-FI,fi;q=0.9,en-US;q=0.8,en;q=0.7',
        'content-type': 'application/json; charset=UTF-8',
        'x-requested-with': 'XMLHttpRequest',
        'origin': f'{ip_address}',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'X-Frame-Options': 'SAMEORIGIN',
        'referer': f'{ip_address}/wcd/spa_main.html',
        "referrerPolicy": "strict-origin-when-cross-origin",
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Edg/113.0.1774.35'
    }

    with requests.session() as session:
        try:
            session, session_token = login(session, ip_address, password, headers, verify_certificate)
            if session == None or session_token == None:
                raise ConnectionError
            
            if disable_Default_Application:
                print('Disabling default application...')
                session, status = disable_default_application(session, ip_address, session_token, headers, verify_certificate)
            else:
                print('Enabling default application...')
                session, status = enable_default_application(session, ip_address, session_token, headers, verify_certificate)
                
            session = logout(session, ip_address, headers, verify_certificate)

            return status

        except ConnectionError:
            return False
        
        except Exception as ex:
            print(f'There was an error. {ex}')
            return None
        
        finally:
            if session:
                session.close()


def login(session, ip_address, password, headers, verify_certificate=False):
    try:
        login_url = f'{ip_address}/wcd/login.cgi'
        payload = {
            'R_ADM': 'AdminAdmin',
            'password': password,
            'func': 'PSL_LP1_LOG',
            'AuthType':'MiddleServer'
        }

        response = session.post(login_url, data=payload, headers=headers, timeout=10, verify=verify_certificate)
        if response.status_code != 200:
            return None, None
        
        if response.headers.get('Content-Type').split(';')[0] == 'text/html':
            soup = BeautifulSoup(response.text, 'html.parser')
            session_token = soup.select_one('input[type="hidden"][id="h_token"]')['value']
            if session_token:
                print('Login to portal successful.')
                print(f'SessionID: {session.cookies.get("ID")}')
                return session, session_token
            else:
                print(f'Could not get session token from {login_url}. No changes could be made.')
                return None, None
        
        elif response.headers.get('Content-Type').split(';')[0] == 'text/xml':
            soup = BeautifulSoup(response.text, 'xml')
            if soup.select_one('Function').text == 'err':
                print(f'Could not login to device {login_url}.')
            else:
                print('Could not read the error message.')
                print(f'{response.url}')
                print(f'{response.status_code}')
                print(f'{response.text}')
            return None, None
        else:
            print('Unknown response type')
            print(f'{response.url}')
            print(f'{response.status_code}')
            print(f'{response.headers}')
            print(f'{response.text}')
            return None, None
        
    except Exception as ex:
        print(f'There was an error when trying to login. {ex}')
        return None, None


def logout(session, ip_address, headers, verify_certificate=False):
    try:
        logout_url = f'{ip_address}/wcd/login_ex.json?_={int(time.time())}'

        response = session.get(logout_url, headers=headers, timeout=10, verify=verify_certificate)
        if response.status_code != 200:
            print(f'Could not logout. {response.status_code}')
            return session
        
        if response.headers.get('Content-Type').split(';')[0] == 'text/plain':
            print('Logout successful.')
            session.cookies.clear()
            return session
        
        elif response.headers.get('Content-Type').split(';')[0] == 'text/xml':
            soup = BeautifulSoup(response.text, 'xml')
            if soup.select_one('Function').text == 'err':
                print('Could not logout.')
            else:
                print('Could not read the error message.')
                print(f'{response.url}')
                print(f'{response.status_code}')
                print(f'{response.text}')
        else:
            print('Unknown response type')
            print(f'{response.url}')
            print(f'{response.status_code}')
            print(f'{response.headers}')
            print(f'{response.text}')
            return session
    except Exception as ex:
        print(f'There was an error when trying to logout. {ex}')
        return session


def disable_default_application(session, ip_address, session_token, headers, verify_certificate=False):
    try:
        openApiSettings_url = f'{ip_address}/wcd/api/AppReqSetCustomMessage/_004_014_IOP000'
        openApi_Settings = {
            "Token": session_token,
            "OpenApi": {
                "SslPortNo": "50003",
                "Proxy": { "ServerAddress": "", "PortNo": "8080", "SslPortNo": "8080", "FtpPortNo": "21", "UserName": "" },
                "VerificationStrength": {
                "Client": "Off",
                "ExpirationDate": "Off",
                "CN": "Off",
                "KeyDirections": "Off",
                "Chain": "Off",
                "LapseConfirmation": "Off"
                },
                "HTTPVersionSetting": "HttpV2n1",
                "OpenApiEnable": "OnWithoutPassword",
                "ExtApplicationLink": "On",
                "SpecifiedAppMode": { "Enable": "Off" }
            }
        }

        response = session.post(openApiSettings_url, data=json.dumps(openApi_Settings), headers=headers, timeout=10, verify=verify_certificate)

        if response.status_code != 200:
            print(f'Could not update Open API settings. {response.status_code}')

        elif response.headers.get('Content-Type').split(';')[0] == 'text/xml':
            soup = BeautifulSoup(response.text, 'xml')
            if (soup.select_one('Function') == 'err'):
                print(soup.select_one('Item Code'))
            else:
                print('Could not read the error message.')
                print(f'{response.url}')
                print(f'{response.status_code}')
                print(f'{response.text}')

        elif response.headers.get('Content-Type').split(';')[0] == 'text/plain':
            if response.json()['Result']['ResultInfo'] == 'Ack':
                print('Default application disabled.')
                return session, True
            else:
                print('Could not disable default application.')
                print(response.json()['Result'])
        else:
            print('Unknown response type')
            print(f'{response.url}')
            print(f'{response.status_code}')
            print(f'{response.headers}')
            print(f'{response.text}')
        return session, False
    
    except Exception as ex:
        print(f'There was an trying to disable default application. {ex}')
        return session

def enable_default_application(session, ip_address, session_token, headers, verify_certificate=False):
    try:
        openApiSettings_url = f'{ip_address}/wcd/api/AppReqSetCustomMessage/_004_014_IOP000'
        openApi_Settings = {
            "Token": session_token,
            "OpenApi": {
                "SslPortNo": "50003",
                "Proxy": { "ServerAddress": "", "PortNo": "8080", "SslPortNo": "8080", "FtpPortNo": "21", "UserName": "" },
                "VerificationStrength": {
                "Client": "Off",
                "ExpirationDate": "Off",
                "CN": "Off",
                "KeyDirections": "Off",
                "Chain": "Off",
                "LapseConfirmation": "Off"
                },
                "HTTPVersionSetting": "HttpV2n1",
                "OpenApiEnable": "OnWithoutPassword",
                "ExtApplicationLink": "On",
                "SpecifiedAppMode": { "Enable": "On", "StartUpApplication": "3", "MfpBasicFunction": "On" }
            }
        }

        response = session.post(openApiSettings_url, data=json.dumps(openApi_Settings), headers=headers, timeout=10, verify=verify_certificate)

        if response.status_code != 200:
            print(f'Could not update Open API settings. {response.status_code}')

        elif response.headers.get('Content-Type').split(';')[0] == 'text/xml':
            soup = BeautifulSoup(response.text, 'xml')
            if (soup.select_one('Function') == 'err'):
                print(soup.select_one('Item Code'))
            else:
                print('Could not read the error message.')
                print(f'{response.url}')
                print(f'{response.status_code}')
                print(f'{response.text}')
            return None
        elif response.headers.get('Content-Type').split(';')[0] == 'text/plain':
            if response.json()['Result']['ResultInfo'] == 'Ack':
                print('Default application Enabled.')
                return session, True
            else:
                print('Could not enable default application.')
                print(response.json()['Result'])
        else:
            print('Unknown response type')
            print(f'{response.url}')
            print(f'{response.status_code}')
            print(f'{response.headers}')
            print(f'{response.text}')
        return session, False
    
    except Exception as ex:
        print(f'There was an trying to disable default application. {ex}')
        return session

def get_new_token(session, ip_address, headers, verify_certificate=False):
    try:
        headers['referer'] = f'{ip_address}/wdc/spa_main.html'
        headers['accept'] = 'application/json, text/javascript, */*; q=0.01'
        token_url = f'{ip_address}/wcd/api/GetToken/AppReqGetCustomData/_A-00-00001?_={int(time.time())}'

        response = session.get(token_url, headers=headers, timeout=10, verify=verify_certificate)

        if response.status_code != 200:
            print(f'Could not get new token. {response.status_code}')
            return session, None
        
        elif response.headers.get('Content-Type').split(';')[0] == 'text/plain':
            return session, response.json()['MFP']['Token']
        
        else:
            print('Unknown response type')
            print(f'{response.url}')
            print(f'{response.status_code}')
            print(f'{response.headers}')
            print(f'{response.text}')
            return session, None
        
    except Exception as ex:
        print(f'There was an error when trying to get a new token. {ex}')
        return session, None
