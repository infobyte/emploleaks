#!/usr/bin/env python
import cmd2
import psycopg2

from colorama import Style, Fore
from prettytable import PrettyTable
from tabulate import tabulate
from linkedin_api import Linkedin

from plugins.twitter import TwitterModule
from plugins.github import GithubModule
from plugins.linkedin import LinkedinModule

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

parser_find = cmd2.Cmd2ArgumentParser()
parser_find.add_argument('--email')
parser_find.add_argument('--domain')

parser_use = cmd2.Cmd2ArgumentParser()
parser_use.add_argument('--plugin',
                         choices=['twitter', 'github', 'linkedin'])

parser_show = cmd2.Cmd2ArgumentParser()
parser_show.add_argument('options')

class FirstApp(cmd2.Cmd):

    def __init__(self, connector_db=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conn = connector_db
        self.plugin_name = ''
        self.plugin_instance = None

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

        tab = PrettyTable(table[0])
        tab.add_rows(table[1:])
        self.poutput(tab)

        cur.close()

    @cmd2.with_argparser(parser_use)
    def do_use(self, args):
        self.prompt = f"{Fore.RED}boom{Style.RESET_ALL}({args.plugin})> "
        self.plugin_name = args.plugin

        if args.plugin == 'twitter':
            self.plugin_instance = TwitterModule()
        elif args.plugin == 'linkedin':
            self.plugin_instance = LinkedinModule()
        elif args.plugin == 'github':
            self.plugin_instance = GithubModule()

    @cmd2.with_argparser(parser_show)
    @plugin_activated
    def do_show(self, args):
        print("Module options:\n")
        table = [['Name', 'Current Setting', 'Required', 'Description']]
        
        for opt in self.plugin_instance.options:
            if opt['required']:
                table.append([ opt['name'], opt['value'], 'yes', opt['description']])
            else:
                table.append([ opt['name'], opt['value'], 'no', opt['description']])
        
        self.poutput(tabulate(table, headers='firstrow'))

    @plugin_activated
    def do_setopt(self, args):
        name = args.arg_list[0]
        value = args.arg_list[1]

        for opt in self.plugin_instance.options:
            if opt['name'] == name:
                opt['value'] = value
                self.poutput(f"[{Fore.GREEN}+{Style.RESET_ALL}] Updating value successfull")
                break
        else:
            self.poutput(f"[{Fore.RED}-{Style.RESET_ALL}] Option invalid...")

    def do_deactivate(self, args):
        self.prompt = f"{Fore.RED}boom{Style.RESET_ALL}> "
        self.plugin_name = ''
        self.plugin_instance = None

    @plugin_activated
    def do_run(self, args):
        if self.plugin_name == 'linkedin':
            cmd = args.arg_list[0]
            if cmd == 'seek':
                company_name = args.arg_list[1]
                
                found_id, found_staff = self.plugin_instance.get_company_info(company_name)
                depth = int((found_staff / 25) + 1)
                outer_loops = range(0, 1)

                profiles = self.plugin_instance.do_loops(found_id, outer_loops, depth)
                
                api = Linkedin(self.plugin_instance.get_username(), self.plugin_instance.get_password())
                for profile in profiles:
                    print(f"[{Fore.GREEN}+{Style.RESET_ALL}] Contacts of: " + profile['full_name'])
                    connections = api.search_people(connection_of=profile['urn'].split(':')[-1], network_depths='F')
                    print(connections)
                    #import pdb;pdb.set_trace()

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
        else:
            print(f"[{Fore.RED}-{Style.RESET_ALL}] Not implemented yet...")
                

if __name__ == '__main__':
    c = FirstApp()
    c.prompt = f"{Fore.RED}boom{Style.RESET_ALL}> "
    c.poutput("E1 051nt3rO \U0001F575")
    c.cmdloop()
