#!/usr/bin/env python3
import cmd2
import psycopg2
import getpass
import os
import configparser
import json
import io
import argparse
import logging

from logging_format import log

from cmd2 import style
from colorama import Style, Fore
from halo import Halo
from prettytable import PrettyTable
from tabulate import tabulate
from linkedin_api import Linkedin

from plugins.twitter import TwitterModule
from plugins.github import GithubModule
from plugins.linkedin import LinkedinModule

def dir_path(string):
    if os.path.isdir(string):
        return string
    log.critical(f'{string} is not a valid directory')

parser_connect = cmd2.Cmd2ArgumentParser()
parser_connect.add_argument('--user',
                                   required=True,
                                   help="the database's user")
parser_connect.add_argument('--passwd',
                                   required=True,
                                   help='the folder of the leak')
parser_connect.add_argument('--dbname',
                                   required=True,
                                   help="the database's name")
parser_connect.add_argument('--host',
                                   default="localhost",
                                   help="the database's host")
parser_connect.add_argument('--port',
                                   default="5432",
                                   help="the database's port")

create_db_parser = cmd2.Cmd2ArgumentParser()
create_db_parser.add_argument('--user', required=True, help='the database user')
create_db_parser.add_argument('--passwd', required=True, help='the password to access the database')
create_db_parser.add_argument('--dbname', required=True, help='the name of the database')
create_db_parser.add_argument('--host', default='localhost', help='the database server')
create_db_parser.add_argument('--port', default='5432', help='the database port')

create_db_parser.add_argument('--comb', type=dir_path, required=True, help='directory with the comb structure')

parser_find = cmd2.Cmd2ArgumentParser()
parser_find.add_argument('--email')
parser_find.add_argument('--domain')

parser_use = cmd2.Cmd2ArgumentParser()
parser_use.add_argument('--plugin',
                         choices=['twitter', 'github', 'linkedin'])

parser_show = cmd2.Cmd2ArgumentParser()
parser_show.add_argument('options')

autosave_options = cmd2.Cmd2ArgumentParser()
autosave_options.add_argument('--enable', action="store_true", default=False)
autosave_options.add_argument('--disable', action="store_true", default=False)

output_json_opts = cmd2.Cmd2ArgumentParser()
output_json_opts.add_argument('--filename', action='store', default=None)
output_json_opts.add_argument('--format', action='store', choices=['json','xml'])

