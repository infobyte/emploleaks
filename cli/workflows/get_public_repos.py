import os
import sys
import time
import json

from colorama import Fore, Style

try:
    company = sys.argv[1]
except IndexError:
    print(f"[{Fore.RED}-{Style.RESET_ALL}] You need to provide a company name")
    sys.exit(1)

app('use --plugin linkedin')
app_handler = app('run login')

while "LinkedIn has a message for you" in app_handler.stdout:
    print(f"[{Fore.RED}-{Style.RESET_ALL}] Failing login... trying again!")
    app_handler = app('run login')
    time.sleep(1)

if "Session" in app_handler.stdout:
    print(f"[{Fore.GREEN}+{Style.RESET_ALL}] Connected to the LinkedIn api successfull")

print("The following command could take a couple of minutes, be pacient")

command_handler = app("run find {}".format(company))
previous_command_handler = app("previous linkedin profiles")

#print(previous_command_handler.stdout)
#import pdb;pdb.set_trace()
linkedin_profiles = json.loads(previous_command_handler.stdout)

#print(linkedin_profiles)
is_first = True
for profile in linkedin_profiles:
    try:
        if profile['contact_info'] != None and profile['contact_info']['websites'] != None:
            for website in profile['contact_info']['websites']:
                if 'github' in website:
                    if is_first:
                        app('deactivate')
                        app('use --plugin github')

                        is_first = False

                    print(f"[{Fore.GREEN}+{Style.RESET_ALL}] github repo located for {profile['full_name']}")

                    username = website.replace('https://github.com', '')
                    username = username.replace('/','')

                    print(f"[{Fore.BLUE}*{Style.RESET_ALL}] accessing repos from {username}")
                    repos_cmd = app('run get_repos {}'.format(username))
                    print(repos_cmd.stdout)
            
                    
            '''
            print(f'[{Fore.GREEN}+{Style.RESET_ALL}] Password for "', end='')
            print('{}" exists'.format(profile['full_name']))

            print(f'[{Fore.BLUE}*{Style.RESET_ALL}] Email: ', end='')
            print(profile['contact_info']['email_address'])

            find_leaked = app("find --email {}".format(profile['contact_info']['email_address']))
            print(find_leaked.stdout)
            '''
    except KeyError:
        pass

