import requests
import re
import urllib
import json

from halo import Halo
from colorama import Fore, Style

class LinkedinModule:
    def __init__(self, queue=None):
        self.options = [{
                'name': 'hide',
                'value': 'yes',
                'required': False,
                'description': "hide the JSESSIONID field"
            }, {
                'name': 'JSESSIONID',
                'value': '',
                'required': False,
                'description': "active cookie session in browser #1"
            }, {
                'name': 'li-at',
                'value': '',
                'required': False,
                'description': "active cookie session in browser #1"
            }]
            
        self.session = None
        self.queue = queue

    def do_show(self, args):
        print("Module options:\n")
        table = [['Name', 'Current Setting', 'Required', 'Description']]        
        hide_pass = self.options[0]['value'] == 'yes'

        for opt in self.options:
            if hide_pass and opt['name'] == 'JSESSIONID':
                table.append([ opt['name'], '*' * len(self.options[1]['value']), 'yes' if opt['required'] else 'no', opt['description']])
                continue
            table.append([ opt['name'], opt['value'], 'yes' if opt['required'] else 'no', opt['description']])
        
        return table

    def impersonate(self):
        self.session = requests.session()

        mobile_agent = ('Mozilla/5.0 (Linux; U; Android 4.4.2; en-us; SCH-I535 '
                        'Build/KOT49H) AppleWebKit/534.30 (KHTML, like Gecko) '
                        'Version/4.0 Mobile Safari/534.30')

        self.session.headers.update({'User-Agent': mobile_agent,
                                'X-RestLi-Protocol-Version': '2.0.0'})

        print("Setting for first time JSESSIONID")
        self.session.cookies.set("JSESSIONID", self.options[1]['value'], domain='.www.linkedin.com', secure=True)

        print("Setting for first time li_at")
        self.session.cookies.set("li_at", self.options[2]['value'], domain='.www.linkedin.com', secure=True)

        self.set_csrf_token()

    def set_csrf_token(self):
        try:
            csrf_token = self.session.cookies['JSESSIONID'].replace('"', '')
            self.session.headers.update({'Csrf-Token': csrf_token})
        except KeyError:
            print("JSESSION is not setted")
        
    def get_company_info(self, name):
        if self.session.cookies.get('JSESSIONID', '') == '':
            print("Run impersonate first")
            return

        escaped_name = urllib.parse.quote_plus(name)

        response = self.session.get(('https://www.linkedin.com'
                                    '/voyager/api/organization/companies?'
                                    'q=universalName&universalName=' + escaped_name))

        if response.status_code == 404:
            print(f"\n[{Fore.RED}-{Style.RESET_ALL}] Could not find that company name. Please double-check LinkedIn and try again.")
            return

        if response.status_code != 200:
            print(f"[{Fore.RED}-{Style.RESET_ALL}] Unexpected HTTP repsonse code {response.status_code} when trying to get the company info:")
            return

        if 'mwlite' in response.text:
            print("\tA permanent fix is being researched. Sorry about that!")
            return

        try:
            response_json = json.loads(response.text)
        except json.decoder.JSONDecodeError:
            print(f"[{Fore.RED}-{Style.RESET_ALL}] Broke processing JSON, RAROOOO!")
            return

        company = response_json['elements'][0]
        
        found_name = company.get('name', 'NOT FOUND')
        found_desc = company.get('tagline', 'NOT FOUND')
        found_staff = company['staffCount']
        found_website = company.get('companyPageUrl', "NOT FOUND")

        found_id = company['trackingInfo']['objectUrn'].split(':')[-1]
        
        return (found_id, found_staff)

    def do_loops(self, company_id, outer_loops, depth):
        profiles_list = []

        try:
            for current_loop in outer_loops:
                current_region = ''
                current_keyword = ''

                for page in range(0, depth):
                    new_names = 0

                    result = self.get_results(company_id, page, current_region, current_keyword)
                    if result.status_code != 200:
                        print(f"\n[{Fore.RED}-{Style.RESET_ALL}] Yikes, got an HTTP {result.status_code}. This is not normal")
                        print("Bailing from loops, but you should troubleshoot.")
                        break
                    if "UPSELL_LIMIT" in result.text:
                        print("[{Fore.RED}-{Style.RESET_ALL}] You've hit the commercial search limit! "
                              "Try again on the 1st of the month. Sorry. :(")
                        return profiles_list

                    found_profiles = self.find_employees(result.text)
                    if not found_profiles:
                        print(f"[{Fore.GREEN}+{Style.RESET_ALL}] We have hit the end of the road! Moving on...")
                        break

                    new_names += len(found_profiles)
                    profiles_list.extend(found_profiles)

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

        headers = {
            'X-Li-Track': '{"clientVersion":"1.13.1793"}'
        }
        result = self.session.get(url, headers=headers)
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
            
            try:
                employee = {'full_name': full_name,
                        'profile_name': profile['publicIdentifier'],
                        'occupation': profile['occupation'],
                        'publicIdentifier': profile['publicIdentifier'],
                        'urn': profile['objectUrn'],
                        }
            except KeyError:
                print("profile has no occupation: {}".format(profile))

            if len(employee['profile_name']) > 1:
                found_profiles.append(employee)

        return found_profiles