class FirstApp(cmd2.Cmd):

    emojis = {
        'cross': "\U0000274c",
        "check": "\U00002714",
        "arrow_up": "\U00002b06",
        "page": "\U0001f4c4",
        "laptop": "\U0001f4bb",
    }

    def __init__(self, connector_db=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conn = connector_db
        self.plugin_name = ''
        self.plugin_instance = None

        self.configfilepath = os.path.join('config', 'tokens.ini')
        
        self.autoload = os.path.isfile(self.configfilepath) # if exists the file autoload = True
        self.autosave = self.autoload

    def leakdb_connected(func):
        def wrapper(*args, **kwargs):
            if args[0].conn == None:
                log.warning(f"Firstly connect the database with '{Style.BRIGHT}{Fore.WHITE}connect{Style.RESET_ALL}' command")
                return
            func(*args)
        return wrapper

    def plugin_activated(func):
        def wrapper(*args, **kwargs):
            if args[0].plugin_name == '':
                log.warning(f"You need to select a plugin with the '{Style.BRIGHT}{Fore.WHITE}use{Style.RESET_ALL}' command")
                return
            func(*args)
        return wrapper

    def do_print(self, args):
        plugin = args.arg_list[0]
        
        for profile in self.queue:
            if profile['plugin'] == plugin:
                print(json.dumps(profile))
        
    @cmd2.with_argparser(parser_connect)
    def do_connect(self, args):
        if self.conn == None:
            try:
                self.conn = psycopg2.connect(host=args.host, port=args.port,  database=args.dbname, user=args.user, password=args.passwd)
            except psycopg2.OperationalError:
                log.critical("Database connection failed")
                return

            log.info("Connecting to the Leak Database...")
        cur = self.conn.cursor()

        cur.execute('SELECT version()')
        db_version = cur.fetchone()
        log.warning(f"version: {db_version[0]}")

        cur.close()

    @cmd2.with_argparser(parser_find)
    @leakdb_connected
    def do_find(self, args):
        cur = self.conn.cursor()

        if args.email:
            cur.execute(f"SELECT * FROM data WHERE email='{args.email}'")

            table = [['passwords leaked']]
            for row in cur:
                table.append([row[1]])
        elif args.domain:
            log.error("Not implemented, because the db is not indexed by domain")
            table = [['email', 'password']]

        if len(table) > 1:
            tab = PrettyTable(table[0])
            tab.add_rows(table[1:])
            self.poutput(tab)
        else:
            log.error(f"Password not found for {args.email}")

        cur.close()

    @cmd2.with_argparser(parser_use)
    def do_use(self, args):
        self.prompt = f"{Fore.RED}emploleaks{Style.RESET_ALL}({args.plugin})> "
        self.plugin_name = args.plugin

        if args.plugin == 'twitter':
            self.plugin_instance = TwitterModule(queue=self.queue)
        elif args.plugin == 'linkedin':
            self.plugin_instance = LinkedinModule(queue=self.queue)
        elif args.plugin == 'github':
            self.plugin_instance = GithubModule(queue=self.queue)

        if self.autoload:
            self.load_options_from_configfile()

    def load_options_from_configfile(self):
        config = configparser.RawConfigParser()
        config.read(self.configfilepath)
        
        try:
            for option in config.items(self.plugin_name):
                for module_option in self.plugin_instance.options:
                    if module_option['name'].upper() == option[0].upper():
                        module_option['value'] = option[1]
                        break
        except configparser.NoSectionError:
            log.error(f"Skipping autoload because there isn't a section named \"{self.plugin_name}\"")
            pass

    @cmd2.with_argparser(parser_show)
    @plugin_activated
    def do_show(self, args):
        table = self.plugin_instance.do_show(args)
        self.poutput(tabulate(table, headers='firstrow', maxcolwidths=[None, 35]))

    @plugin_activated
    def do_setopt(self, args):
        name = args.arg_list[0]
        try:
            value = args.arg_list[1]
        except IndexError:
            value = getpass.getpass(prompt= name+": ")

        if self.autosave:
            config = configparser.RawConfigParser()
            config.read(self.configfilepath)

        for opt in self.plugin_instance.options:
            if opt['name'] == name:
                opt['value'] = value
                log.info("Updating value successfull")

                if self.autosave:
                    if not config.has_section(self.plugin_name):
                        config.add_section(self.plugin_name)

                    config.set(self.plugin_name, name, value)
               
                    if not os.path.exists('config'):
                         os.mkdir('config')

                    with open(self.configfilepath, 'w') as configfile:
                        config.write(configfile)
                        

                break
        else:
            log.error("Option invalid...")

    def do_deactivate(self, args):
        self.prompt = f"{Fore.RED}emploleaks{Style.RESET_ALL}> "
        self.plugin_name = ''
        self.plugin_instance = None

    @plugin_activated
    def do_run(self, args):
        if self.plugin_name == 'linkedin':
            try:
                cmd = args.arg_list[0]
            except IndexError:
                cmd = 'help'

            if cmd == 'find':
                try:
                    company_name = args.arg_list[1]
                
                    spinner = Halo(text='Gathering Information', spinner='dots')
                    spinner.start()

                    try:
                        found_id, found_staff = self.plugin_instance.get_company_info(company_name)
                        spinner.stop()
                    except:
                        log.critical(f"The company name '{company_name}' does not exist at LinkedIn")
                        spinner.stop()
                        return

                    depth = int((found_staff / 25) + 1)
                    outer_loops = range(0, 1)

                    #TODO: agregar la opcion para iterar de 25 en 25. Haciendo multiples llamadas a do_loops
                    profiles = self.plugin_instance.do_loops(found_id, outer_loops, depth)
                
                    api = Linkedin('', '', authenticate = True, cookies = self.plugin_instance.session.cookies)

                    spinner.stop_and_persist(symbol=self.emojis['laptop'], text='Listing profiles:')
                
                    for i, profile in enumerate(profiles):
                        print("{:2d}: ".format(i))
                        print("\tfull name: " + profile['full_name'])
                        print("\tprofile name: " + profile['profile_name'])
                        print("\toccupation: " + profile['occupation'])
                        print("\tpublic identifier: " + profile['publicIdentifier'])
                        print("\turn: " + profile['urn'])

                        spinner.start()                        
                        contact_info = api.get_profile_contact_info(public_id=profile['publicIdentifier'])

                        self.queue.append({
                            'plugin': 'linkedin',
                            'profile': profile,
                            'contact_info': contact_info
                        })

                        spinner.stop_and_persist(symbol=self.emojis['check'], text='Getting and processing contact info of "{}"'.format(profile['full_name']))

                        print("\tContact info:")
                      
                        if contact_info['email_address'] != None:
                            print("\t\temail: " + contact_info['email_address'])
                      
                        if contact_info['websites'] != None and contact_info['websites'] != []:
                            for i, website in enumerate(contact_info['websites']):
                                print("\t\twebsite {:d}. {:s}".format(i, website['url']))
                      
                        if contact_info['twitter'] != None and contact_info['twitter'] != []:
                            for i, twitter in enumerate(contact_info['twitter']):
                                print("\t\ttwitter {:d}. {:s}".format(i, twitter['name']))
                       
                        if contact_info['phone_numbers'] != None and contact_info['phone_numbers'] != []:
                            for i, phone in enumerate(contact_info['phone_numbers']):
                                print("\t\tphone {:d}. {}".format(i, phone))
                    
                        self.poutput(
                            style(f"\n{self.emojis['check']} Done", fg='green')
                        )
                except KeyboardInterrupt:
                    spinner.stop()
                        
            elif cmd == 'help':
                print("login: login in linkedin with your credentials")
                print("find [company]: seek members of the company at linkedin")
                print("help: show this message")

            elif cmd == 'impersonate':
                log.info("Using cookies from the browser")
                self.plugin_instance.impersonate()

        elif self.plugin_name == 'github':
            try:
                cmd = args.arg_list[0]
            except IndexError:
                self.plugin_instance.help()

            if cmd == 'stalk':
                github_username = args.arg_list[1]
                fields = [['username', 'email']]
                tab = PrettyTable(fields[0])

                mails = self.plugin_instance.find_mail(github_username)
                for mail in mails:
                    fields.append([ mail['user'], mail['email'] ])

                if len(fields) > 1:
                    tab.add_rows(fields[1:])
                    print(tab)
                else:
                    log.error("mail not found")

            elif cmd == 'help':
                self.plugin_instance.help()

            elif cmd == "get_repos":
                github_username = args.arg_list[1]
                data = self.plugin_instance.get_repos(github_username)
                
                fields = [['name', 'url', 'description']]
                #tab = PrettyTable(fields[0])
                
                for repo in data:
                    fields.append([ repo['name'], repo['url'], repo['description']])

                #tab.add_rows(fields[1:])
                #print(tab)
                self.poutput(tabulate(fields, headers='firstrow'))

            else:
                log.critical("Argument {} not recognized".format(cmd))
  
        elif self.plugin_name == 'twitter':
            try:
                cmd = args.arg_list[0]
            except IndexError:
                self.plugin_instance.help()

            if cmd == 'get_profile':
                try:
                    self.plugin_instance.run(username = args.arg_list[1])
                except IndexError:
                    log.error("Specify a twitter account as argument")

            elif cmd == 'get_tweets':
                try:
                    self.plugin_instance.get_tweets(username = args.arg_list[1])
                except IndexError:
                    log.error("Specify a twitter account as argument")

            elif cmd == 'help':
                self.plugin_instance.help()
            else:
                log.critical("Argument {} not recorgnized".format(cmd))

        else:
            log.critical("Not implemented yet...")
        
    @cmd2.with_argparser(output_json_opts)
    def do_set_output(self, args):
        if args.format == 'json' and args.filename != None:
            self.queue.append({
                'plugin': 'core',
                'format': args.format,
                'file': args.filename
            })
        else:
            log.critical("Not implemented yet...")
        
        log.info("All the issues will be loaded in the file")

    @cmd2.with_argparser(autosave_options)       
    def do_autosave(self, args):
        if args.enable and args.disable:
            log.critical("Invalid option, cannot set and unset this feature")
            return
        
        if args.enable:
            self.autosave = True
        elif args.disable:
            self.autosave = False
        
        log.info("autosave " + ('enabled' if self.autosave else 'disabled'))

    @cmd2.with_argparser(autosave_options)
    def do_autoload(self, args):
        if args.enable:
            self.autoload = True
        elif args.disable:
            self.autoload = False

        log.info("autoload " + ('enabled' if self.autoload else 'disabled'))

    @cmd2.with_argparser(create_db_parser)
    def do_create_db(self, args):
        log.warning('The full database occups more than 200 GB, take this in account')
        log.warning('Creating the database')
        #create_db_and_user.sh
        os.system('sudo -u postgres psql -c "CREATE DATABASE {0};"'.format(args.dbname))
        os.system('sudo -u postgres psql -c "CREATE USER {0} with encrypted password \'{1}\';"'.format(args.user, args.passwd))
        os.system('sudo -u postgres psql -c "ALTER ROLE {0} WITH SUPERUSER;"'.format(args.user))
        os.system('sudo -u postgres psql -c "ALTER DATABASE {0} OWNER TO {1};"'.format(args.dbname, args.user))
        os.system('sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE {0} TO {1};"'.format(args.dbname, args.user))

        # https://www.dbi-services.com/blog/the-fastest-way-to-load-1m-rows-in-postgresql/
        os.system('sudo -u postgres psql -c "ALTER SYSTEM SET fsync=\'off\';"')
        os.system('sudo -u postgres psql -c "ALTER SYSTEM SET synchronous_commit=\'off\';"')
        os.system('sudo -u postgres psql -c "ALTER SYSTEM SET full_page_writes=\'off\';"')
        os.system('sudo -u postgres psql -c "ALTER SYSTEM SET bgwriter_lru_maxpages=0;"')
        os.system('sudo -u postgres psql -c "ALTER SYSTEM SET wal_level=\'minimal\';"')
        os.system('sudo -u postgres psql -c "ALTER SYSTEM SET archive_mode=\'off\';"')
        os.system('sudo -u postgres psql -c "ALTER SYSTEM SET work_mem=\'64MB\';"')
        os.system('sudo -u postgres psql -c "ALTER SYSTEM SET max_wal_senders=0;"')
        os.system('sudo -u postgres psql -c "ALTER SYSTEM SET maintenance_work_mem=\'64MB\';"')
        os.system('sudo -u postgres psql -c "ALTER SYSTEM SET shared_buffers=\'128MB\';"')

        if self.conn == None:
            try:
                self.conn = psycopg2.connect(host=args.host, database=args.dbname, user=args.user, password=args.passwd)
            except psycopg2.OperationalError:
                log.critical("Database connection failed")
                return

            log.info("Connecting to the Leak Database...")
        cur = self.conn.cursor()
        
        cur.execute("CREATE TABLE IF NOT EXISTS data (email varchar(256) NOT NULL, password varchar(256) NOT NULL);")
        
        for root, dirs, files in os.walk(os.path.join(args.comb, "data"), topdown=False):
            for name in files:
                fname = (os.path.join(root, name))
                log.info(f'Importing from {fname}')
                
                with open(fname + '.csv', 'w') as sanitized:
                    with open(fname) as inputfile:
                        for line in inputfile:
                            line = line.strip()
                            if line and line.isprintable():
                                # Escape \ and "
                                line = line.replace('\\', '\\\\').replace('"', '\\"')
                                # Add quotes and replace : with ,
                                line = line.replace(':', '\",\"', 1)
                                line = '\"' + line + '\"'
                                
                                sanitized.write(line + '\n')
                os.remove(fname)
                try:
                    cur.execute("COPY data FROM %s CSV ESCAPE '\\';", (fname + '.csv',))
                except:
                    log.critical('May be a malformated entry in the file')
                # Make the changes to the database persistent
                self.conn.commit()

        log.info('Creating index...')
        cur.execute("CREATE INDEX email_idx_btree ON data USING btree (email);")

        cur.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='cross api tool for osint.')
    parser.add_argument('-d', '--debug', action='store_true', help='enable debug messages')
    args = parser.parse_args()

    if args.debug:
        log.setLevel(logging.DEBUG)

    queue = []

    c = FirstApp()
    c.queue = queue
    c.prompt = f"{Fore.RED}emploleaks{Style.RESET_ALL}> "
    ascii_logo = '''
___________              .__         .__                 __            
\_   _____/ _____ ______ |  |   ____ |  |   ____ _____  |  | __  ______
 |    __)_ /     \____  \|  |  /  _ \|  | _/ __ \__   \ |  |/ / /  ___/
 |        \  Y Y  \  |_> >  |_(  <_> )  |_\  ___/ / __ \|    <  \___ \ 
/_______  /__|_|  /   __/|____/\____/|____/\___  >____  /__|_ \/____  >
        \/      \/|__|                         \/     \/     \/     \/ 
'''
    c.poutput(ascii_logo)
    c.poutput("OSINT tool \U0001F575  to chain multiple apis")
    c.cmdloop()
