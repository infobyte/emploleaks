import requests
import re
import urllib
import json

from halo import Halo
from colorama import Fore, Style

class LinkedinModule:
    def __init__(self):
        self.options = [{
                'name': 'USER',
                'value': '',
                'required': True,
                'description': "linkedin account's username"
             }, {
                'name': 'PASS',
                'value': '',
                'required': True,
                'description': "linkedin accout's password"
            }, {
                'name': 'hide',
                'value': 'yes',
                'required': False,
                'description': "hide the password field"
            }]
            
        self.session = None

    def get_username(self):
        return self.options[0]['value']

    def get_password(self):
        return self.options[1]['value']

    def do_show(self, args):
        print("Module options:\n")
        table = [['Name', 'Current Setting', 'Required', 'Description']]        
        hide_pass = self.options[2]['value'] == 'yes'

        for opt in self.options:
            if hide_pass and opt['name'] == 'PASS':
                table.append([ opt['name'], '*' * len(self.options[1]['value']), 'yes' if opt['required'] else 'no', opt['description']])
                continue
            table.append([ opt['name'], opt['value'], 'yes' if opt['required'] else 'no', opt['description']])
        
        return table

    def login(self):
        username = self.get_username()
        password = self.get_password()

        self.session = requests.session()
        login_problems = ['challenge', 'captcha', 'manage-account', 'add-email']

        mobile_agent = ('Mozilla/5.0 (Linux; U; Android 4.4.2; en-us; SCH-I535 '
                        'Build/KOT49H) AppleWebKit/534.30 (KHTML, like Gecko) '
                        'Version/4.0 Mobile Safari/534.30')

        self.session.headers.update({'User-Agent': mobile_agent,
                                'X-RestLi-Protocol-Version': '2.0.0'})
        
        anon_response = self.session.get('https://www.linkedin.com/login')
        login_csrf = re.findall(r'name="loginCsrfParam" value="(.*?)"', anon_response.text)

        if login_csrf:
            login_csrf = login_csrf[0]
        else:
            print(f"[{Fore.RED}-{Style.RESET_ALL}] Having trouble loading login page... try the command again.")
            return

        auth_payload = {
            'session_key': username,
            'session_password': password,
            'isJsEnabled': 'false',
            'loginCsrfParam': login_csrf
            }

        response = self.session.post('https://www.linkedin.com/checkpoint/lg/login-submit'
                                '?loginSubmitSource=GUEST_HOME',
                                data=auth_payload, allow_redirects=False)

        if response.status_code in (302, 303):
            self.set_csrf_token()
            redirect = response.headers['Location']
            
            if 'feed' in redirect:
                return True

            if 'add-phone' in redirect:
                url = 'https://www.linkedin.com/checkpoint/post-login/security/dismiss-phone-event'
                response = self.session.post(url)
                if response.status_code == 200:
                    return self.session
                print(f"[{Fore.RED}-{Style.RESET_ALL}] Could not skip phone prompt. Log in via the web and then try again.")

            elif any(x in redirect for x in login_problems):
                print(f"[{Fore.RED}-{Style.RESET_ALL}] LinkedIn has a message for you that you need to address.")
                print(f"[{Fore.BLUE}*{Style.RESET_ALL}] Please log in using a web browser first, and then come back and try again.")

            else:
                print(f"[{Fore.RED}-{Style.RESET_ALL}] Some unknown redirection ocurred. If this persist, please open an issue and include the info below:")
                print("DEBUG INFO:")
                print(f"LOCATION: {redirect}")
                print(f"RESPONSE TEXT:\n{response.text}")

            return False

        if '<title>LinkedIn Login' in response.text:
            print(f"[{Fore.RED}-{Style.RESET_ALL}] Check your username and password and try again.")
            return False
        
        print(f"[{Fore.RED}-{Style.RESET_ALL}] Some unknown error logging in. If this persist, please open and issue on github.")
        print("DEBUG INFO:")
        print(f"RESPONSE CODE: {response.status_code}")
        print(f"RESPONSE TEXT:\n{response.text}")
        
        return False

    def set_csrf_token(self):
        csrf_token = self.session.cookies['JSESSIONID'].replace('"', '')
        self.session.headers.update({'Csrf-Token': csrf_token})
        
    def get_company_info(self, name):
        spinner = Halo(text='Gathering Information', spinner='dots')

        spinner.start()
        escaped_name = urllib.parse.quote_plus(name)

        response = self.session.get(('https://www.linkedin.com'
                                    '/voyager/api/organization/companies?'
                                    'q=universalName&universalName=' + escaped_name))

        if response.status_code == 404:
            print(f"[{Fore.RED}-{Style.RESET_ALL}] Could not find that company name. Please double-check LinkedIn and try again.")
            return

        if response.status_code != 200:
            spinner.stop()
            print(f"[{Fore.RED}-{Style.RESET_ALL}] Unexpected HTTP repsonse code when trying to get the company info:")
            print(f"\t{response.status_code}")
            return

        if 'mwlite' in response.text:
            spinner.stop()
            print("\tA permanent fix is being researched. Sorry about that!")
            return

        try:
            response_json = json.loads(response.text)
        except json.decoder.JSONDecodeError:
            spinner.stop()
            print(f"[{Fore.RED}-{Style.RESET_ALL}] Broke processing JSON, RAROOOO!")
            return

        company = response_json['elements'][0]
        
        found_name = company.get('name', 'NOT FOUND')
        found_desc = company.get('tagline', 'NOT FOUND')
        found_staff = company['staffCount']
        found_website = company.get('companyPageUrl', "NOT FOUND")

        found_id = company['trackingInfo']['objectUrn'].split(':')[-1]
        
        spinner.stop_and_persist(symbol='🦄'.encode('utf-8'), text='Wow!')
        return (found_id, found_staff)

    def do_loops(self, company_id, outer_loops, depth):
        profiles_list = []

        try:
            for current_loop in outer_loops:
                current_region = ''
                current_keyword = ''

                for page in range(0, depth):
                    new_names = 0

                    spinner = Halo(text="Scraping results on loop...",  spinner='dots')

                    result = self.get_results(company_id, page, current_region, current_keyword)
                    if result.status_code != 200:
                        print(f"\n[{Fore.RED}-{Style.RESET_ALL}] Yikes, got an HTTP {result.status_code}. This is not normal")
                        print("Bailing from loops, but you should troubleshoot.")
                        break
                    if "UPSELL_LIMIT" in result.text:
                        print("[{Fore.RED}-{Style.RESET_ALL}] You've hit the commercial search limit! "
                              "Try again on the 1st of the month. Sorry. :(")
                        spinner.stop()
                        return profiles_list

                    found_profiles = self.find_employees(result.text)
                    if not found_profiles:
                        print(f"[{Fore.GREEN}+{Style.RESET_ALL}] We have hit the end of the road! Moving on...")
                        break

                    new_names += len(found_profiles)
                    profiles_list.extend(found_profiles)

                    spinner.stop()
                    print(f"[{Fore.GREEN}+{Style.RESET_ALL}] Added {new_names} new names.")


        except KeyboardInterrupt:
            print("\n\n[!] Caught Ctrl-C. Breaking loops and writing files")

        return profiles_list
    
    def get_results(self, company_id, page, region, keyword):
        if region:
            region = re.sub(':', '%3A', region)  # must URL encode this parameter

        # Build the base search URL.
        url = ('https://www.linkedin.com'
               '/voyager/api/search/hits'
               f'?facetCurrentCompany=List({company_id})'
               f'&facetGeoRegion=List({region})'
               f'&keywords=List({keyword})'
               '&q=people&maxFacetValues=15'
               '&supportedFacets=List(GEO_REGION,CURRENT_COMPANY)'
               '&count=25'
               '&origin=organization'
               f'&start={page * 25}')

        result = self.session.get(url)
        return result
    
    def find_employees(self,result):
        found_profiles = []

        try:
            result_json = json.loads(result)
        except json.decoder.JSONDecodeError:
            return False

        if not result_json['elements']:
            return False


        for body in result_json['elements']:
            profile = (body['hitInfo']
                           ['com.linkedin.voyager.search.SearchProfile']
                           ['miniProfile'])
            
            full_name = f"{profile['firstName']} {profile['lastName']}"
            employee = {'full_name': full_name,
                        'profile_name': profile['publicIdentifier'],
                        'occupation': profile['occupation'],
                        'publicIdentifier': profile['publicIdentifier'],
                        'urn': profile['objectUrn'],
                        }

            if len(employee['profile_name']) > 1:
                found_profiles.append(employee)

        return found_profiles


