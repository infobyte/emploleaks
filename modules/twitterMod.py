import re
import pymysql
import urllib.parse
import json
import string
import requests
import sys
import os
import random
import tempfile
import argparse
from helper import createDbConnection,closeDbConnection


class twitterMod:
    def __init__(self):
        self.cursor,self.db = createDbConnection()
        twitter_username_id, twitter_username = self.selectTwitterUser()
        self.updateTwitterData(twitter_username_id)
        print("updated")

        #===aca es donde escriben las funciones pertinentes====
        #la conexion a la db esta abierta

        #def doblablabla...
        #....


        #========

        closeDbConnection(self.cursor,self.db)

    
    def selectTwitterUser(self):
        try:
            self.cursor.execute("SELECT twitter_username_id,username FROM TwitterUsernames WHERE checked=%s;",("No",))
            data = self.cursor.fetchall()

            twitter_username_id = data[0][0]
            twitter_username = data[0][1]

            print(twitter_username_id)
            print(twitter_username)

            return twitter_username_id, twitter_username
        except (pymysql.Error, pymysql.Warning) as e:
            print(e)
            closeDbConnection(self.cursor,self.db)
            sys.exit()
    
    def updateTwitterData(self,twitter_username_id):
        try:
            self.cursor.execute("UPDATE TwitterUsernames SET checked=%s WHERE twitter_username_id=%s;",('Yes',twitter_username_id))
            self.db.commit()
        except (pymysql.Error, pymysql.Warning) as e:
            print(e)
            closeDbConnection(self.cursor,self.db)
            sys.exit()



twitterMod()
