import pymysql
import re
import tempfile
import subprocess
import os
import time
import signal
import sys
import hashlib
import socket
import json

settings_path = os.path.dirname(__file__) + '/settings.json'

class Helper:
    json_file = open(settings_path)
    settings = json.load(json_file)
    json_file.close()

    dbset = settings['DB_SETTINGS']
    userset = settings['LINKEDIN_SETTINGS']

def createDbConnection():
    db = pymysql.connect(host=Helper.dbset["mysqlhost"], user=Helper.dbset["mysqluser"], password=Helper.dbset["mysqlpassword"],database=Helper.dbset["mysqldb"])
    cursor = db.cursor()
    return cursor,db

def closeDbConnection(cursor,db):
    cursor.close()
    db.close()

Helper()
