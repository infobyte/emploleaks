import random
import tweepy

class TwitterModule:
    def __init__(self):
        self.options = [{
                'name': 'BEARER_TOKEN',
                'value': '',
                'required': True,
                'description': "Token for access the twitter API"
             }, {
                'name': 'obfuscate',
                'value': 'no',
                'required': True,
                'description': "obfuscate the token in the show options menu"
            }]
            
    def do_show(self, args):
        print("Module options:\n")
        table = [['Name', 'Current Setting', 'Required', 'Description']]
        ofuscate_token = self.options[1]['value'] == 'yes'

        for opt in self.options:
            if ofuscate_token and opt['name'] == 'BEARER_TOKEN':
                table.append([ opt['name'], ''.join(['*' if random.randint(0,1) == 1 else c for c in self.options[0]['value']]), 'yes' if opt['required'] else 'no', opt['description']])
                continue
            table.append([ opt['name'], opt['value'], 'yes' if opt['required'] else 'no', opt['description']])
        return table

    def run(self):
        client = tweepy.Client(bearer_token=self.options[0]['value'])
        query = '#petday -is:retweet lang:en'
        tweets = client.search_recent_tweets(query=query, tweet_fields=['context_annotations', 'created_at'], max_results=100)
        
        for tweet in tweets.data:
            print(tweet.text)

    def help(self):
        print("This plugin support the following commands:")
        print("\t* get_tweets @username: get_tweets of user")
        
