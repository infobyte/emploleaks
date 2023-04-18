import requests

class GithubModule:
    def __init__(self, client_id=None, client_secret=None):
        self.client_id = client_id
        self.client_secret = client_secret

    def options(self):
        print("esto y aquello")    
