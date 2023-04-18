import requests

class TwitterModule:
    def __init__(self):
        self.options = [{
                'name': 'CLIENT_ID',
                'value': '',
                'required': True,
                'description': "linkedin api's client id"
             }, {
                'name': 'CLIENT_SECRET',
                'value': '',
                'required': True,
                'description': "linkedin api's client secret"
            }]
            
    def run(self):
        print("corriendo plugin kaker")
