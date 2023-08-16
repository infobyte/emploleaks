#!/usr/bin/env python3
import cmd2
import psycopg2
import getpass
import os
import configparser
import json
import io

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
    print(f'[{Fore.RED}-{Style.RESET_ALL}] {string} is not a valid directory')

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

create_db_parser = cmd2.Cmd2ArgumentParser()
create_db_parser.add_argument('--user', required=True, help='the database user')
create_db_parser.add_argument('--passwd', required=True, help='the password to access the database')
create_db_parser.add_argument('--dbname', required=True, help='the name of the database')
create_db_parser.add_argument('--host', default='localhost', help='the database server')

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

parser_output = cmd2.Cmd2ArgumentParser()
parser_output.add_argument('--grepeable', action="store_true")
parser_output.add_argument('--no-grepeable', action='store_true')

class FirstApp(cmd2.Cmd):

    def __init__(self, connector_db=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conn = connector_db
        self.plugin_name = ''
        self.plugin_instance = None

        self.configfilepath = os.path.join('config', 'tokens.ini')
        
        self.autoload = os.path.isfile(self.configfilepath) # if exists the file autoload = True
        self.autosave = self.autoload
        self.output_grepeable = False
        self.previous = []

    def leakdb_connected(func):
        def wrapper(*args, **kwargs):
            if args[0].conn == None:
                args[0].poutput(f"[{Fore.RED}-{Style.RESET_ALL}] Firstly connect the database with '{Style.BRIGHT}{Fore.WHITE}connect{Style.RESET_ALL}' command")
                return
            func(*args)
        return wrapper

    def plugin_activated(func):
        def wrapper(*args, **kwargs):
            if args[0].plugin_name == '':
                args[0].poutput(f"[{Fore.RED}-{Style.RESET_ALL}] You need to select a plugin with the '{Style.BRIGHT}{Fore.WHITE}use{Style.RESET_ALL}' command")
                return
            func(*args)
        return wrapper

    @cmd2.with_argparser(parser_connect)
    def do_connect(self, args):
        if self.conn == None:
            try:
                self.conn = psycopg2.connect(host=args.host, database=args.dbname, user=args.user, password=args.passwd)
            except psycopg2.OperationalError:
                self.poutput(f"[{Fore.RED}-{Style.RESET_ALL}] Database connection failed")
                return

            self.poutput(f"[{Fore.GREEN}+{Style.RESET_ALL}] Connecting to the Leak Database...")
        cur = self.conn.cursor()

        cur.execute('SELECT version()')
        db_version = cur.fetchone()
        self.poutput(f"[{Fore.BLUE}*{Style.RESET_ALL}] version: {db_version[0]}")

        cur.close()

    def do_previous(self, args):
        plugin = args.arg_list[0]
        name = args.arg_list[1]
        for prev in self.previous:
            if name == prev['name'] and plugin == prev['plugin']:
                print(json.dumps(prev['data']))
                break

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
            self.poutput(f"[{Fore.RED}-{Style.RESET_ALL}] Not implemented, because the db is not indexed by domain")
            table = [['email', 'password']]

            '''
            self.poutput("This could take too long, are you sure? [y/N] ")
            cur.execute(f"SELECT * FROM data WHERE email like '%@{args.domain}'")
            
            for row in cur:
                table.append([row[0], row[1]])
            '''

        if len(table) > 1:
            tab = PrettyTable(table[0])
            tab.add_rows(table[1:])
            self.poutput(tab)
        else:
            print(f"[{Fore.RED}-{Style.RESET_ALL}] Password not found for {args.email}")

        cur.close()

    @cmd2.with_argparser(parser_use)
    def do_use(self, args):
        self.prompt = f"{Fore.RED}emploleaks{Style.RESET_ALL}({args.plugin})> "
        self.plugin_name = args.plugin

        if args.plugin == 'twitter':
            self.plugin_instance = TwitterModule()
        elif args.plugin == 'linkedin':
            self.plugin_instance = LinkedinModule()
        elif args.plugin == 'github':
            self.plugin_instance = GithubModule()

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
            print(f"[{Fore.RED}-{Style.RESET_ALL}] Skipping autoload because there isn't a section named \"{self.plugin_name}\"")
            pass

    @cmd2.with_argparser(parser_show)
    @plugin_activated
    def do_show(self, args):
        table = self.plugin_instance.do_show(args)
        self.poutput(tabulate(table, headers='firstrow'))

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
                self.poutput(f"[{Fore.GREEN}+{Style.RESET_ALL}] Updating value successfull")

                if self.autosave:
                    if not config.has_section(self.plugin_name):
                        config.add_section(self.plugin_name)

                    config.set(self.plugin_name, name, value)
                
                    with open(self.configfilepath, 'w') as configfile:
                        config.write(configfile)

                break
        else:
            self.poutput(f"[{Fore.RED}-{Style.RESET_ALL}] Option invalid...")

    def do_deactivate(self, args):
        self.prompt = f"{Fore.RED}emploleaks{Style.RESET_ALL}> "
        self.plugin_name = ''
        self.plugin_instance = None

    @cmd2.with_argparser(parser_output)
    def do_output(self, args):
        if args.grepeable:
            self.output_grepeable = True
            print(f"[{Fore.GREEN}+{Style.RESET_ALL}] grepeable format enabled")
        elif args.no_grepeable:
            self.output_grepeable = False
            print(f"[{Fore.GREEN}+{Style.RESET_ALL}] grepeable format disabled")

    @plugin_activated
    def do_run(self, args):
        if self.plugin_name == 'linkedin':
            try:
                cmd = args.arg_list[0]
            except IndexError:
                cmd = 'help'

            if cmd == 'find':
                company_name = args.arg_list[1]
                
                if not self.output_grepeable:
                    spinner = Halo(text='Gathering Information', spinner='dots')
                    spinner.start()

                found_id, found_staff = self.plugin_instance.get_company_info(company_name)
                depth = int((found_staff / 25) + 1)
                outer_loops = range(0, 1)

                #TODO: agregar la opcion para iterar de 25 en 25. Haciendo multiples llamadas a do_loops
                profiles = self.plugin_instance.do_loops(found_id, outer_loops, depth)

                self.previous.append({
                    'name': 'profiles',
                    'plugin': 'linkedin',
                    'data': profiles
                    })

                api = Linkedin(self.plugin_instance.get_username(), self.plugin_instance.get_password())
                
                if not self.output_grepeable:
                    spinner.stop_and_persist(symbol='🦄'.encode('utf-8'), text='Listing profiles:')

                for i, profile in enumerate(profiles):
                    if not self.output_grepeable:
                        print("{:2d}: ".format(i))
                        print("\tfull name: " + profile['full_name'])
                        print("\tprofile name: " + profile['profile_name'])
                        print("\toccupation: " + profile['occupation'])
                        print("\tpublic identifier: " + profile['publicIdentifier'])
                        print("\turn: " + profile['urn'])
                        
                        spinner.start()
                        contact_info = api.get_profile_contact_info(public_id=profile['publicIdentifier'])

                        for prev_profile in self.previous[-1]['data']:
                            #import pdb;pdb.set_trace()
                            if prev_profile['publicIdentifier'] == profile['publicIdentifier']:
                                prev_profile['contact_info'] = contact_info
                                break
                        else:
                            print(f"[{Fore.RED}-{Style.RESET_ALL}] Bug: public_id was not found in prev_profile")
                        
                        spinner.stop_and_persist(symbol='🔑'.encode('utf-8'), text='Getting and processing contact info of "{}"'.format(profile['full_name']))

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
                        
                    else:
                        contact_info = api.get_profile_contact_info(public_id=profile['publicIdentifier'])
                        
                        print(",".join([profile['full_name'],
                                        profile['profile_name'],
                                        profile['occupation'].replace(',', '.'),
                                        profile['publicIdentifier'],
                                        profile['urn']]), end="")
                        
                        email_address = '' if contact_info['email_address'] == None else  contact_info['email_address']
                        websites = []
                        twitters = []
                        phones = []
                        
                        if contact_info['websites'] != None and contact_info['websites'] != []:
                            for website in contact_info['websites']:
                                websites.append(website['url'])

                        if contact_info['twitter'] != None and contact_info['twitter'] != []:
                            for twitter in contact_info['twitter']:
                                twitters.append(twitter['name'])

                        if contact_info['phone_numbers'] != None and contact_info['phone_numbers'] != []:
                            for phone in contact_info['phone_numbers']:
                                phones.append(phone)

                        print(",{},{},{},{}".format(email_address, '|'.join(websites), '|'.join(twitters), '|'.join(phones)))


                    #TODO: fix this
                    #connections = api.search_people(connection_of=profile['urn'].split(':')[-1], network_depths='F')
                    #print(connections)

            elif cmd == 'help':
                print("login: login in linkedin with your credentials")
                print("find [company]: seek members of the company at linkedin")
                print("help: show this message")

            elif cmd == 'login':
                username = self.plugin_instance.get_username()
                password = self.plugin_instance.get_password()
                
                if username != '' and password != '':
                    if self.plugin_instance.login():
                        print(f"[{Fore.GREEN}+{Style.RESET_ALL}] Session established.")
                        
                    else:
                        print(f"[{Fore.RED}-{Style.RESET_ALL}] Session could not be established.")

                else:
                    print(f"[{Fore.RED}-{Style.RESET_ALL}] Fill the options. To see it, use 'show options'.")

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
                    print(f"[{Fore.RED}-{Style.RESET_ALL}] mail not found")

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
                print("Argument {} not recognized".format(cmd))
  
        elif self.plugin_name == 'twitter':
            try:
                cmd = args.arg_list[0]
            except IndexError:
                self.plugin_instance.help()

            if cmd == 'get_profile':
                try:
                    self.plugin_instance.run(username = args.arg_list[1])
                except IndexError:
                    print(f"[{Fore.RED}-{Style.RESET_ALL}] Specify a twitter account as argument")

            elif cmd == 'get_tweets':
                try:
                    self.plugin_instance.get_tweets(username = args.arg_list[1])
                except IndexError:
                    print(f"[{Fore.RED}-{Style.RESET_ALL}] Specify a twitter account as argument")

            elif cmd == 'help':
                self.plugin_instance.help()
            else:
                print("Argument {} not recorgnized".format(cmd))

        else:
            print(f"[{Fore.RED}-{Style.RESET_ALL}] Not implemented yet...")
        
    @cmd2.with_argparser(autosave_options)       
    def do_autosave(self, args):
        if args.enable and args.disable:
            print(f"[{Fore.RED}-{Style.RESET_ALL}] Invalid option, cannot set and unset this feature")
            return
        
        if args.enable:
            self.autosave = True
        elif args.disable:
            self.autosave = False
        
        print(f"[{Fore.GREEN}+{Style.RESET_ALL}] autosave " + ('enabled' if self.autosave else 'disabled'))

    @cmd2.with_argparser(autosave_options)
    def do_autoload(self, args):
        if args.enable:
            self.autoload = True
        elif args.disable:
            self.autoload = False

        print(f"[{Fore.GREEN}+{Style.RESET_ALL}] autoload " + ('enabled' if self.autoload else 'disabled'))

    @cmd2.with_argparser(create_db_parser)
    def do_create_db(self, args):
        print(f'[{Fore.BLUE}*{Style.RESET_ALL}] The full database occups more than 200 GB, take this in account')
        print(f'[{Fore.BLUE}*{Style.RESET_ALL}] Creating the database')
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
                self.poutput(f"[{Fore.RED}-{Style.RESET_ALL}] Database connection failed")
                return

            self.poutput(f"[{Fore.GREEN}+{Style.RESET_ALL}] Connecting to the Leak Database...")
        cur = self.conn.cursor()
        
        cur.execute("CREATE TABLE IF NOT EXISTS data (email varchar(256) NOT NULL, password varchar(256) NOT NULL);")
        
        for root, dirs, files in os.walk(os.path.join(args.comb, "data"), topdown=False):
            for name in files:
                fname = (os.path.join(root, name))
                print(f'[{Fore.GREEN}+{Style.RESET_ALL}] Importing from {fname}')
                
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
                    print(f'[{Fore.RED}-{Style.RESET_ALL}] May be a malformated entry in the file')
                # Make the changes to the database persistent
                self.conn.commit()

        print(f'[{Fore.BLUE}*{Style.RESET_ALL}] Creating index...')
        cur.execute("CREATE INDEX email_idx_btree ON data USING btree (email);")

        cur.close()

if __name__ == '__main__':
    c = FirstApp()
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
