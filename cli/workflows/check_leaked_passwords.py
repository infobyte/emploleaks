import os
import sys
import time

from colorama import Fore, Style
from halo import Halo

class User:
    def __init__(self):
        self.full_name = None
        self.profile_name = None
        self.occupation = None
        self.public_identifier = None
        self.urn = None
        self.contact_info = {}

#print("Running Python script {!r} which was called with {} arguments".format(os.path.basename(sys.argv[0]), len(sys.argv) - 1))
#for i, arg in enumerate(sys.argv[1:]):
#    print("arg {}: {!r}".format(i + 1, arg))

try:
    company = sys.argv[1]
except IndexError:
    print(f"[{Fore.RED}-{Style.RESET_ALL}] You need to provide a company name")
    sys.exit(1)


app('use --plugin linkedin')
app('output --grepeable')

app_handler = app('run login')

while "LinkedIn has a message for you" in app_handler.stdout:
    print(f"[{Fore.RED}-{Style.RESET_ALL}] Failing login... trying again!")
    app_handler = app('run login')
    time.sleep(1)

if "Session" in app_handler.stdout:
    print(f"[{Fore.GREEN}+{Style.RESET_ALL}] Connected to the LinkedIn api successfull")

print("The following command could take a couple of minutes, be pacient")

spinner = Halo(text='Getting profiles from LinkedIn', spinner='dots')

spinner.start()
command_handler = app("run find {}".format(company))
spinner.stop_and_persist(symbol='🦄'.encode('utf-8'), text="All profiles available")

user_list = []

for line in command_handler.stdout.split('\n'):
    if not line.startswith('[') and len(line.split(',')) > 5:
        try:
            user = User()
            user.full_name = line.split(',')[0]
            user.profile_name = line.split(',')[1]
            user.occupation = line.split(',')[2]
            user.public_identifier = line.split(',')[3]
            user.urn = line.split(',')[4]
        except IndexError:
            import pdb;pdb.set_trace()
            print("IndexError spliteando {}".format(line))
        
        try:
            user.contact_info['email'] = line.split(',')[5]
            user.contact_info['websites'] = line.split(',')[6]
            user.contact_info['twitter'] = line.split(',')[7]
        except IndexError:
            print("The user has not contact information")
            continue

        if user.contact_info['email'] != '':
            print("preguntando por: {}".format(user.contact_info['email']))

        user_list.append(user)
