import contextlib
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

    command_handler = app(f"run find {company_name}")

print_command = app("print linkedin")

print_output = app("print core")
output = None
if print_output.stdout.count("\n") == 1:
    output = json.loads(print_output.stdout[:-1])
    print(f"Loading the issues in format {output['format']} in the file {output['file']}")

profiles = [json.loads(line) for line in print_command.stdout.split('\n')[:-1]]
issues = []
for profile in profiles:
    with contextlib.suppress(KeyError):
        if profile['contact_info'] != None and profile['contact_info']['email_address'] != None and '@' in \
                profile['contact_info']['email_address']:
            print(f'[{Fore.GREEN}+{Style.RESET_ALL}] Password for "', end='')
            print(f"""{profile['profile']['full_name']}" appears at LinkedIn""")

            print(f'[{Fore.BLUE}*{Style.RESET_ALL}] Email: ', end='')
            print(profile['contact_info']['email_address'])

            find_leaked = app(f"find --email {profile['contact_info']['email_address']}")
            print(find_leaked.stdout)

            if output != None and "leaked" in find_leaked.stdout:
                issues.append({
                    'issue': f"password leaked for {profile['profile']['full_name']}",
                    'description': find_leaked.stdout
                })

if issues != []:
    with open(output['file'], "a") as json_file:
        json_file.write(json.dumps(issues))
