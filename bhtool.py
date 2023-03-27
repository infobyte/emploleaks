import time
from linkedin_api import Linkedin
import re
import pymysql
import urllib.parse
import json
import string
import requests
import sys
import os
import random
import tempfile
import argparse
from modules.helper import Helper,createDbConnection,closeDbConnection

class NameMutator():
    def __init__(self, name):
        self.name = self.clean_name(name)
        self.name = self.split_name(self.name)

    @staticmethod
    def clean_name(name):
        name = name.lower()

        name = re.sub("[àáâãäå]", 'a', name)
        name = re.sub("[èéêë]", 'e', name)
        name = re.sub("[ìíîï]", 'i', name)
        name = re.sub("[òóôõö]", 'o', name)
        name = re.sub("[ùúûü]", 'u', name)
        name = re.sub("[ýÿ]", 'y', name)
        name = re.sub("[ß]", 'ss', name)
        name = re.sub("[ñ]", 'n', name)

        name = re.sub(r'\([^()]*\)', '', name)

        allowed_chars = re.compile('[^a-zA-Z -]')
        name = allowed_chars.sub('', name)

        titles = ['mr', 'miss', 'mrs', 'phd', 'prof', 'professor', 'md', 'dr', 'mba']
        pattern = "\\b(" + "|".join(titles) + ")\\b"
        name = re.sub(pattern, '', name)

        name = re.sub(r'\s+', ' ', name).strip()

        return name

    @staticmethod
    def split_name(name):
        parsed = re.split(' |-', name)

        if len(parsed) > 2:
            split_name = {'first': parsed[0], 'second': parsed[-2], 'last': parsed[-1]}
        else:
            split_name = {'first': parsed[0], 'second': '', 'last': parsed[-1]}

        return split_name

    def f_last(self):
        names = set()
        names.add(self.name['first'][0] + self.name['last'])

        if self.name['second']:
            names.add(self.name['first'][0] + self.name['second'])

        return names

    def f_dot_last(self):
        names = set()
        names.add(self.name['first'][0] + '.' + self.name['last'])

        if self.name['second']:
            names.add(self.name['first'][0] + '.' + self.name['second'])

        return names

    def last_f(self):
        names = set()
        names.add(self.name['last'] + self.name['first'][0])

        if self.name['second']:
            names.add(self.name['second'] + self.name['first'][0])

        return names

    def first_dot_last(self):
        names = set()
        names.add(self.name['first'] + '.' + self.name['last'])

        if self.name['second']:
            names.add(self.name['first'] + '.' + self.name['second'])

        return names

    def first_l(self):
        names = set()
        names.add(self.name['first'] + self.name['last'][0])

        if self.name['second']:
            names.add(self.name['first'] + self.name['second'][0])

        return names

    def first(self):
        names = set()
        names.add(self.name['first'])

        return names

