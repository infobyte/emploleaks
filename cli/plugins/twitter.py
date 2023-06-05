import random
import tweepy

from colorama import Fore, Style

class TwitterModule:
    def __init__(self):
        self.options = [{
                'name': 'BEARER_TOKEN',
                'value': '',
                'required': False,
                'description': "Token for access the twitter API"
            },{
                'name': 'ACCESS_TOKEN',
                'value': '',
                'required': False,
                'description': "Access token"
            },{
                'name': 'SECRET_TOKEN',
                'value': '',
                'required': False,
                'description': "Token Secret"
            },{
                'name': 'CONSUMER_KEY',
                'value': '',
                'required': False,
                'description': 'impossible, I don\'t know anything'
            },{
                'name': 'CONSUMER_SECRET',
                'value': '',
                'required': False,
                'description': "impossible, I don\'t know anything"
            },{
                'name': 'obfuscate',
                'value': 'no',
                'required': True,
                'description': "obfuscate the token in the show options menu"
            }]

        self.client = None
            
    def do_show(self, args):
        print("Module options:\n")
        table = [['Name', 'Current Setting', 'Required', 'Description']]
        ofuscate_token = self.options[5]['value'] == 'yes'

        for opt in self.options:
            if ofuscate_token and ( opt['name'] == 'BEARER_TOKEN' or opt['name'] == 'ACCESS_TOKEN' or opt['name'] == 'SECRET_KEY' ):
                table.append([ opt['name'], ''.join(['*' if random.randint(0,1) == 1 else c for c in self.options[0]['value']]), 'yes' if opt['required'] else 'no', opt['description']])
                continue
            table.append([ opt['name'], opt['value'], 'yes' if opt['required'] else 'no', opt['description']])
        return table

    def run(self, username=None):
        bearer_token = self.options[0]['value']
        access_token = self.options[1]['value']
        secret_token = self.options[2]['value']
        consumer_key = self.options[3]['value']
        consumer_secret = self.options[4]['value']

        if bearer_token != '':
            self.client = tweepy.Client(bearer_token=self.options[0]['value'])
            info_user = self.client.get_user(username = username, user_fields=['public_metrics', 'location', 'url'])
            
            print("Twitter Module")
            print("==============\n")
            print("username: {}".format(info_user.data.username))
            print("name: {}".format(info_user.data.name))
            print("location: {}".format(info_user.data.location))
            print("url: {}".format(info_user.data.url))
            

    def get_tweets(self, username=None):
        bearer_token = self.options[0]['value']
        
        if bearer_token != '' and self.client != None:
            user_id = self.client.get_user(username = username).data.id
            print("Fetching tweets from user: {}".format(user_id))
            tweets = self.client.get_users_tweets(id=user_id)
            
            if tweets.data != None:
                print("tweets:")
                for info in tweets.data:
                    print(info)
            
    def help(self):
        print("This plugin support the following commands:")
        print("\t* get_tweets @username: get_tweets of user")
        
