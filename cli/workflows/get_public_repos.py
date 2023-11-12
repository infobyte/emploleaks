import contextlib
import os
import sys
import time
import json

from colorama import Fore, Style

try:
    company_name = sys.argv[1]
except IndexError:
    company_name = None
    print("As you don't provide a company name it will use the previous linkedin profiles loaded")

if company_name != None:
    app('use --plugin linkedin')
    app_handler = app('run impersonate')

    print("Connected to the LinkedIn api successfull")
    print("The following command could take a couple of minutes, be pacient")

    command_handler = app(f"run find {company}")

print_command = app("print linkedin")

profiles = [json.loads(line) for line in print_command.stdout.split('\n')[:-1]]
for profile in profiles:
    with contextlib.suppress(KeyError):
        if profile['contact_info'] != None and profile['contact_info']['websites'] != None:
            for website in profile['contact_info']['websites']:
                if 'github' in website:
                    if is_first:
                        app('deactivate')
                        app('use --plugin github')

                        is_first = False

                    print(f"[{Fore.GREEN}+{Style.RESET_ALL}] github repo located for {profile['profile']['full_name']}")

                    username = website.replace('https://github.com', '')
                    username = username.replace('/','')

                    print(f"[{Fore.BLUE}*{Style.RESET_ALL}] accessing repos from {username}")
                    repos_cmd = app(f'run get_repos {username}')
                    print(repos_cmd.stdout)

