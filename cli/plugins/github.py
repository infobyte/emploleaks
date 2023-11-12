import requests
import json

from colorama import Style, Fore


class GithubModule:
    def __init__(self, queue=None):
        self.options = [{
            'name': 'token',
            'value': '',
            'required': True,
            'description': "github token to request"
        }, {
            'name': 'blur',
            'value': 'yes',
            'required': True,
            'description': "get fruit over the token"
        }]
        self.session = requests.Session()
        self.queue = queue

    def get_token(self):
        return self.options[0]['value']

    def do_show(self, args):
        print("Module options:\n")
        table = [['Name', 'Current Setting', 'Required', 'Description']]
        blur = self.options[1]['value'] == 'yes'

        table.extend(
            [
                opt['name'],
                opt['value'],
                'yes' if opt['required'] else 'no',
                opt['description'],
            ]
            for opt in self.options
        )
        return table

    def find_mail(self, username):
        mails = []

        headers = {'Authorization': 'Bearer ' + self.options[0]['value']}
        user_url = f"https://api.github.com/users/{username}"
        response = self.session.get(user_url, headers=headers)
        if response.status_code == 200:
            data = json.loads(response.text)
            mails.append({'user': username, 'email': data["email"]})
        else:
            print(f"[{Fore.RED}-{Style.RESET_ALL}] Error getting the information")
            return []

        return mails

    def get_repos(self, username):
        repos_url = f"https://api.github.com/users/{username}/repos"

        headers = {'Authorization': 'Bearer ' + self.options[0]['value']}
        response = self.session.get(repos_url, headers=headers)
        if response.status_code == 200:
            return json.loads(response.text)
        else:
            print(f"[{Fore.RED}-{Style.RESET_ALL} Error getting the repos")

    def help(self):
        print("plugin commands:")
        print("stalk github_username\tget email address from account.")
        print("get_repos github_username\tretrieve all public repos of the user.")
