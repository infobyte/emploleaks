import os
import time
import json
import sys

from colorama import Fore, Style

try:
    company_name = sys.argv[1]
except IndexError:
    company_name = None
    print("As you don't provide a company name it will use the previous linkedin profiles loaded")

if company_name != None:
    app('use --plugin linkedin')
    app_handler = app('run impersonate')

    print(f"[{Fore.GREEN}+{Style.RESET_ALL}] Connected to the LinkedIn api successfull")
    print("The following command could take a couple of minutes, be pacient")

    command_handler = app("run find {}".format(company_name))

print_command = app("print linkedin")

profiles = []
for line in print_command.stdout.split('\n')[:-1]:
    profiles.append(json.loads(line))

for profile in profiles:
    try:
        if profile['contact_info'] != None and profile['contact_info']['email_address'] != None and '@' in profile['contact_info']['email_address']:
            print(f'[{Fore.GREEN}+{Style.RESET_ALL}] Password for "', end='')
            print('{}" appears at LinkedIn'.format(profile['profile']['full_name']))

            print(f'[{Fore.BLUE}*{Style.RESET_ALL}] Email: ', end='')
            print(profile['contact_info']['email_address'])

            find_leaked = app("find --email {}".format(profile['contact_info']['email_address']))
            print(find_leaked.stdout)
    except KeyError:
        pass