class bhtool:
    def __init__(self):
        self.args = self.parse_arguments()
        self.session = self.login()

        domain_id = self.insert_domain_and_company()

        if not self.session:
            print("Session could not be established.")
            sys.exit()

        print("Session established.")

        found_id, self.found_staff = self.get_company_info(self.args.company,self.session)

        depth = self.set_inner_loops()
        outer_loops = self.set_outer_loops()

        #profiles = [{'full_name': X ,'profile_name': X},...]
        profiles = self.do_loops(self.session, found_id, outer_loops, depth)

        #profiles = [{'full_name': X ,'profile_name': X,'employee_id': X},...]
        profiles = self.insert_employeesmail_formated(domain_id, self.args.domain, profiles)

        self.api = Linkedin(Helper.userset['username'], Helper.userset['password'])

        self.get_and_insert_linkedin_contact_information(domain_id, profiles)

    def insert_domain_and_company(self):
        cursor,db = createDbConnection()
        try:
            cursor.execute("INSERT INTO Domains(domain_name,company_linkedin_page) VALUES(%s,%s);",(self.args.domain,self.args.company))
            db.commit()
            domain_id = cursor.lastrowid
        except (pymysql.Error, pymysql.Warning) as e:
            print(e)
            closeDbConnection(cursor,db)
            return 0
        closeDbConnection(cursor,db)

        print("domain and company inserted")
        return domain_id

    def parse_arguments(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--company', type=str, action='store',required=True,help='Company name exactly as typed in the company linkedin profile page URL.')
        parser.add_argument('-d', '--domain', type=str, action='store',required=True,help='Company domain, it will be used to create coorporate mails.')

        # Read arguments from command line
        args = parser.parse_args()

        return args

    def login(self):
        session = requests.session()

        login_problems = ['challenge', 'captcha', 'manage-account', 'add-email']

        mobile_agent = ('Mozilla/5.0 (Linux; U; Android 4.4.2; en-us; SCH-I535 '
                        'Build/KOT49H) AppleWebKit/534.30 (KHTML, like Gecko) '
                        'Version/4.0 Mobile Safari/534.30')
        session.headers.update({'User-Agent': mobile_agent,
                                'X-RestLi-Protocol-Version': '2.0.0'})

        anon_response = session.get('https://www.linkedin.com/login')
        login_csrf = re.findall(r'name="loginCsrfParam" value="(.*?)"',
                                anon_response.text)
        if login_csrf:
            login_csrf = login_csrf[0]
        else:
            print("Having trouble loading login page... try the command again.")
            sys.exit()

        # Define the data we will POST for our login.
        auth_payload = {
            'session_key': Helper.userset['username'],
            'session_password': Helper.userset['password'],
            'isJsEnabled': 'false',
            'loginCsrfParam': login_csrf
            }

        response = session.post('https://www.linkedin.com/checkpoint/lg/login-submit'
                                '?loginSubmitSource=GUEST_HOME',
                                data=auth_payload, allow_redirects=False)

        if response.status_code in (302, 303):
            # Add CSRF token for all additional requests
            session = self.set_csrf_token(session)
            redirect = response.headers['Location']
            if 'feed' in redirect:
                return session
            if 'add-phone' in redirect:
                url = 'https://www.linkedin.com/checkpoint/post-login/security/dismiss-phone-event'
                response = session.post(url)
                if response.status_code == 200:
                    return session
                print("[!] Could not skip phone prompt. Log in via the web and then try again.\n")

            elif any(x in redirect for x in login_problems):
                print("[!] LinkedIn has a message for you that you need to address. "
                      "Please log in using a web browser first, and then come back and try again.")
            else:
                print("[!] Some unknown redirection occurred. If this persists, please open an issue "
                      "and include the info below:")
                print("DEBUG INFO:")
                print(f"LOCATION: {redirect}")
                print(f"RESPONSE TEXT:\n{response.text}")

            return False

        if '<title>LinkedIn Login' in response.text:
            print("[!] Check your username and password and try again.\n")
            return False

        print("[!] Some unknown error logging in. If this persists, please open an issue on github.\n")
        print("DEBUG INFO:")
        print(f"RESPONSE CODE: {response.status_code}")
        print(f"RESPONSE TEXT:\n{response.text}")
        return False

    def set_csrf_token(self,session):
        csrf_token = session.cookies['JSESSIONID'].replace('"', '')
        session.headers.update({'Csrf-Token': csrf_token})
        return session

    def do_loops(self,session, company_id, outer_loops, depth):
        profiles_list = []

        try:
            for current_loop in outer_loops:
                current_region = ''
                current_keyword = ''

                for page in range(0, depth):
                    new_names = 0

                    sys.stdout.flush()
                    sys.stdout.write(f"[*] Scraping results on loop {str(page+1)}...    ")
                    result = self.get_results(session, company_id, page, current_region, current_keyword)
                    if result.status_code != 200:
                        print(f"\n[!] Yikes, got an HTTP {result.status_code}. This is not normal")
                        print("Bailing from loops, but you should troubleshoot.")
                        break
                    if "UPSELL_LIMIT" in result.text:
                        sys.stdout.write('\n')
                        print("[!] You've hit the commercial search limit! "
                              "Try again on the 1st of the month. Sorry. :(")
                        return profiles_list

                    found_profiles = self.find_employees(result.text)
                    if not found_profiles:
                        sys.stdout.write('\n')
                        print("[*] We have hit the end of the road! Moving on...")
                        break

                    new_names += len(found_profiles)
                    profiles_list.extend(found_profiles)

                    sys.stdout.write(f"    [*] Added {str(new_names)} new names. "
                                     f"Running total: {str(len(profiles_list))}"
                                     "              \r")

        except KeyboardInterrupt:
            print("\n\n[!] Caught Ctrl-C. Breaking loops and writing files")

        return profiles_list

    def get_results(self,session, company_id, page, region, keyword):
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

        result = session.get(url)
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
                        'profile_name': profile['publicIdentifier']}

            if len(employee['profile_name']) > 1:
                found_profiles.append(employee)

        return found_profiles

    def get_company_info(self,name, session):
        escaped_name = urllib.parse.quote_plus(name)

        response = session.get(('https://www.linkedin.com'
                                '/voyager/api/organization/companies?'
                                'q=universalName&universalName=' + escaped_name))

        if response.status_code == 404:
            print("[!] Could not find that company name. Please double-check LinkedIn and try again.")
            sys.exit()

        if response.status_code != 200:
            print("[!] Unexpected HTTP response code when trying to get the company info:")
            print(f"    {response.status_code}")
            sys.exit()

        if 'mwlite' in response.text:
            print("    A permanent fix is being researched. Sorry about that!")
            sys.exit()

        try:
            response_json = json.loads(response.text)
        except json.decoder.JSONDecodeError:
            sys.exit()

        company = response_json["elements"][0]

        found_name = company.get('name', "NOT FOUND")
        found_desc = company.get('tagline', "NOT FOUND")
        found_staff = company['staffCount']
        found_website = company.get('companyPageUrl', "NOT FOUND")

        found_id = company['trackingInfo']['objectUrn'].split(':')[-1]

        return (found_id, found_staff)

    def set_inner_loops(self):
        loops = int((self.found_staff / 25) + 1)

        return loops

    def set_outer_loops(self):
        outer_loops = range(0, 1)

        return outer_loops

    def insert_employeesmail_formated(self, domain_id, domain_name, profiles):
        cursor,db = createDbConnection()

        n_d = {'f_last':'','f_dot_last':'','first_l':'','first_dot_last':'','first':'','last_f':''}
        name_variations = ['f_last','f_dot_last','first_l','first_dot_last','first','last_f']

        for profile in profiles:
            mutator = NameMutator(profile["full_name"])

            for name_v in name_variations:
                try:
                    for name in getattr(mutator, name_v)():
                        n_d[name_v] = name + "@" + domain_name
                except Exception as e:
                    continue
            
            try:
                cursor.execute("INSERT INTO Employees(f_last,f_dot_last,first_l,first_dot_last,first,last_f,domain_id) VALUES(%s,%s,%s,%s,%s,%s,%s);",(n_d['f_last'],n_d['f_dot_last'],n_d['first_l'],n_d['first_dot_last'],n_d['first'],n_d['last_f'],domain_id))
                db.commit()
                employee_id = cursor.lastrowid
                profile['employee_id'] = employee_id

            except (pymysql.Error, pymysql.Warning) as e:
                print(e)
                break
        closeDbConnection(cursor,db)
        return profiles


    #================================================================================================================

    def get_and_insert_linkedin_contact_information(self, domain_id, profiles):
        cursor,db = createDbConnection()
        for profile in profiles:
            contact_info_dict = self.api.get_profile_contact_info(profile['profile_name'])
            if contact_info_dict['email_address'] != [] and contact_info_dict['email_address'] != None:
                try:
                    cursor.execute("INSERT INTO PersonalMails(personal_mail_name,leak_checked,employee_id) VALUES(%s,%s,%s);",(contact_info_dict['email_address'],'No',profile['employee_id']))
                    db.commit()
                except (pymysql.Error, pymysql.Warning) as e:
                    pass
            if contact_info_dict['websites'] != [] and contact_info_dict['websites'] != None:
                for web in contact_info_dict['websites']:
                    try:
                        cursor.execute("INSERT INTO Websites(website,checked,employee_id) VALUES(%s,%s,%s);",(web['url'],'No',profile['employee_id']))
                        db.commit()
                    except (pymysql.Error, pymysql.Warning) as e:
                        pass
            if contact_info_dict['twitter'] != [] and contact_info_dict['twitter'] != None:
                for twitter in contact_info_dict['twitter']:
                    try:
                        cursor.execute("INSERT INTO TwitterUsernames(username,checked,employee_id) VALUES(%s,%s,%s);",(twitter['name'],'No',profile['employee_id']))
                        db.commit()
                    except (pymysql.Error, pymysql.Warning) as e:
                        pass
            print("profile inserted")

        closeDbConnection(cursor,db)



bhtool()

