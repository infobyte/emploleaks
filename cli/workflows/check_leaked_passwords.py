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

linkedin_profiles = json.loads(previous_command_handler.stdout)
for profile in linkedin_profiles:
    if profile['contact_info'] != None and profile['contact_info']['email_address'] != None:
        import pdb;pdb.set_trace()
        find_leaked = app("find {}".format(profile['contact_info']['email_address']))
        print(find_leaked.stdout)        

