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
            print(f"[{Fore.RED}-{Style.RESET_ALL}] Method not implemented")

            client = tweepy.Client(bearer_token=self.options[0]['value'])
            tweets = client.user_timeline(screen_name="@pastaCLS")
            query = '#alberso -is:retweet lang:es'
            tweets = client.search_recent_tweets(query=query, tweet_fields=['context_annotations', 'created_at'], max_results=100)
        
            for tweet in tweets.data:
                print(tweet.text)
            
        elif access_token != '' and secret_token != '' and consumer_key != '' and consumer_secret != '':
            print(f"[{Fore.GREEN}+{Style.RESET_ALL}] Connecting to the API through Access and Secret token")
            
            auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
            auth.set_access_token(access_token, secret_token)
            api = tweepy.API(auth)
            
            number_of_tweets = 200
            tweets = api.user_timeline(screen_name = username)
            
            for tweet in tweets:
                print(tweet.text)

    def help(self):
        print("This plugin support the following commands:")
        print("\t* get_tweets @username: get_tweets of user")
        
