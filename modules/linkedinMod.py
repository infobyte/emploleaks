import re
import pymysql
import urllib.parse
import json
from linkedin_api import Linkedin
import string
import requests
import sys
import os
import random
import tempfile
import argparse
from helper import Helper,createDbConnection,closeDbConnection


class linkedinMod:
    def __init__(self):
        self.api = Linkedin(Helper.userset['username'], Helper.userset['password'])

        self.cursor,self.db = createDbConnection()
        linkedin_username_id, linkedin_username, employee_id = self.selectLinkedinUser()
        self.updateLinkedinData(linkedin_username_id)

        self.parseInsertLinkedinContactInformation(linkedin_username, employee_id)

        closeDbConnection(self.cursor,self.db)

    def parseInsertLinkedinContactInformation(self, profile_name, employee_id):
        contact_info_dict = self.api.get_profile_contact_info(profile_name)
        if contact_info_dict['email_address'] != [] and contact_info_dict['email_address'] != None:
            try:
                self.cursor.execute("INSERT INTO PersonalMails(personal_mail_name,leak_checked,employee_id) VALUES(%s,%s,%s);",(contact_info_dict['email_address'],'No',employee_id))
                self.db.commit()
            except (pymysql.Error, pymysql.Warning) as e:
                pass
        if contact_info_dict['websites'] != [] and contact_info_dict['websites'] != None:
            for web in contact_info_dict['websites']:
                try:
                    self.cursor.execute("INSERT INTO Websites(website,checked,employee_id) VALUES(%s,%s,%s);",(web['url'],'No',employee_id))
                    self.db.commit()
                except (pymysql.Error, pymysql.Warning) as e:
                    pass
        if contact_info_dict['twitter'] != [] and contact_info_dict['twitter'] != None:
            for twitter in contact_info_dict['twitter']:
                try:
                    self.cursor.execute("INSERT INTO TwitterUsernames(username,checked,employee_id) VALUES(%s,%s,%s);",(twitter['name'],'No',employee_id))
                    self.db.commit()
                except (pymysql.Error, pymysql.Warning) as e:
                    pass
        print("profile inserted")

    
    def selectLinkedinUser(self):
        try:
            self.cursor.execute("SELECT linkedin_username_id,username,employee_id FROM LinkedinUsernames WHERE checked=%s;",("No",))
            data = self.cursor.fetchall()

            linkedin_username_id = data[0][0]
            linkedin_username = data[0][1]
            employee_id = data[0][2]

            print(linkedin_username_id)
            print(linkedin_username)

            return linkedin_username_id, linkedin_username, employee_id
        except (pymysql.Error, pymysql.Warning) as e:
            print(e)
            closeDbConnection(self.cursor,self.db)
            sys.exit()
    
    def updateLinkedinData(self,linkedin_username_id):
        try:
            self.cursor.execute("UPDATE LinkedinUsernames SET checked=%s WHERE linkedin_username_id=%s;",('Yes',linkedin_username_id))
            self.db.commit()
        except (pymysql.Error, pymysql.Warning) as e:
            print(e)
            closeDbConnection(self.cursor,self.db)
            sys.exit()



linkedinMod()
