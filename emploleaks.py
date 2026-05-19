#!/usr/bin/env python3
import cmd2
import psycopg2
import sqlite3
import getpass
import os
import configparser
import json
import io
import argparse
import logging
import clickhouse_driver
import logging.handlers
import time
from tld import get_tld, get_fld
from tld.utils import update_tld_names
import tldextract

from utils.logging_format import log

from cmd2 import style, Fg
from colorama import Style, Fore
from halo import Halo
from prettytable import PrettyTable
from tabulate import tabulate
#from plugins.twitter import TwitterModule
from plugins.github import GithubModule
from plugins.linkedin import LinkedinModule
from plugins.hibp import HaveIBeenPwnedModule
from utils.ai_classifier import classify_roles
from utils.leak_parser import parse_file, iter_leak_files
from utils.email_lookup import lookup_email_sync

# Configurar logging para clickhouse_driver
clickhouse_logger = logging.getLogger('clickhouse_driver')
clickhouse_logger.setLevel(logging.WARNING)  # Cambiar de DEBUG a WARNING

# Configurar logging para urllib3 (usado por requests)
urllib3_logger = logging.getLogger('urllib3')
urllib3_logger.setLevel(logging.WARNING)

# Configurar logging para git
git_logger = logging.getLogger('git')
git_logger.setLevel(logging.WARNING)

# Configurar rutas base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, 'data')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
CONFIG_DIR = os.path.join(BASE_DIR, 'config')

# Crear directorios necesarios si no existen
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

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

parser_connect_leaks = cmd2.Cmd2ArgumentParser()
parser_connect_leaks.add_argument('--user', default=None,
                                   help="ClickHouse user (default: from config or 'default')")
parser_connect_leaks.add_argument('--passwd', default=None,
                                   help="ClickHouse password (default: from config or empty)")
parser_connect_leaks.add_argument('--dbname', default=None,
                                   help="ClickHouse database name (default: from config or 'credentials_db')")
parser_connect_leaks.add_argument('--host', default=None,
                                   help="ClickHouse host (default: from config or 'localhost')")
parser_connect_leaks.add_argument('--port', default=None,
                                   help="ClickHouse port (default: from config or '9000')")
parser_connect_leaks.add_argument('--secure',
                                   action='store_true',
                                   help="use secure connection (TLS)")
parser_connect_leaks.add_argument('--save', action='store_true',
                                   help="save connection settings to config")

create_db_parser = cmd2.Cmd2ArgumentParser()
create_db_parser.add_argument('--user', required=True, help='ClickHouse database user')
create_db_parser.add_argument('--passwd', required=True, help='ClickHouse database password')
create_db_parser.add_argument('--dbname', required=True, help='Name of the ClickHouse database to create')
create_db_parser.add_argument('--host', default='localhost', help='ClickHouse server host')
create_db_parser.add_argument('--port', default='9000', help='ClickHouse server port')
create_db_parser.add_argument('--secure', action='store_true', help='Use secure connection (TLS)')
create_db_parser.add_argument('--import-data', help='Optional: Path to a directory containing credential files to import (format: email:password:url)')

parser_find = cmd2.Cmd2ArgumentParser()
parser_find.add_argument('--email')
parser_find.add_argument('--domain')

parser_use = cmd2.Cmd2ArgumentParser()
parser_use.add_argument('--plugin',choices=['github', 'linkedin','hibp'])

parser_show = cmd2.Cmd2ArgumentParser()
parser_show.add_argument('options')

parser_find_breaches = cmd2.Cmd2ArgumentParser()
parser_find_breaches.description = "Search for breaches in all company emails using HaveIBeenPwned API"

parser_addcompany = cmd2.Cmd2ArgumentParser()
parser_addcompany.add_argument('--name')

parser_selectcompany = cmd2.Cmd2ArgumentParser()
parser_selectcompany.add_argument('--name')

parser_listcompanies = cmd2.Cmd2ArgumentParser()
parser_listcompanies.add_argument('list')

parser_findpasswords = cmd2.Cmd2ArgumentParser()
parser_findpasswords.add_argument('mode', choices=['find_all', 'only_usernames', 'only_emails'],
                                help='Search mode: find_all (search everything), only_usernames (search by usernames only), only_emails (search by emails only)')
parser_findpasswords.add_argument('--email', type=str, help='Buscar contraseñas filtradas para un correo específico (no se guarda en la base)')

parser_print = cmd2.Cmd2ArgumentParser()
parser_print.add_argument('--data',choices=['emails', 'passwords', 'breaches', 'gits', 'phones', 'twitters', 'websites', 'all', 'secrets'])
parser_print.add_argument('--export', action='store_true', help='Export data to CSV file')
parser_print.add_argument('--html', action='store_true', help='Generate interactive HTML report (only with --data all)')
parser_print.add_argument('--ai', action='store_true', help='Use AI to group employees by department in HTML report')

parser_set_ai = cmd2.Cmd2ArgumentParser()
parser_set_ai.add_argument('--endpoint', default='http://localhost:11434/v1',
                           help='OpenAI-compatible API endpoint (default: Ollama local)')
parser_set_ai.add_argument('--key', default='ollama',
                           help='API key (default: "ollama" for local Ollama)')
parser_set_ai.add_argument('--model', default='llama3',
                           help='Model name (e.g. gpt-4o-mini, llama3, mistral)')

parser_classify = cmd2.Cmd2ArgumentParser()
parser_classify.add_argument('--force', action='store_true',
                             help='Re-classify even if departments are already assigned')

parser_lookup = cmd2.Cmd2ArgumentParser()
parser_lookup.add_argument('--include-potential', action='store_true',
                           help='Also check potential (generated) emails, not just confirmed ones')
parser_lookup.add_argument('--email', type=str, default=None,
                           help='Lookup a single specific email address')

autosave_options = cmd2.Cmd2ArgumentParser()
autosave_options.add_argument('--enable', action="store_true", default=False)
autosave_options.add_argument('--disable', action="store_true", default=False)

output_json_opts = cmd2.Cmd2ArgumentParser()
output_json_opts.add_argument('--filename', action='store', default=None)
output_json_opts.add_argument('--format', action='store', choices=['json','xml'])

parser_deletecompany = cmd2.Cmd2ArgumentParser()
parser_deletecompany.add_argument('--name', required=True, help='name of the company to delete')

parser_run_find = cmd2.Cmd2ArgumentParser()
parser_run_find.add_argument('company_name', help='LinkedIn company name')
parser_run_find.add_argument('company_domain', help='Company email domain')
parser_run_find.add_argument('--email-format', help='Optional email format for potential emails (e.g. {n}.{s} for first initial + last name)')

parser_import_leaks = cmd2.Cmd2ArgumentParser()
parser_import_leaks.add_argument('directory', nargs='?', default=None,
                                  help='Directory with leak files (default: leaks_data/)')
parser_import_leaks.add_argument('--no-ai', action='store_true',
                                  help='Skip AI format detection for unknown files')

# Create parsers for commands
parser_use = argparse.ArgumentParser(description='Use a plugin')
parser_use.add_argument('--plugin', required=True, help='Plugin to use')

class GroupConcat:
    def __init__(self):
        self.values = set()
    
    def step(self, value):
        if value is not None:
            self.values.add(value)
    
    def finalize(self):
        return ','.join(sorted(self.values))

class EmploLeaksCLI(cmd2.Cmd):
    """EmploLeaks CLI"""

    emojis = {
        'cross': "\U0000274c",
        "check": "\U00002714",
        "arrow_up": "\U00002b06",
        "page": "\U0001f4c4",
        "laptop": "\U0001f4bb",
        'profile': "👤",
        'email': "📧",
        'website': "🌐",
        'twitter': "🐦",
        'phone': "📱",
        'github': "💻",
        'success': "✅",
        'error': "❌",
        'warning': "⚠️",
        'info': "ℹ️",
        'search': "🔍",
        'link': "🔗",
        'plus': "➕",
        'arrow': "➡️",
        'sparkles': "✨"
    }

    def preloop(self) -> None:
        """Print banner before starting the CLI"""
        banner = """
                      _       _            _        
  ___ _ __ ___  _ __ | | ___ | | ___  __ _| | _____ 
 / _ \\ '_ ` _ \\| '_ \\| |/ _ \\| |/ _ \\/ _` | |/ / __|
|  __/ | | | | | |_) | | (_) | |  __/ (_| |   <\\__ \\
 \\___|_| |_| |_| .__/|_|\\___/|_|\\___|\\__,_|_|\\_\\___/
               |_|                                  
"""
        self.poutput(style(banner, fg=Fg['WHITE']))
        self.poutput(style('\nWelcome to EmploLeaks CLI. Type help or ? to list commands.\n', fg=Fg['WHITE']))
        super().preloop()

    def __init__(self, connector_db=None, *args, **kwargs):
        super().__init__(*args, allow_cli_args=False, **kwargs)
        
        # Disable unused cmd2 commands
        self.hidden_commands.extend([
            'set',           # Disable set command
            'macro',         # Disable macro command
            'run_pyscript',  # Disable run_pyscript command
            'run_script',    # Disable run_script command
            'edit',          # Disable edit command
            'alias',         # Disable alias command
            'shortcuts',     # Disable shortcuts command
            'shell'          # Disable shell command
        ])
        
        self.conn = None  # PostgreSQL connection for leaks database
        self.leaks_conn = None  # ClickHouse connection for leaks database
        self.local_conn = None  # SQLite connection for local data
        self.company_id = None
        self.company_name = ''
        self.plugin_name = ''
        self.plugin_instance = None
        self.configfilepath = os.path.join(CONFIG_DIR, 'tokens.ini')
        self.autoload = os.path.isfile(self.configfilepath)
        self.autosave = self.autoload
        
        self.ai_endpoint = 'http://localhost:11434/v1'
        self.ai_key = 'ollama'
        self.ai_model = 'llama3'
        
        self.ch_host = 'localhost'
        self.ch_port = '9000'
        self.ch_user = 'default'
        self.ch_passwd = ''
        self.ch_dbname = 'credentials_db'
        
        self._load_global_config()
        
        # Emojis para la interfaz
        self.emojis = {
            'profile': "👤",
            'email': "📧",
            'website': "🌐",
            'twitter': "🐦",
            'phone': "📱",
            'github': "💻",
            'success': "✅",
            'error': "❌",
            'warning': "⚠️",
            'info': "ℹ️",
            'search': "🔍",
            'link': "🔗",
            'check': "✔️",
            'plus': "➕",
            'arrow': "➡️",
            'sparkles': "✨"
        }
        
        # Initialize SQLite database if it doesn't exist
        db_path = os.path.join(DB_DIR, 'emploleaks.db')
        self.local_conn = sqlite3.connect(db_path)
        self.local_conn.row_factory = sqlite3.Row
        self._init_local_db()

    def _init_local_db(self):
        """Initialize the local SQLite database with required tables."""
        cur = self.local_conn.cursor()
        
        # Crear tabla de compañías si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                company_id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT UNIQUE NOT NULL
            )
        """)
        
        # Crear tabla de empleados si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                title TEXT,
                profile_photo_url TEXT,
                company_id INTEGER,
                FOREIGN KEY (company_id) REFERENCES companies (company_id)
            )
        """)
        
        # Migrate: add profile_photo_url if missing (existing DBs)
        try:
            cur.execute("ALTER TABLE employees ADD COLUMN profile_photo_url TEXT")
            self.local_conn.commit()
        except sqlite3.OperationalError:
            pass
        
        # Crear tabla de emails si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                email_id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                employee_id INTEGER,
                FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
            )
        """)
        
        # Crear tabla de emails potenciales si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS potential_emails (
                email_id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                employee_id INTEGER,
                FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
            )
        """)
        
        # Crear tabla de contraseñas si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS passwords (
                password_id INTEGER PRIMARY KEY AUTOINCREMENT,
                password TEXT NOT NULL,
                email_id INTEGER,
                breach_context TEXT,
                FOREIGN KEY (email_id) REFERENCES emails (email_id),
                FOREIGN KEY (email_id) REFERENCES potential_emails (email_id),
                UNIQUE(password, email_id, breach_context)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS username_passwords (
                password_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                breach_context TEXT,
                company_id INTEGER,
                FOREIGN KEY (company_id) REFERENCES companies (company_id),
                UNIQUE(username, password, breach_context, company_id)
            )
        """)
        
        # Crear tabla de brechas si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS breaches (
                breach_id INTEGER PRIMARY KEY AUTOINCREMENT,
                breach_name TEXT NOT NULL,
                breach_date TEXT,
                breach_description TEXT,
                breach_domain TEXT,
                breach_data_classes TEXT,
                breach_is_verified BOOLEAN,
                breach_is_fabricated BOOLEAN,
                breach_is_sensitive BOOLEAN,
                breach_is_retired BOOLEAN,
                breach_is_spam_list BOOLEAN,
                breach_logo_path TEXT,
                breach_email TEXT,
                email_id INTEGER,
                FOREIGN KEY (email_id) REFERENCES emails (email_id)
            )
        """)
        
        # Crear tabla de GitHub si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS githubs (
                github_id INTEGER PRIMARY KEY AUTOINCREMENT,
                github_url TEXT NOT NULL,
                employee_id INTEGER,
                FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
            )
        """)
        
        # Crear tabla de Twitter si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS twitters (
                twitter_id INTEGER PRIMARY KEY AUTOINCREMENT,
                twitter_url TEXT NOT NULL,
                employee_id INTEGER,
                FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
            )
        """)
        
        # Crear tabla de teléfonos si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS phones (
                phone_id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT NOT NULL,
                employee_id INTEGER,
                FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
            )
        """)
        
        # Crear tabla de sitios web si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS websites (
                website_id INTEGER PRIMARY KEY AUTOINCREMENT,
                website_url TEXT NOT NULL,
                employee_id INTEGER,
                FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
            )
        """)
        
        # Crear tabla de secretos si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS secrets_repos (
                secret_id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_url TEXT NOT NULL,
                secret_type TEXT NOT NULL,
                secret_value TEXT NOT NULL,
                file_path TEXT,
                commit_hash TEXT,
                commit_date TEXT,
                found_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                employee_id INTEGER,
                company_id INTEGER,
                FOREIGN KEY (employee_id) REFERENCES employees (employee_id),
                FOREIGN KEY (company_id) REFERENCES companies (company_id)
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_profiles (
                profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                url TEXT,
                exists_flag BOOLEAN DEFAULT 1,
                email_recovery TEXT,
                phone_recovery TEXT,
                email_id INTEGER,
                employee_id INTEGER,
                FOREIGN KEY (email_id) REFERENCES emails (email_id),
                FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
            )
        """)

        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_passwords_unique ON passwords(password, email_id, breach_context)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_username_passwords_unique ON username_passwords(username, password, breach_context, company_id)")

        for col, default in [('triage_status', "'pending'"), ('department', 'NULL'), ('excluded', '0')]:
            for table in ['passwords', 'username_passwords', 'secrets_repos', 'employees']:
                if col == 'department' and table not in ('employees',):
                    continue
                if col == 'excluded' and table != 'employees':
                    continue
                if col == 'triage_status' and table == 'employees':
                    continue
                try:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT {default}")
                except sqlite3.OperationalError:
                    pass

        self.local_conn.commit()
        cur.close()

    def _load_global_config(self):
        """Load global settings (AI, etc.) from config file on startup."""
        if not os.path.isfile(self.configfilepath):
            return
        config = configparser.RawConfigParser()
        config.read(self.configfilepath)

        if config.has_section('ai'):
            self.ai_endpoint = config.get('ai', 'endpoint', fallback=self.ai_endpoint)
            self.ai_key = config.get('ai', 'key', fallback=self.ai_key)
            self.ai_model = config.get('ai', 'model', fallback=self.ai_model)
            log.debug(f"AI config loaded: model={self.ai_model}")

        if config.has_section('clickhouse'):
            self.ch_host = config.get('clickhouse', 'host', fallback='localhost')
            self.ch_port = config.get('clickhouse', 'port', fallback='9000')
            self.ch_user = config.get('clickhouse', 'user', fallback='default')
            self.ch_passwd = config.get('clickhouse', 'passwd', fallback='')
            self.ch_dbname = config.get('clickhouse', 'dbname', fallback='credentials_db')
            self._auto_connect_clickhouse()

    def _save_config_section(self, section, values):
        """Save a section of key-value pairs to the config file."""
        config = configparser.RawConfigParser()
        config.read(self.configfilepath)
        if not config.has_section(section):
            config.add_section(section)
        for k, v in values.items():
            config.set(section, k, v)
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(self.configfilepath, 'w') as f:
            config.write(f)

    def _auto_connect_clickhouse(self):
        """Try to connect to ClickHouse using saved config. Fails silently."""
        try:
            self.leaks_conn = clickhouse_driver.Client(
                host=self.ch_host,
                port=int(self.ch_port),
                user=self.ch_user,
                password=self.ch_passwd,
            )
            self.leaks_conn.execute('SELECT 1')
            self._ensure_credentials_db()
            log.debug(f"ClickHouse auto-connected to {self.ch_host}:{self.ch_port}")
        except Exception:
            self.leaks_conn = None

    def _ensure_credentials_db(self):
        """Create the credentials database and table if they don't exist."""
        if not self.leaks_conn:
            return
        try:
            self.leaks_conn.execute(f'CREATE DATABASE IF NOT EXISTS {self.ch_dbname}')
            self.leaks_conn.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.ch_dbname}.credentials (
                    mail_username String,
                    mail_domain String,
                    mail_tld String,
                    password String,
                    uri_subdomain String,
                    uri_domain String,
                    uri_tld String
                ) ENGINE = ReplacingMergeTree()
                ORDER BY (mail_username, mail_domain, mail_tld, password, uri_subdomain, uri_domain, uri_tld)
                SETTINGS index_granularity = 8192
            ''')
            self.leaks_conn.disconnect()
            self.leaks_conn = clickhouse_driver.Client(
                host=self.ch_host,
                port=int(self.ch_port),
                database=self.ch_dbname,
                user=self.ch_user,
                password=self.ch_passwd,
            )
        except Exception as e:
            log.debug(f"ClickHouse DB init: {e}")

    def __del__(self):
        """Cleanup database connections on object destruction"""
        if self.local_conn:
            self.local_conn.close()
        if self.conn:
            self.conn.close()
        if self.leaks_conn:
            self.leaks_conn.disconnect()

    def leakdb_connected(func):
        def wrapper(*args, **kwargs):
            if args[0].conn == None:
                log.warning(f"[!] Database connection required for this operation. Use '{Style.BRIGHT}{Fore.WHITE}connect_leaks{Style.RESET_ALL}' command to connect to the leaks database")
                return
            return func(*args, **kwargs)
        return wrapper

    def leaksdb_connected(func):
        def wrapper(*args, **kwargs):
            if args[0].leaks_conn == None:
                log.warning(f"Firstly connect to the leaks database with '{Style.BRIGHT}{Fore.WHITE}connect_leaks{Style.RESET_ALL}' command")
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

    def company_selected(func):
        def wrapper(*args, **kwargs):
            if args[0].company_name == '' and args[0].company_id == None:
                log.warning(f"You need to select a company with the '{Style.BRIGHT}{Fore.WHITE}select_company{Style.RESET_ALL}' command")
                return
            func(*args)
        return wrapper

    def _generate_html_report(self, filename, use_ai=False):
        """Generate a modular dashboard HTML report with tabs for each data category."""
        cur = self.local_conn.cursor()
        esc = self._html_escape

        cur.execute("""
            SELECT e.employee_id, e.name, e.title, e.profile_photo_url, e.department
            FROM employees e WHERE e.company_id = ? ORDER BY e.name
        """, (self.company_id,))
        employees = cur.fetchall()

        if not employees:
            log.info("No employees found for this company.")
            cur.close()
            return

        has_departments = any(emp['department'] for emp in employees)

        if use_ai and not has_departments:
            if self.ai_endpoint and self.ai_key and self.ai_model:
                log.info("No departments found. Running AI classification...")
                titles = [emp['title'] for emp in employees if emp['title']]
                role_to_dept = classify_roles(titles, self.ai_endpoint, self.ai_key, self.ai_model) or {}
                if role_to_dept:
                    for emp in employees:
                        if emp['title']:
                            dept = role_to_dept.get(emp['title'], 'Other')
                            cur.execute("UPDATE employees SET department = ? WHERE employee_id = ?",
                                        (dept, emp['employee_id']))
                    self.local_conn.commit()
                    cur.execute("""
                        SELECT e.employee_id, e.name, e.title, e.profile_photo_url, e.department
                        FROM employees e WHERE e.company_id = ? ORDER BY e.name
                    """, (self.company_id,))
                    employees = cur.fetchall()
                    has_departments = True
            else:
                log.warning("AI not configured. Use 'set_ai' or 'classify' command first.")

        def get_dept(emp):
            return emp['department'] or ''

        emp_data = []
        all_breaches = []
        all_email_creds = []
        all_secrets = []

        for emp in employees:
            eid = emp['employee_id']
            name = emp['name'] or ''
            title = emp['title'] or ''
            photo = emp['profile_photo_url'] or ''
            dept = get_dept(emp)

            cur.execute("SELECT email FROM emails WHERE employee_id = ?", (eid,))
            confirmed = [r['email'] for r in cur.fetchall()]
            cur.execute("SELECT email FROM potential_emails WHERE employee_id = ?", (eid,))
            potential = [r['email'] for r in cur.fetchall()]
            cur.execute("SELECT phone_number FROM phones WHERE employee_id = ?", (eid,))
            phones = [r['phone_number'] for r in cur.fetchall()]
            cur.execute("SELECT website_url FROM websites WHERE employee_id = ?", (eid,))
            websites = [r['website_url'] for r in cur.fetchall()]
            cur.execute("SELECT github_url FROM githubs WHERE employee_id = ?", (eid,))
            githubs = [r['github_url'] for r in cur.fetchall()]
            cur.execute("SELECT twitter_url FROM twitters WHERE employee_id = ?", (eid,))
            twitters = [r['twitter_url'] for r in cur.fetchall()]

            cur.execute("""
                SELECT b.breach_name, b.breach_date, em.email FROM breaches b
                INNER JOIN emails em ON b.email_id = em.email_id
                WHERE em.employee_id = ?
            """, (eid,))
            for r in cur.fetchall():
                all_breaches.append({'name': name, 'email': r['email'], 'breach': r['breach_name'], 'date': r['breach_date'] or '—'})

            cur.execute("""
                SELECT p.password, p.breach_context, em.email FROM passwords p
                INNER JOIN emails em ON p.email_id = em.email_id WHERE em.employee_id = ?
            """, (eid,))
            for r in cur.fetchall():
                all_email_creds.append({'name': name, 'identifier': r['email'], 'password': r['password'], 'context': r['breach_context'] or '', 'type': 'confirmed'})
            cur.execute("""
                SELECT p.password, p.breach_context, pe.email FROM passwords p
                INNER JOIN potential_emails pe ON p.email_id = pe.email_id WHERE pe.employee_id = ?
            """, (eid,))
            for r in cur.fetchall():
                all_email_creds.append({'name': name, 'identifier': r['email'], 'password': r['password'], 'context': r['breach_context'] or '', 'type': 'potential'})

            cur.execute("SELECT secret_type, secret_value, repo_url, file_path FROM secrets_repos WHERE employee_id = ?", (eid,))
            for r in cur.fetchall():
                all_secrets.append({'name': name, 'type': r['secret_type'], 'value': r['secret_value'] or '', 'repo': r['repo_url'] or '', 'file': r['file_path'] or ''})

            emp_data.append({
                'name': name, 'title': title, 'photo': photo, 'dept': dept,
                'confirmed': confirmed, 'potential': potential, 'phones': phones,
                'websites': websites, 'githubs': githubs, 'twitters': twitters,
                'has_breaches': bool(all_breaches and any(b['name'] == name for b in all_breaches)),
                'has_passwords': bool(all_email_creds and any(c['name'] == name for c in all_email_creds)),
                'has_secrets': bool(all_secrets and any(s['name'] == name for s in all_secrets)),
            })

        cur.execute("""
            SELECT username, password, breach_context
            FROM username_passwords WHERE company_id = ?
        """, (self.company_id,))
        username_creds = [{'username': r['username'], 'password': r['password'], 'context': r['breach_context'] or ''} for r in cur.fetchall()]

        total_emp = len(emp_data)
        total_emails = sum(1 for e in emp_data if e['confirmed'] or e['potential'])
        total_breaches = len(all_breaches)
        total_email_creds = len(all_email_creds)
        total_user_creds = len(username_creds)
        total_secrets = len(all_secrets)
        unique_breach_names = len(set(b['breach'] for b in all_breaches))
        dept_set = sorted(set(e['dept'] for e in emp_data if e['dept']))

        # --- Tab 1: Overview ---
        findings_html = ''
        if all_email_creds or username_creds:
            findings_html += f'''<div class="finding finding-critical">
                <div class="finding-icon">!</div>
                <div><div class="finding-title">{total_email_creds + total_user_creds} leaked credentials found</div>
                <div class="finding-desc">{total_email_creds} matched by email, {total_user_creds} matched by username across ClickHouse leak database.</div></div></div>'''
        if all_secrets:
            findings_html += f'''<div class="finding finding-high">
                <div class="finding-icon">!</div>
                <div><div class="finding-title">{total_secrets} secrets exposed in repositories</div>
                <div class="finding-desc">Secrets found via gitleaks scan in employee GitHub/GitLab repositories.</div></div></div>'''
        if all_breaches:
            findings_html += f'''<div class="finding finding-medium">
                <div class="finding-icon">i</div>
                <div><div class="finding-title">{total_breaches} breach records across {unique_breach_names} known breaches</div>
                <div class="finding-desc">Employee emails found in public data breaches via HaveIBeenPwned.</div></div></div>'''
        if not findings_html:
            findings_html = '<p class="empty-state">No critical findings yet. Run find_passwords, find_breaches, or find_secrets to populate this section.</p>'

        overview_tab = f'''<div class="tab-pane active" id="tab-overview">
            <div class="metrics-grid">
                <div class="metric-card"><div class="metric-value">{total_emp}</div><div class="metric-label">Employees</div></div>
                <div class="metric-card"><div class="metric-value">{total_emails}</div><div class="metric-label">With Emails</div></div>
                <div class="metric-card accent-red"><div class="metric-value">{total_breaches}</div><div class="metric-label">Breach Records</div></div>
                <div class="metric-card accent-orange"><div class="metric-value">{total_email_creds + total_user_creds}</div><div class="metric-label">Leaked Credentials</div></div>
                <div class="metric-card accent-purple"><div class="metric-value">{total_secrets}</div><div class="metric-label">Secrets Found</div></div>
                {'<div class="metric-card accent-cyan"><div class="metric-value">' + str(len(dept_set)) + '</div><div class="metric-label">Departments</div></div>' if dept_set else ''}
            </div>
            <div class="panel">
                <h2 class="panel-title">Key Findings</h2>
                <div class="findings-list">{findings_html}</div>
            </div>
        </div>'''

        # --- Tab 2: Profiling ---
        cards_by_dept = {}
        for e in emp_data:
            dept_key = e['dept'] or '_ungrouped'
            photo_html = f'<img src="{esc(e["photo"])}" alt="{esc(e["name"])}" />' if e['photo'] else '<div class="no-photo"><svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="#484f58" stroke-width="1.5"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 4-7 8-7s8 3 8 7"/></svg></div>'

            contact_items = ''
            for em in e['confirmed']:
                contact_items += f'<li class="contact-email"><span class="contact-label">Email</span><span class="contact-value confirmed">{esc(em)}</span></li>'
            for em in e['potential']:
                contact_items += f'<li class="contact-email"><span class="contact-label">Potential</span><span class="contact-value potential">{esc(em)}</span></li>'
            for ph in e['phones']:
                contact_items += f'<li><span class="contact-label">Phone</span><span class="contact-value">{esc(ph)}</span></li>'
            for w in e['websites']:
                contact_items += f'<li><span class="contact-label">Web</span><a href="{esc(w)}" target="_blank" class="contact-value link">{esc(w)}</a></li>'
            for g in e['githubs']:
                contact_items += f'<li><span class="contact-label">GitHub</span><a href="{esc(g)}" target="_blank" class="contact-value link github-link">{esc(g)}</a></li>'
            for t in e['twitters']:
                contact_items += f'<li><span class="contact-label">Twitter</span><a href="{esc(t)}" target="_blank" class="contact-value link">{esc(t)}</a></li>'

            indicators = ''
            if e['has_breaches']:
                indicators += '<span class="indicator ind-breach" title="Breached">B</span>'
            if e['has_passwords']:
                indicators += '<span class="indicator ind-cred" title="Leaked credentials">C</span>'
            if e['has_secrets']:
                indicators += '<span class="indicator ind-secret" title="Secrets in repos">S</span>'

            card = f'''<div class="profile-card" data-name="{esc(e['name'].lower())}" data-role="{esc(e['title'].lower())}" data-dept="{esc(e['dept'].lower())}">
                <div class="profile-header">
                    <div class="profile-photo">{photo_html}</div>
                    <div class="profile-info">
                        <h3>{esc(e['name'])}</h3>
                        <p class="profile-role">{esc(e['title'])}</p>
                        {f'<span class="dept-tag">{esc(e["dept"])}</span>' if e['dept'] else ''}
                    </div>
                    <div class="profile-indicators">{indicators}</div>
                </div>
                {'<ul class="contact-list">' + contact_items + '</ul>' if contact_items else '<p class="empty-state small">No contact information found.</p>'}
            </div>'''
            cards_by_dept.setdefault(dept_key, []).append(card)

        if has_departments:
            sorted_depts = sorted(d for d in cards_by_dept if d != '_ungrouped')
            if '_ungrouped' in cards_by_dept:
                sorted_depts.append('_ungrouped')
            dept_buttons = '<button class="dept-filter active" data-dept="all">All</button>'
            for d in sorted_depts:
                label = d if d != '_ungrouped' else 'Uncategorized'
                dept_buttons += f'<button class="dept-filter" data-dept="{esc(d.lower())}">{esc(label)} ({len(cards_by_dept[d])})</button>'
            dept_filter_bar = f'<div class="dept-filter-bar">{dept_buttons}</div>'
            profiling_grid = ''
            for d in sorted_depts:
                label = d if d != '_ungrouped' else 'Uncategorized'
                profiling_grid += f'<div class="dept-group" data-dept-group="{esc(d.lower())}"><h3 class="dept-group-title">{esc(label)}<span class="badge">{len(cards_by_dept[d])}</span></h3><div class="profiles-grid">{"".join(cards_by_dept[d])}</div></div>'
        else:
            dept_filter_bar = ''
            all_cards = []
            for cards in cards_by_dept.values():
                all_cards.extend(cards)
            profiling_grid = f'<div class="profiles-grid">{"".join(all_cards)}</div>'

        profiling_tab = f'''<div class="tab-pane" id="tab-profiling">
            <div class="tab-toolbar">
                <input type="text" class="search-input" id="profiling-search" placeholder="Search by name, role or department..." />
                {dept_filter_bar}
            </div>
            <div id="profiling-content">{profiling_grid}</div>
        </div>'''

        # --- Tab 3: Breaches ---
        if all_breaches:
            breach_rows = ''
            for b in sorted(all_breaches, key=lambda x: x['breach']):
                breach_rows += f'<tr><td>{esc(b["name"])}</td><td class="mono">{esc(b["email"])}</td><td>{esc(b["breach"])}</td><td>{esc(b["date"])}</td></tr>'
            breaches_table = f'''<div class="panel"><h2 class="panel-title">Breach Records <span class="badge">{total_breaches}</span></h2>
                <div class="table-toolbar"><input type="text" class="search-input" id="breach-search" placeholder="Filter breaches..." /></div>
                <div class="table-wrap"><table class="data-table" id="breach-table">
                <thead><tr><th>Employee</th><th>Email</th><th>Breach</th><th>Date</th></tr></thead>
                <tbody>{breach_rows}</tbody></table></div></div>'''
        else:
            breaches_table = '<div class="panel"><p class="empty-state">No breach records found. Use the HIBP plugin with find_breaches to check employee emails.</p></div>'

        breaches_tab = f'<div class="tab-pane" id="tab-breaches">{breaches_table}</div>'

        # --- Tab 4: Credentials ---
        if all_email_creds:
            cred_rows = ''
            for c in all_email_creds:
                type_class = 'confirmed' if c['type'] == 'confirmed' else 'potential'
                cred_rows += f'<tr><td>{esc(c["name"])}</td><td class="mono {type_class}">{esc(c["identifier"])}</td><td class="mono pwd">{esc(c["password"])}</td><td class="ctx">{esc(c["context"])}</td></tr>'
            email_creds_html = f'''<div class="panel"><h2 class="panel-title">Credentials by Email <span class="badge">{total_email_creds}</span></h2>
                <div class="table-toolbar"><input type="text" class="search-input" id="cred-email-search" placeholder="Filter by email, employee..." /></div>
                <div class="table-wrap"><table class="data-table" id="cred-email-table">
                <thead><tr><th>Employee</th><th>Email</th><th>Password</th><th>Leak Source</th></tr></thead>
                <tbody>{cred_rows}</tbody></table></div></div>'''
        else:
            email_creds_html = '<div class="panel"><p class="empty-state">No email-based credentials found. Use find_passwords only_emails or find_all.</p></div>'

        if username_creds:
            user_rows = ''
            for c in username_creds:
                user_rows += f'<tr><td class="mono">{esc(c["username"])}</td><td class="mono pwd">{esc(c["password"])}</td><td class="ctx">{esc(c["context"])}</td></tr>'
            user_creds_html = f'''<div class="panel"><h2 class="panel-title">Credentials by Username <span class="badge">{total_user_creds}</span></h2>
                <p class="panel-desc">Found by searching usernames (without domain) across the ClickHouse leak database. May include false positives for common usernames.</p>
                <div class="table-toolbar"><input type="text" class="search-input" id="cred-user-search" placeholder="Filter by username..." /></div>
                <div class="table-wrap"><table class="data-table" id="cred-user-table">
                <thead><tr><th>Username</th><th>Password</th><th>Leak Source</th></tr></thead>
                <tbody>{user_rows}</tbody></table></div></div>'''
        else:
            user_creds_html = '<div class="panel"><p class="empty-state">No username-based credentials found. Use find_passwords only_usernames or find_all.</p></div>'

        credentials_tab = f'<div class="tab-pane" id="tab-credentials">{email_creds_html}{user_creds_html}</div>'

        # --- Tab 5: Secrets ---
        if all_secrets:
            secret_rows = ''
            for s in all_secrets:
                truncated = s['value'][:60] + '...' if len(s['value']) > 60 else s['value']
                repo_name = s['repo'].split('/')[-1] if '/' in s['repo'] else s['repo']
                secret_rows += f'<tr><td>{esc(s["name"])}</td><td><span class="secret-type">{esc(s["type"])}</span></td><td class="mono pwd">{esc(truncated)}</td><td><a href="{esc(s["repo"])}" target="_blank" class="link">{esc(repo_name)}</a></td><td class="mono ctx">{esc(s["file"])}</td></tr>'
            secrets_html = f'''<div class="panel"><h2 class="panel-title">Exposed Secrets <span class="badge">{total_secrets}</span></h2>
                <div class="table-toolbar"><input type="text" class="search-input" id="secrets-search" placeholder="Filter secrets..." /></div>
                <div class="table-wrap"><table class="data-table" id="secrets-table">
                <thead><tr><th>Employee</th><th>Type</th><th>Value</th><th>Repository</th><th>File</th></tr></thead>
                <tbody>{secret_rows}</tbody></table></div></div>'''
        else:
            secrets_html = '<div class="panel"><p class="empty-state">No secrets found. Use the GitHub plugin with run find_secrets to scan employee repositories.</p></div>'

        secrets_tab = f'<div class="tab-pane" id="tab-secrets">{secrets_html}</div>'

        ai_subtitle = ' | Grouped by department' if has_departments else ''

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EmploLeaks Report &mdash; {esc(self.company_name)}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',sans-serif;background:#0d1117;color:#c9d1d9;min-height:100vh}}
a{{color:#58a6ff;text-decoration:none}}a:hover{{text-decoration:underline}}
.mono{{font-family:'SF Mono',SFMono-Regular,Consolas,'Liberation Mono',Menlo,monospace;font-size:12px}}

/* Header */
.header{{background:linear-gradient(135deg,#161b22 0%,#1a1e2e 100%);padding:28px 40px;border-bottom:1px solid #30363d}}
.header h1{{font-size:26px;color:#f0f6fc;letter-spacing:-0.3px}}.header h1 span{{color:#f85149}}
.header .sub{{color:#8b949e;font-size:13px;margin-top:4px}}

/* Tab nav */
.tab-nav{{display:flex;gap:0;background:#161b22;border-bottom:2px solid #30363d;padding:0 40px;overflow-x:auto}}
.tab-btn{{padding:12px 20px;color:#8b949e;font-size:13px;font-weight:600;cursor:pointer;border:none;background:none;border-bottom:2px solid transparent;margin-bottom:-2px;transition:all .15s;white-space:nowrap;display:flex;align-items:center;gap:6px}}
.tab-btn:hover{{color:#c9d1d9}}.tab-btn.active{{color:#f0f6fc;border-bottom-color:#58a6ff}}
.tab-btn .cnt{{background:#30363d;color:#8b949e;padding:1px 7px;border-radius:10px;font-size:11px;font-weight:600}}
.tab-btn.active .cnt{{background:#1f6feb;color:#fff}}

/* Tab panes */
.tab-pane{{display:none;padding:24px 40px}}.tab-pane.active{{display:block}}

/* Metrics grid */
.metrics-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin-bottom:24px}}
.metric-card{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:20px;text-align:center}}
.metric-value{{font-size:32px;font-weight:700;color:#58a6ff;line-height:1}}.metric-label{{font-size:11px;color:#8b949e;text-transform:uppercase;letter-spacing:.5px;margin-top:6px}}
.accent-red .metric-value{{color:#f85149}}.accent-orange .metric-value{{color:#f0883e}}.accent-purple .metric-value{{color:#d2a8ff}}.accent-cyan .metric-value{{color:#79c0ff}}

/* Findings */
.findings-list{{display:flex;flex-direction:column;gap:10px}}
.finding{{display:flex;gap:14px;padding:14px 18px;border-radius:8px;align-items:flex-start;background:#161b22;border:1px solid #30363d}}
.finding-icon{{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;flex-shrink:0}}
.finding-critical .finding-icon{{background:#f851491a;color:#f85149;border:1px solid #f8514933}}
.finding-high .finding-icon{{background:#d2a8ff1a;color:#d2a8ff;border:1px solid #d2a8ff33}}
.finding-medium .finding-icon{{background:#f0883e1a;color:#f0883e;border:1px solid #f0883e33}}
.finding-title{{color:#f0f6fc;font-weight:600;font-size:14px}}.finding-desc{{color:#8b949e;font-size:13px;margin-top:2px}}

/* Panels */
.panel{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:24px;margin-bottom:20px}}
.panel-title{{font-size:16px;color:#f0f6fc;margin-bottom:16px;display:flex;align-items:center;gap:8px}}
.panel-desc{{color:#8b949e;font-size:13px;margin-bottom:16px;font-style:italic}}
.badge{{background:#1f6feb;color:#fff;font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600}}

/* Tables */
.table-toolbar{{margin-bottom:12px}}.table-wrap{{overflow-x:auto}}
.data-table{{width:100%;border-collapse:collapse;font-size:13px}}
.data-table th{{text-align:left;padding:10px 12px;background:#21262d;color:#8b949e;font-size:11px;text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid #30363d;position:sticky;top:0;cursor:pointer;user-select:none;white-space:nowrap}}
.data-table th:hover{{color:#c9d1d9}}
.data-table th .sort-arrow{{margin-left:4px;opacity:.4;font-size:10px}}
.data-table th.sorted .sort-arrow{{opacity:1}}
.data-table td{{padding:8px 12px;border-bottom:1px solid #21262d;vertical-align:top;word-break:break-all}}
.data-table tbody tr:hover{{background:#1c2128}}
.data-table .confirmed{{color:#79c0ff}}.data-table .potential{{color:#8b949e;font-style:italic}}
.data-table .pwd{{color:#f0883e}}.data-table .ctx{{color:#6e7681;font-size:12px}}
.secret-type{{background:#5a1a5e;color:#d2a8ff;padding:2px 6px;border-radius:4px;font-size:11px;font-weight:600}}

/* Search inputs */
.search-input{{width:100%;max-width:400px;padding:8px 14px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:13px;outline:none}}
.search-input:focus{{border-color:#58a6ff}}
.tab-toolbar{{margin-bottom:20px;display:flex;flex-direction:column;gap:12px}}

/* Profile cards */
.profiles-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:14px}}
.profile-card{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:18px;transition:border-color .15s}}
.profile-card:hover{{border-color:#484f58}}
.profile-header{{display:flex;gap:14px;align-items:center;margin-bottom:12px}}
.profile-photo img{{width:52px;height:52px;border-radius:50%;object-fit:cover;border:2px solid #30363d}}
.no-photo{{width:52px;height:52px;border-radius:50%;background:#21262d;border:2px solid #30363d;display:flex;align-items:center;justify-content:center}}
.profile-info{{flex:1;min-width:0}}
.profile-info h3{{font-size:15px;color:#f0f6fc;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.profile-role{{font-size:12px;color:#8b949e;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.dept-tag{{display:inline-block;margin-top:4px;padding:1px 8px;border-radius:10px;font-size:10px;font-weight:600;background:#272d38;color:#a5d6ff;border:1px solid #384860}}
.profile-indicators{{display:flex;gap:4px}}
.indicator{{width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700}}
.ind-breach{{background:#6e32261a;color:#f85149;border:1px solid #f8514944}}
.ind-cred{{background:#5a30001a;color:#f0883e;border:1px solid #f0883e44}}
.ind-secret{{background:#5a1a5e1a;color:#d2a8ff;border:1px solid #d2a8ff44}}
.contact-list{{list-style:none;display:flex;flex-direction:column;gap:4px}}
.contact-list li{{display:flex;gap:8px;font-size:12px;align-items:baseline}}
.contact-label{{color:#6e7681;min-width:55px;text-transform:uppercase;font-size:10px;font-weight:600;letter-spacing:.3px;flex-shrink:0;padding-top:1px}}
.contact-value{{word-break:break-all}}.contact-value.confirmed{{color:#79c0ff}}.contact-value.potential{{color:#8b949e;font-style:italic}}.contact-value.link{{color:#58a6ff}}
.contact-value.github-link{{color:#56d364}}

/* Dept groups */
.dept-group{{margin-bottom:24px}}
.dept-group-title{{font-size:17px;color:#f0f6fc;margin-bottom:12px;display:flex;align-items:center;gap:8px}}
.dept-filter-bar{{display:flex;gap:6px;flex-wrap:wrap}}
.dept-filter{{padding:5px 12px;border-radius:16px;font-size:12px;cursor:pointer;background:#21262d;border:1px solid #30363d;color:#c9d1d9;transition:all .15s}}
.dept-filter:hover{{border-color:#58a6ff;color:#f0f6fc}}.dept-filter.active{{background:#1f6feb;border-color:#1f6feb;color:#fff}}

/* Misc */
.empty-state{{color:#484f58;font-size:14px;text-align:center;padding:40px 20px;font-style:italic}}
.empty-state.small{{font-size:12px;padding:8px 0;text-align:left}}
.hidden{{display:none!important}}
@media(max-width:600px){{.tab-pane{{padding:16px}}.profiles-grid{{grid-template-columns:1fr}}.header{{padding:20px}}.tab-nav{{padding:0 16px}}}}
</style>
</head>
<body>
<div class="header">
    <h1><span>emploleaks</span> // {esc(self.company_name)}</h1>
    <p class="sub">Generated {time.strftime("%Y-%m-%d %H:%M:%S")}{ai_subtitle}</p>
</div>
<nav class="tab-nav">
    <button class="tab-btn active" data-tab="tab-overview">Overview</button>
    <button class="tab-btn" data-tab="tab-profiling">Profiling <span class="cnt">{total_emp}</span></button>
    <button class="tab-btn" data-tab="tab-breaches">Data Breaches <span class="cnt">{total_breaches}</span></button>
    <button class="tab-btn" data-tab="tab-credentials">Credentials <span class="cnt">{total_email_creds + total_user_creds}</span></button>
    <button class="tab-btn" data-tab="tab-secrets">Secrets <span class="cnt">{total_secrets}</span></button>
</nav>
{overview_tab}
{profiling_tab}
{breaches_tab}
{credentials_tab}
{secrets_tab}
<script>
/* Tab switching */
document.querySelectorAll('.tab-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.tab).classList.add('active');
    }});
}});

/* Generic table search */
function setupTableSearch(inputId, tableId) {{
    const input = document.getElementById(inputId);
    const table = document.getElementById(tableId);
    if (!input || !table) return;
    input.addEventListener('input', () => {{
        const q = input.value.toLowerCase();
        table.querySelectorAll('tbody tr').forEach(row => {{
            row.classList.toggle('hidden', q && !row.textContent.toLowerCase().includes(q));
        }});
    }});
}}
setupTableSearch('breach-search', 'breach-table');
setupTableSearch('cred-email-search', 'cred-email-table');
setupTableSearch('cred-user-search', 'cred-user-table');
setupTableSearch('secrets-search', 'secrets-table');

/* Profiling search */
const profSearch = document.getElementById('profiling-search');
if (profSearch) {{
    profSearch.addEventListener('input', () => {{
        const q = profSearch.value.toLowerCase();
        document.querySelectorAll('.profile-card').forEach(c => {{
            const match = !q || c.dataset.name.includes(q) || c.dataset.role.includes(q) || c.dataset.dept.includes(q);
            c.classList.toggle('hidden', !match);
        }});
        document.querySelectorAll('.dept-group').forEach(g => {{
            const has = g.querySelectorAll('.profile-card:not(.hidden)').length > 0;
            g.classList.toggle('hidden', !has);
        }});
    }});
}}

/* Dept filter */
document.querySelectorAll('.dept-filter').forEach(btn => {{
    btn.addEventListener('click', () => {{
        document.querySelectorAll('.dept-filter').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const dept = btn.dataset.dept;
        document.querySelectorAll('.dept-group').forEach(g => {{
            g.classList.toggle('hidden', dept !== 'all' && g.dataset.deptGroup !== dept);
        }});
    }});
}});

/* Column sorting */
document.querySelectorAll('.data-table th').forEach(th => {{
    th.innerHTML += ' <span class="sort-arrow">&#9650;</span>';
    th.addEventListener('click', () => {{
        const table = th.closest('table');
        const idx = Array.from(th.parentNode.children).indexOf(th);
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const asc = !th.classList.contains('sorted-asc');
        table.querySelectorAll('th').forEach(h => {{ h.classList.remove('sorted','sorted-asc','sorted-desc'); }});
        th.classList.add('sorted', asc ? 'sorted-asc' : 'sorted-desc');
        th.querySelector('.sort-arrow').innerHTML = asc ? '&#9650;' : '&#9660;';
        rows.sort((a, b) => {{
            const av = a.children[idx]?.textContent || '';
            const bv = b.children[idx]?.textContent || '';
            return asc ? av.localeCompare(bv) : bv.localeCompare(av);
        }});
        rows.forEach(r => tbody.appendChild(r));
    }});
}});
</script>
</body>
</html>'''

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)

        cur.close()
        log.info(f"HTML report generated: {filename}")

    @staticmethod
    def _html_escape(text):
        """Escape HTML special characters."""
        if not text:
            return ''
        return (str(text)
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#x27;'))

    @cmd2.with_argparser(parser_print)
    @company_selected
    def do_print(self, args):
        cur = self.local_conn.cursor()
        
        # Get current timestamp for filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        export_filename = None
        if args.export:
            export_filename = f"{timestamp}_{self.company_name}.csv"
            try:
                csv_file = open(export_filename, 'w', newline='', encoding='utf-8')
                csv_writer = None
            except IOError as e:
                log.error(f"Error creating CSV file: {e}")
                return

        if args.data == 'all' and args.html:
            html_filename = f"{timestamp}_{self.company_name}_report.html"
            self._generate_html_report(html_filename, use_ai=args.ai)
            cur.close()
            return

        if args.data == 'all':
            # Check if websites table exists
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='websites'")
            websites_exists = cur.fetchone() is not None
            
            # Check if secrets_repos table exists
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='secrets_repos'")
            secrets_exists = cur.fetchone() is not None
            
            # Modify query based on whether websites and secrets tables exist
            if websites_exists and secrets_exists:
                query = """
                    WITH employee_data AS (
                        SELECT 
                            e.employee_id,
                            e.name,
                            e.title,
                            em.email as confirmed_email,
                            pe.email as potential_email,
                            g.github_url,
                            t.twitter_url,
                            p.phone_number,
                            w.website_url,
                            b.breach_name,
                            sr.secret_type || ': ' || sr.secret_value as secret
                        FROM employees e
                        LEFT JOIN emails em ON e.employee_id = em.employee_id
                        LEFT JOIN potential_emails pe ON e.employee_id = pe.employee_id
                        LEFT JOIN githubs g ON e.employee_id = g.employee_id
                        LEFT JOIN twitters t ON e.employee_id = t.employee_id
                        LEFT JOIN phones p ON e.employee_id = p.employee_id
                        LEFT JOIN websites w ON e.employee_id = w.employee_id
                        LEFT JOIN breaches b ON em.email_id = b.email_id
                        LEFT JOIN secrets_repos sr ON e.employee_id = sr.employee_id
                        WHERE e.company_id = ?
                    )
                    SELECT 
                        name,
                        title,
                        GROUP_CONCAT(DISTINCT confirmed_email) as emails,
                        GROUP_CONCAT(DISTINCT potential_email) as potential_emails,
                        GROUP_CONCAT(DISTINCT github_url) as githubs,
                        GROUP_CONCAT(DISTINCT twitter_url) as twitters,
                        GROUP_CONCAT(DISTINCT phone_number) as phones,
                        GROUP_CONCAT(DISTINCT website_url) as websites,
                        GROUP_CONCAT(DISTINCT breach_name) as breaches,
                        GROUP_CONCAT(DISTINCT secret) as secrets
                    FROM employee_data
                    GROUP BY employee_id, name, title
                """
                table_fields = ["Name", "Title", "Emails", "Potential Emails", "GitHub", "Twitter", "Phone", "Websites", "Breaches", "Secrets"]
            elif websites_exists:
                query = """
                    WITH employee_data AS (
                        SELECT 
                            e.employee_id,
                            e.name,
                            e.title,
                            em.email as confirmed_email,
                            pe.email as potential_email,
                            g.github_url,
                            t.twitter_url,
                            p.phone_number,
                            w.website_url,
                            b.breach_name
                        FROM employees e
                        LEFT JOIN emails em ON e.employee_id = em.employee_id
                        LEFT JOIN potential_emails pe ON e.employee_id = pe.employee_id
                        LEFT JOIN githubs g ON e.employee_id = g.employee_id
                        LEFT JOIN twitters t ON e.employee_id = t.employee_id
                        LEFT JOIN phones p ON e.employee_id = p.employee_id
                        LEFT JOIN websites w ON e.employee_id = w.employee_id
                        LEFT JOIN breaches b ON em.email_id = b.email_id
                        WHERE e.company_id = ?
                    )
                    SELECT 
                        name,
                        title,
                        GROUP_CONCAT(DISTINCT confirmed_email) as emails,
                        GROUP_CONCAT(DISTINCT potential_email) as potential_emails,
                        GROUP_CONCAT(DISTINCT github_url) as githubs,
                        GROUP_CONCAT(DISTINCT twitter_url) as twitters,
                        GROUP_CONCAT(DISTINCT phone_number) as phones,
                        GROUP_CONCAT(DISTINCT website_url) as websites,
                        GROUP_CONCAT(DISTINCT breach_name) as breaches
                    FROM employee_data
                    GROUP BY employee_id, name, title
                """
                table_fields = ["Name", "Title", "Emails", "Potential Emails", "GitHub", "Twitter", "Phone", "Websites", "Breaches"]
            elif secrets_exists:
                query = """
                    WITH employee_data AS (
                        SELECT 
                            e.employee_id,
                            e.name,
                            e.title,
                            em.email as confirmed_email,
                            pe.email as potential_email,
                            g.github_url,
                            t.twitter_url,
                            p.phone_number,
                            b.breach_name,
                            sr.secret_type || ': ' || sr.secret_value as secret
                        FROM employees e
                        LEFT JOIN emails em ON e.employee_id = em.employee_id
                        LEFT JOIN potential_emails pe ON e.employee_id = pe.employee_id
                        LEFT JOIN githubs g ON e.employee_id = g.employee_id
                        LEFT JOIN twitters t ON e.employee_id = t.employee_id
                        LEFT JOIN phones p ON e.employee_id = p.employee_id
                        LEFT JOIN breaches b ON em.email_id = b.email_id
                        LEFT JOIN secrets_repos sr ON e.employee_id = sr.employee_id
                        WHERE e.company_id = ?
                    )
                    SELECT 
                        name,
                        title,
                        GROUP_CONCAT(DISTINCT confirmed_email) as emails,
                        GROUP_CONCAT(DISTINCT potential_email) as potential_emails,
                        GROUP_CONCAT(DISTINCT github_url) as githubs,
                        GROUP_CONCAT(DISTINCT twitter_url) as twitters,
                        GROUP_CONCAT(DISTINCT phone_number) as phones,
                        GROUP_CONCAT(DISTINCT breach_name) as breaches,
                        GROUP_CONCAT(DISTINCT secret) as secrets
                    FROM employee_data
                    GROUP BY employee_id, name, title
                """
                table_fields = ["Name", "Title", "Emails", "Potential Emails", "GitHub", "Twitter", "Phone", "Breaches", "Secrets"]
            else:
                query = """
                    WITH employee_data AS (
                        SELECT 
                            e.employee_id,
                            e.name,
                            e.title,
                            em.email as confirmed_email,
                            pe.email as potential_email,
                            g.github_url,
                            t.twitter_url,
                            p.phone_number,
                            b.breach_name
                        FROM employees e
                        LEFT JOIN emails em ON e.employee_id = em.employee_id
                        LEFT JOIN potential_emails pe ON e.employee_id = pe.employee_id
                        LEFT JOIN githubs g ON e.employee_id = g.employee_id
                        LEFT JOIN twitters t ON e.employee_id = t.employee_id
                        LEFT JOIN phones p ON e.employee_id = p.employee_id
                        LEFT JOIN breaches b ON em.email_id = b.email_id
                        WHERE e.company_id = ?
                    )
                    SELECT 
                        name,
                        title,
                        GROUP_CONCAT(DISTINCT confirmed_email) as emails,
                        GROUP_CONCAT(DISTINCT potential_email) as potential_emails,
                        GROUP_CONCAT(DISTINCT github_url) as githubs,
                        GROUP_CONCAT(DISTINCT twitter_url) as twitters,
                        GROUP_CONCAT(DISTINCT phone_number) as phones,
                        GROUP_CONCAT(DISTINCT breach_name) as breaches
                    FROM employee_data
                    GROUP BY employee_id, name, title
                """
                table_fields = ["Name", "Title", "Emails", "Potential Emails", "GitHub", "Twitter", "Phone", "Breaches"]

            # Enable GROUP_CONCAT for SQLite
            cur.execute("SELECT GROUP_CONCAT('test')")
            if cur.fetchone()[0] is None:
                # If GROUP_CONCAT is not available, create it
                self.local_conn.create_aggregate("GROUP_CONCAT", 1, GroupConcat)
            
            cur.execute(query, (self.company_id,))
            employees = cur.fetchall()
            
            if len(employees) == 0:
                log.info("No employees found for this company.")
                if args.export:
                    csv_file.close()
                return

            # Create a pretty table
            table = PrettyTable()
            table.field_names = table_fields
            table.max_width = 30  # Limit column width
            table.hrules = True   # Add horizontal lines

            # Initialize CSV writer if export is enabled
            if args.export:
                import csv
                csv_writer = csv.writer(csv_file)
                csv_writer.writerow(table_fields)

            for emp in employees:
                # Clean up None values and format lists
                row = []
                for field in table_fields:
                    field_lower = field.lower().replace(' ', '_')
                    try:
                        value = emp[field_lower] if field_lower in emp.keys() else ''
                        # For secrets, format them nicely
                        if field == "Secrets" and value:
                            secrets = value.split(',')
                            formatted_secrets = []
                            for secret in secrets:
                                if ':' in secret:
                                    type_, value_ = secret.split(':', 1)
                                    formatted_secrets.append(f"{type_.strip()}: {value_.strip()[:20]}...")
                                else:
                                    formatted_secrets.append(secret)
                            value = '\n'.join(formatted_secrets)
                        row.append(value if value is not None else '')
                    except (KeyError, IndexError):
                        row.append('')
                table.add_row(row)
                if args.export:
                    csv_writer.writerow(row)

            self.poutput(table)
            if args.export:
                csv_file.close()
                log.info(f"Data exported to {export_filename}")

        elif args.data == 'websites':
            # Check if websites table exists
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='websites'")
            if not cur.fetchone():
                log.info("Websites table not found. No websites have been stored yet.")
                if args.export:
                    csv_file.close()
                return

            cur.execute("""
                SELECT e.name, w.website_url
                FROM employees e
                INNER JOIN websites w ON e.employee_id = w.employee_id
                WHERE e.company_id = ?
            """, (self.company_id,))

            websites = cur.fetchall()

            if len(websites) == 0:
                log.info("No websites found for company employees.")
                if args.export:
                    csv_file.close()
            else:
                table = PrettyTable()
                table.field_names = ["Name", "Website"]
                table.max_width = 50
                
                if args.export:
                    import csv
                    csv_writer = csv.writer(csv_file)
                    csv_writer.writerow(["Name", "Website"])
                
                for site in websites:
                    table.add_row([site['name'], site['website_url']])
                    if args.export:
                        csv_writer.writerow([site['name'], site['website_url']])
                
                self.poutput(table)
                if args.export:
                    csv_file.close()
                    log.info(f"Data exported to {export_filename}")

        elif args.data == 'emails':
            # Get both confirmed and potential emails
            cur.execute("""
                SELECT e.name, em.email as email, 'confirmed' as type
                FROM employees e
                INNER JOIN emails em ON e.employee_id = em.employee_id 
                WHERE e.company_id = ?
                UNION ALL
                SELECT e.name, pe.email as email, 'potential' as type
                FROM employees e
                INNER JOIN potential_emails pe ON e.employee_id = pe.employee_id 
                WHERE e.company_id = ?
                ORDER BY name, type, email
            """, (self.company_id, self.company_id))

            emails = cur.fetchall()

            if len(emails) == 0:
                log.info("There are no emails for this company yet, please find some first.")
                if args.export:
                    csv_file.close()
            else:
                table = PrettyTable()
                table.field_names = ["Name", "Email", "Type"]
                table.max_width = 50
                
                if args.export:
                    import csv
                    csv_writer = csv.writer(csv_file)
                    csv_writer.writerow(["Name", "Email", "Type"])
                
                for row in emails:
                    table.add_row([row['name'], row['email'], row['type']])
                    if args.export:
                        csv_writer.writerow([row['name'], row['email'], row['type']])
                
                self.poutput(table)
                if args.export:
                    csv_file.close()
                    log.info(f"Data exported to {export_filename}")

        elif args.data == 'passwords':
            # Get passwords from both tables
            cur.execute("""
                SELECT email, password, breach_context 
                FROM emails 
                INNER JOIN passwords ON emails.email_id = passwords.email_id 
                INNER JOIN employees ON employees.employee_id = emails.employee_id 
                WHERE company_id = ?
            """, (self.company_id,))
            email_passwords = cur.fetchall()

            cur.execute("""
                SELECT email, password, breach_context 
                FROM potential_emails 
                INNER JOIN passwords ON potential_emails.email_id = passwords.email_id 
                INNER JOIN employees ON employees.employee_id = potential_emails.employee_id 
                WHERE company_id = ?
            """, (self.company_id,))
            potential_email_passwords = cur.fetchall()

            cur.execute("""
                SELECT username, password, breach_context 
                FROM username_passwords 
                WHERE company_id = ?
            """, (self.company_id,))
            username_passwords = cur.fetchall()

            all_passwords = []
            
            # Process email passwords
            for row in email_passwords:
                all_passwords.append({
                    'identifier': row['email'],
                    'password': row['password'],
                    'breach_context': row['breach_context']
                })
            
            # Process potential email passwords
            for row in potential_email_passwords:
                all_passwords.append({
                    'identifier': row['email'],
                    'password': row['password'],
                    'breach_context': row['breach_context']
                })
            
            # Process username passwords
            for row in username_passwords:
                all_passwords.append({
                    'identifier': row['username'],
                    'password': row['password'],
                    'breach_context': row['breach_context']
                })

            if len(all_passwords) == 0:
                log.info("There are no passwords for this company yet, please find some first.")
                if args.export:
                    csv_file.close()
            else:
                table = PrettyTable()
                table.field_names = ["Identifier", "Password", "Breach Context"]
                table.max_width = 30
                
                if args.export:
                    import csv
                    csv_writer = csv.writer(csv_file)
                    csv_writer.writerow(["Identifier", "Password", "Breach Context"])
                
                for row in all_passwords:
                    table_row = [
                        row['identifier'],
                        row['password'],
                        row['breach_context'] if row['breach_context'] else ''
                    ]
                    table.add_row(table_row)
                    if args.export:
                        csv_writer.writerow(table_row)
                
                self.poutput(table)
                if args.export:
                    csv_file.close()
                    log.info(f"Data exported to {export_filename}")

        elif args.data == 'breaches':
            cur.execute("""
                SELECT 
                    b.breach_email as email,
                    b.breach_name,
                    b.breach_date,
                    b.breach_description,
                    b.breach_domain,
                    b.breach_data_classes,
                    b.breach_is_verified,
                    b.breach_is_sensitive
                FROM breaches b
                INNER JOIN emails e ON b.email_id = e.email_id
                INNER JOIN employees emp ON e.employee_id = emp.employee_id
                WHERE emp.company_id = ?
                ORDER BY b.breach_email, b.breach_date DESC
            """, (self.company_id,))

            breaches = cur.fetchall()

            if len(breaches) == 0:
                log.info("No emails in the database have been breached yet.")
                if args.export:
                    csv_file.close()
            else:
                table = PrettyTable()
                table.field_names = ["Email", "Breach Name", "Date", "Domain", "Data Classes", "Verified", "Sensitive"]
                table.max_width = 30

                if args.export:
                    import csv
                    csv_writer = csv.writer(csv_file)
                    csv_writer.writerow(["Email", "Breach Name", "Date", "Domain", "Data Classes", "Verified", "Sensitive", "Description"])
                
                for breach in breaches:
                    data_classes = json.loads(breach['breach_data_classes']) if breach['breach_data_classes'] else []
                    data_classes_str = ", ".join(data_classes) if data_classes else "N/A"
                    
                    table_row = [
                        breach['email'],
                        breach['breach_name'],
                        breach['breach_date'] or "Unknown",
                        breach['breach_domain'] or "N/A",
                        data_classes_str,
                        "Yes" if breach['breach_is_verified'] else "No",
                        "Yes" if breach['breach_is_sensitive'] else "No"
                    ]
                    table.add_row(table_row)
                    
                    if args.export:
                        csv_writer.writerow(table_row + [breach['breach_description'] or ""])
                
                self.poutput(table)
                if args.export:
                    csv_file.close()
                    log.info(f"Data exported to {export_filename}")

        elif args.data == 'gits':
            cur.execute("""
                SELECT name, github_url 
                FROM employees 
                INNER JOIN githubs ON employees.employee_id = githubs.employee_id 
                WHERE company_id = ?
            """, (self.company_id,))

            names_gits = cur.fetchall()

            if len(names_gits) == 0:
                log.info("There are no GitHub/GitLab accounts for company employees.")
                if args.export:
                    csv_file.close()
            else:
                if args.export:
                    import csv
                    csv_writer = csv.writer(csv_file)
                    csv_writer.writerow(["Name", "GitHub URL"])
                
                for name_git in names_gits:
                    print(f"{name_git['name']} : {name_git['github_url']}")
                    if args.export:
                        csv_writer.writerow([name_git['name'], name_git['github_url']])
                
                if args.export:
                    csv_file.close()
                    log.info(f"Data exported to {export_filename}")

        elif args.data == 'phones':
            cur.execute("""
                SELECT name, phone_number 
                FROM employees 
                INNER JOIN phones ON employees.employee_id = phones.employee_id 
                WHERE company_id = ?
            """, (self.company_id,))

            names_phones = cur.fetchall()

            if len(names_phones) == 0:
                log.info("There are no phone numbers for company employees.")
                if args.export:
                    csv_file.close()
            else:
                if args.export:
                    import csv
                    csv_writer = csv.writer(csv_file)
                    csv_writer.writerow(["Name", "Phone Number"])
                
                for name_phone in names_phones:
                    print(f"{name_phone['name']} : {name_phone['phone_number']}")
                    if args.export:
                        csv_writer.writerow([name_phone['name'], name_phone['phone_number']])
                
                if args.export:
                    csv_file.close()
                    log.info(f"Data exported to {export_filename}")

        elif args.data == 'twitters':
            cur.execute("""
                SELECT name, twitter_url 
                FROM employees 
                INNER JOIN twitters ON employees.employee_id = twitters.employee_id 
                WHERE company_id = ?
            """, (self.company_id,))

            names_twitters = cur.fetchall()

            if len(names_twitters) == 0:
                log.info("There are no Twitter accounts for company employees.")
                if args.export:
                    csv_file.close()
            else:
                if args.export:
                    import csv
                    csv_writer = csv.writer(csv_file)
                    csv_writer.writerow(["Name", "Twitter URL"])
                
                for name_twitter in names_twitters:
                    print(f"{name_twitter['name']} : {name_twitter['twitter_url']}")
                    if args.export:
                        csv_writer.writerow([name_twitter['name'], name_twitter['twitter_url']])
                
                if args.export:
                    csv_file.close()
                    log.info(f"Data exported to {export_filename}")

        elif args.data == 'secrets':
            cur.execute("""
                SELECT 
                    sr.repo_url,
                    sr.secret_type,
                    sr.secret_value,
                    sr.file_path,
                    sr.commit_hash,
                    sr.commit_date,
                    e.name as employee_name
                FROM secrets_repos sr
                LEFT JOIN employees e ON sr.employee_id = e.employee_id
                WHERE sr.company_id = ?
                ORDER BY sr.found_date DESC
            """, (self.company_id,))
            
            secrets = cur.fetchall()
            
            if len(secrets) == 0:
                log.info("No secrets found for this company yet. Use 'find_secrets' to search for secrets.")
                if args.export:
                    csv_file.close()
            else:
                table = PrettyTable()
                table.field_names = ["Repository", "Type", "Secret", "File", "Commit", "Date", "Employee"]
                table.max_width = 30
                
                if args.export:
                    import csv
                    csv_writer = csv.writer(csv_file)
                    csv_writer.writerow(["Repository", "Type", "Secret", "File", "Commit", "Date", "Employee"])
                
                for secret in secrets:
                    table_row = [
                        secret['repo_url'],
                        secret['secret_type'],
                        secret['secret_value'],
                        secret['file_path'],
                        secret['commit_hash'][:8] if secret['commit_hash'] else '',
                        secret['commit_date'],
                        secret['employee_name']
                    ]
                    table.add_row(table_row)
                    if args.export:
                        csv_writer.writerow(table_row)
                
                self.poutput(table)
                if args.export:
                    csv_file.close()
                    log.info(f"Data exported to {export_filename}")

        else:
            log.error("Invalid data type")

        cur.close()

    @cmd2.with_argparser(parser_listcompanies)
    def do_list_companies(self, args):
        """List all companies in the local database."""
        cur = self.local_conn.cursor()
        cur.execute("SELECT company_name FROM companies")
        
        table = [['Companies']]
        for row in cur:
            table.append([row['company_name']])
            
        if len(table) > 1:
            tab = PrettyTable(table[0])
            tab.add_rows(table[1:])
            self.poutput(tab)
        else:
            log.error("There are no companies in the database. Use 'add_company' to add one.")
            
        cur.close()

    @cmd2.with_argparser(parser_selectcompany)
    def do_select_company(self, args):
        """Select a company to work with from the local database."""
        cur = self.local_conn.cursor()
        try:
            cur.execute("SELECT company_id, company_name FROM companies WHERE company_name = ?", (args.name,))
            row = cur.fetchone()
            if row:
                self.company_id = row['company_id']
                self.company_name = row['company_name']
                
                if self.plugin_name == '':
                    self.prompt = f"{Fore.RED}emploleaks{Style.RESET_ALL}({self.company_name})> "
                else:
                    self.prompt = f"{Fore.RED}emploleaks{Style.RESET_ALL}({self.company_name})({self.plugin_name})> "
            else:
                log.error("There is no company with that name in the database.")
        except sqlite3.Error as error:
            log.error(f"Database error: {error}")
        finally:
            cur.close()

    @cmd2.with_argparser(parser_addcompany)
    def do_add_company(self, args):
        """Add a new company to the local database."""
        if not args.name:
            log.error("Company name is required")
            return
            
        cur = self.local_conn.cursor()
        try:
            cur.execute("INSERT INTO companies (company_name) VALUES (?)", (args.name,))
            self.local_conn.commit()
            log.info(f"Company '{args.name}' added successfully")
        except sqlite3.IntegrityError:
            log.error("A company with that name already exists")
            self.local_conn.rollback()
        except sqlite3.Error as error:
            log.error(f"Database error: {error}")
            self.local_conn.rollback()
        finally:
            cur.close()

    @cmd2.with_argparser(parser_use)
    @company_selected
    def do_use(self, args):
        """Use a plugin"""
        if args.plugin == 'github':
            self.plugin_name = 'github'
            self.plugin_instance = GithubModule(queue=self.queue, local_conn=self.local_conn, company_id=self.company_id)
        elif args.plugin == 'linkedin':
            self.plugin_name = 'linkedin'
            self.plugin_instance = LinkedinModule(queue=self.queue, local_conn=self.local_conn, company_id=self.company_id)
        elif args.plugin == 'hibp':
            self.plugin_name = 'hibp'
            self.plugin_instance = HaveIBeenPwnedModule(local_conn=self.local_conn, company_id=self.company_id)
        else:
            log.error("Plugin not found")
            return

        log.info(f"Using {self.plugin_name} plugin")
        self.prompt = f"{Fore.RED}emploleaks{Style.RESET_ALL}({self.company_name})({self.plugin_name})> "

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
        """Show available options and their current values for the current plugin.
        
        Usage:
            show options    Display all options and their values for the current plugin
        """
        table = self.plugin_instance.do_show(args)
        self.poutput(tabulate(table, headers='firstrow', maxcolwidths=[None, 35]))

    @plugin_activated
    def do_setopt(self, args):
        """Set an option for the current plugin.
        
        Usage:
            setopt <option_name> [value]
            
        If value is not provided, you will be prompted to enter it securely.
        The value will be saved if autosave is enabled.
        
        Example:
            setopt apikey my_api_key
            setopt username  # Will prompt for username
        """
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
                
                # Special handling for HIBP API key
                if self.plugin_name == 'hibp' and name == 'apikey':
                    self.plugin_instance.set_apikey(value)
                
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
        """Deactivate the current plugin and return to the main prompt.
        
        This command will:
        1. Clear the current plugin instance
        2. Reset the plugin name
        3. Update the prompt to show only the company name
        """
        self.prompt = f"{Fore.RED}emploleaks{Style.RESET_ALL}> "
        self.plugin_name = ''
        self.plugin_instance = None

    @plugin_activated
    def do_run(self, args):
        """Run a command from the current plugin.
        
        Available commands depend on the active plugin:
        
        LinkedIn Plugin:
            run find <company_name> <company_domain> [--email-format FORMAT]
                Search for employees at a company and generate potential emails
            run impersonate
                Use browser cookies for LinkedIn authentication
        
        GitHub Plugin:
            run stalk <github_username>
                Get detailed information about a GitHub user
            run get_repos <github_username>
                Get repositories for a GitHub user
            run find_secrets [--download-all]
                Search for secrets in company repositories
        
        HIBP Plugin:
            run find_breaches
                Search for breaches using HaveIBeenPwned API
        """
        if not self.plugin_instance:
            log.error("No plugin selected. Use 'use --plugin' first.")
            return

        if self.plugin_name == 'linkedin':
            try:
                cmd = args.arg_list[0]
            except IndexError:
                self.plugin_instance.help()
                return

            if cmd == 'find':
                if len(args.arg_list) < 3:
                    log.error("Usage: run find [linkedin company] [company domain] [--email-format FORMAT]")
                    return
                    
                company_name = args.arg_list[1]
                company_domain = args.arg_list[2]
                email_format = None
                
                # Check for email format argument
                if len(args.arg_list) > 3 and args.arg_list[3] == '--email-format':
                    try:
                        email_format = args.arg_list[4]
                    except IndexError:
                        log.error("Email format not provided after --email-format flag")
                        return
                
                # Run the find command
                company_info = self.plugin_instance.get_company_info(company_name)
                if not company_info:
                    return

                company_id, staff_count = company_info
                print(f"\n[+] Found {staff_count} employees at {company_name}")

                profiles = self.plugin_instance.do_loops(company_id, company_domain, [''], 10, email_format)
                if not profiles:
                    return
                    
                spinner = Halo(text='Listing profiles:', spinner='dots')
                spinner.start()
                
                try:
                    for i, profile in enumerate(profiles):
                        print(f"\n[{Fore.CYAN}Profile {i+1}{Style.RESET_ALL}]")
                        print(f"  {Fore.GREEN}Name:{Style.RESET_ALL}    {profile['full_name']}")
                        print(f"  {Fore.GREEN}Role:{Style.RESET_ALL}    {profile['occupation']}")

                        # First insert the employee (with search result photo if available)
                        cur = self.local_conn.cursor()
                        try:
                            sql = """INSERT INTO employees(name, title, profile_photo_url, company_id) VALUES(?, ?, ?, ?) RETURNING employee_id;"""
                            cur.execute(sql, (profile['full_name'], profile['occupation'], profile.get('search_photo_url', ''), self.company_id))
                            row = cur.fetchone()
                            if row:
                                employee_id = row['employee_id']
                            self.local_conn.commit()
                        except sqlite3.Error as error:
                            log.error(f"Database error while adding employee: {error}")
                            self.local_conn.rollback()
                            continue

                        # Siempre procesar emails potenciales
                        if email_format and profile.get('potential_emails'):
                            print(f"\n  {Fore.GREEN}Potential Emails:{Style.RESET_ALL}")
                            for email in profile['potential_emails']:
                                print(f"    [+] {email}")
                                try:
                                    sql = """INSERT INTO potential_emails(email, employee_id) VALUES(?, ?);"""
                                    cur.execute(sql, (email, employee_id))
                                    self.local_conn.commit()
                                except sqlite3.IntegrityError:
                                    self.local_conn.rollback()
                                except sqlite3.Error as error:
                                    log.error(f"Database error while adding potential email: {error}")
                                    self.local_conn.rollback()

                        # Fetch contact_info using the public_id and the existing session
                        if profile.get('public_id'):
                            contact_info = self.plugin_instance.get_contact_info(profile['public_id'])

                            if contact_info and isinstance(contact_info, dict):
                                if 'email_address' in contact_info and contact_info['email_address']:
                                    print(f"\n  {Fore.GREEN}Confirmed Email:{Style.RESET_ALL}")
                                    print(f"    [*] {contact_info['email_address']}")
                                    try:
                                        sql = """INSERT INTO emails(email, employee_id) VALUES(?, ?);"""
                                        cur.execute(sql, (contact_info['email_address'], employee_id))
                                        self.local_conn.commit()
                                    except sqlite3.IntegrityError:
                                        self.local_conn.rollback()
                                    except sqlite3.Error as error:
                                        log.error(f"Database error while adding confirmed email: {error}")
                                        self.local_conn.rollback()

                                if 'websites' in contact_info and contact_info['websites']:
                                    print(f"\n  {Fore.GREEN}Websites:{Style.RESET_ALL}")
                                    for i, website in enumerate(contact_info['websites']):
                                        url = website['url']
                                        print(f"    [{i+1}] {url}")
                                        try:
                                            sql = """INSERT INTO websites(website_url, employee_id) VALUES(?, ?);"""
                                            cur.execute(sql, (url, employee_id))
                                            self.local_conn.commit()
                                        except sqlite3.Error as error:
                                            log.error(f"Database error while adding website: {error}")
                                            self.local_conn.rollback()

                                        if 'github.com' in url or 'gitlab.com' in url:
                                            try:
                                                cur.execute(
                                                    "INSERT INTO githubs(github_url, employee_id) VALUES(?, ?)",
                                                    (url, employee_id)
                                                )
                                                self.local_conn.commit()
                                            except sqlite3.IntegrityError:
                                                pass
                                            except sqlite3.Error as error:
                                                self.local_conn.rollback()

                                if 'twitter' in contact_info and contact_info['twitter']:
                                    print(f"\n  {Fore.GREEN}Twitter Profiles:{Style.RESET_ALL}")
                                    for i, twitter in enumerate(contact_info['twitter']):
                                        print(f"    [{i+1}] @{twitter['name']}")
                                        try:
                                            sql = """INSERT INTO twitters(twitter_url, employee_id) VALUES(?, ?);"""
                                            cur.execute(sql, ('https://x.com/' + twitter['name'], employee_id))
                                            self.local_conn.commit()
                                        except sqlite3.Error as error:
                                            log.error(f"Database error while adding twitter: {error}")
                                            self.local_conn.rollback()

                                if 'phone_numbers' in contact_info and contact_info['phone_numbers']:
                                    print(f"\n  {Fore.GREEN}Phone Numbers:{Style.RESET_ALL}")
                                    for i, phone in enumerate(contact_info['phone_numbers']):
                                        print(f"    [{i+1}] {phone['number']}")
                                        try:
                                            sql = """INSERT INTO phones(phone_number, employee_id) VALUES(?, ?);"""
                                            cur.execute(sql, (phone['number'], employee_id))
                                            self.local_conn.commit()
                                        except sqlite3.Error as error:
                                            log.error(f"Database error while adding phone: {error}")
                                            self.local_conn.rollback()

                                if contact_info.get('profile_photo_url'):
                                    try:
                                        cur.execute("UPDATE employees SET profile_photo_url = ? WHERE employee_id = ?",
                                                    (contact_info['profile_photo_url'], employee_id))
                                        self.local_conn.commit()
                                    except sqlite3.Error as error:
                                        log.error(f"Database error while saving photo URL: {error}")
                                        self.local_conn.rollback()

                        print(f"\n[+] Profile processed successfully!")

                except KeyboardInterrupt:
                    spinner.stop()
                finally:
                    spinner.stop()

            elif cmd == 'impersonate':
                log.info("Using cookies from the browser")
                self.plugin_instance.impersonate()

        elif self.plugin_name == 'github':
            try:
                cmd = args.arg_list[0]
            except IndexError:
                self.plugin_instance.help()
                return

            if cmd == 'stalk':
                if len(args.arg_list) < 2:
                    log.error("Usage: run stalk <github_username>")
                    return
                self.plugin_instance.stalk(args.arg_list[1])
            elif cmd == 'get_repos':
                if len(args.arg_list) < 2:
                    log.error("Usage: run get_repos <github_username>")
                    return
                self.plugin_instance.get_repos(args.arg_list[1])
            elif cmd == 'find_secrets':
                download_all = '--download-all' in args.arg_list
                self.plugin_instance.find_secrets(download_all=download_all)
            else:
                log.error(f"Unknown command: {cmd}")
                self.plugin_instance.help()
  
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

        elif self.plugin_name == 'hibp':
            try:
                cmd = args.arg_list[0]
            except IndexError:
                self.plugin_instance.help()
                return

            if cmd == 'find_breaches':
                # Recreate breaches table with new structure
                cur = self.local_conn.cursor()
                try:
                    # Drop existing table
                    cur.execute("DROP TABLE IF EXISTS breaches")
                    # Create new table with updated structure
                    cur.execute("""
                        CREATE TABLE breaches (
                            breach_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            breach_name TEXT NOT NULL,
                            breach_date TEXT,
                            breach_description TEXT,
                            breach_domain TEXT,
                            breach_data_classes TEXT,
                            breach_is_verified BOOLEAN,
                            breach_is_fabricated BOOLEAN,
                            breach_is_sensitive BOOLEAN,
                            breach_is_retired BOOLEAN,
                            breach_is_spam_list BOOLEAN,
                            breach_logo_path TEXT,
                            breach_email TEXT,
                            email_id INTEGER,
                            FOREIGN KEY (email_id) REFERENCES emails (email_id)
                        )
                    """)
                    self.local_conn.commit()
                    log.info("Breaches table recreated with new structure")
                except sqlite3.Error as e:
                    log.error(f"Error recreating breaches table: {str(e)}")
                    self.local_conn.rollback()
                    return
                finally:
                    cur.close()

                self.plugin_instance.find_breaches()
            else:
                log.error(f"Unknown command: {cmd}")
                self.plugin_instance.help()

        else:
            log.critical("Not implemented yet...")
        
    @cmd2.with_argparser(autosave_options)       
    def do_autosave(self, args):
        """Enable or disable automatic saving of plugin configurations to config file.
        
        Usage:
            autosave --enable    Enable automatic saving of plugin configurations
            autosave --disable   Disable automatic saving of plugin configurations
        """
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
        """Enable or disable automatic loading of plugin configurations from config file.
        
        Usage:
            autoload --enable    Enable automatic loading of plugin configurations
            autoload --disable   Disable automatic loading of plugin configurations
        """
        if args.enable:
            self.autoload = True
        elif args.disable:
            self.autoload = False

        log.info("autoload " + ('enabled' if self.autoload else 'disabled'))

    @cmd2.with_argparser(create_db_parser)
    def do_create_db(self, args):
        """Create and initialize a ClickHouse database for storing leaked credentials.
        
        This command will:
        1. Create a new ClickHouse database
        2. Create the necessary table structure
        3. Optionally import credential data from files
        
        The credentials table structure is:
        - mail_username: Username part of the email
        - mail_domain: Domain part of the email
        - mail_tld: Top-level domain of the email
        - password: The leaked password
        - uri_subdomain: Subdomain where the leak was found (optional)
        - uri_domain: Domain where the leak was found
        - uri_tld: TLD where the leak was found

        Expected file format for credential data:
        email:password:url
        Example: user@domain.com:password123:subdomain.example.com
        """
        log.warning('Creating the ClickHouse database for leaked credentials')
        
        def parse_url(url):
            """Parse URL into subdomain, domain, and tld components."""
            try:
                # Remove protocol if present
                url = url.replace('http://', '').replace('https://', '')
                # Remove path and query parameters
                url = url.split('/')[0]
                
                parts = url.split('.')
                if len(parts) < 2:
                    return '', url, ''
                    
                tld = parts[-1]
                domain = parts[-2]
                subdomain = '.'.join(parts[:-2]) if len(parts) > 2 else ''
                
                return subdomain, domain, tld
            except Exception as e:
                log.error(f"Error parsing URL {url}: {str(e)}")
                return '', '', ''

        try:
            # First connect to default database to create our database
            conn = clickhouse_driver.Client(
                host=args.host,
                port=int(args.port),
                user=args.user,
                password=args.passwd,
                secure=args.secure
            )
            
            # Create database if it doesn't exist
            conn.execute(f'CREATE DATABASE IF NOT EXISTS {args.dbname}')
            log.info(f"Database {args.dbname} created successfully")
            
            # Create user if it doesn't exist
            conn.execute(f"CREATE USER IF NOT EXISTS {args.user} IDENTIFIED WITH plaintext_password BY '{args.passwd}'")
            log.info(f"User {args.user} created successfully")
            
            # Grant privileges
            conn.execute(f'GRANT ALL ON {args.dbname}.* TO {args.user}')
            log.info(f"Privileges granted to {args.user}")
            
            # Now connect to our new database
            self.leaks_conn = clickhouse_driver.Client(
                host=args.host,
                port=int(args.port),
                database=args.dbname,
                user=args.user,
                password=args.passwd,
                secure=args.secure
            )
            
            # Create the credentials table with proper structure
            self.leaks_conn.execute('''
                CREATE TABLE IF NOT EXISTS credentials (
                    mail_username String,
                    mail_domain String,
                    mail_tld String,
                    password String,
                    uri_subdomain String,
                    uri_domain String,
                    uri_tld String
                ) ENGINE = ReplacingMergeTree()
                ORDER BY (mail_username, mail_domain, mail_tld, password, uri_subdomain, uri_domain, uri_tld)
                SETTINGS index_granularity = 8192
            ''')
            log.info("Credentials table created successfully")
            
            # Import data if a directory is provided
            if args.import_data:
                if not os.path.isdir(args.import_data):
                    log.error(f"Import directory {args.import_data} does not exist")
                    return
                    
                log.info(f"Starting data import from {args.import_data}")
                log.info("Expected file format: email:password:url")
                imported_count = 0
                error_count = 0
                
                for root, _, files in os.walk(args.import_data):
                    for filename in files:
                        if filename.endswith(('.txt', '.csv', '.dat')):
                            filepath = os.path.join(root, filename)
                            log.info(f"Processing file: {filepath}")
                            
                            try:
                                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                                    # Prepare batch insert
                                    batch = []
                                    batch_size = 10000
                                    
                                    for line_num, line in enumerate(f, 1):
                                        line = line.strip()
                                        if not line or ':' not in line:
                                            continue
                                            
                                        try:
                                            # Split into email, password, and url
                                            parts = line.split(':', 2)
                                            if len(parts) != 3:
                                                log.error(f"Invalid format in {filepath} line {line_num}: {line}")
                                                error_count += 1
                                                continue
                                                
                                            email, password, url = parts
                                            
                                            # Parse email components
                                            try:
                                                username, domain = email.split('@')
                                                domain_parts = domain.split('.')
                                                tld = domain_parts[-1]
                                                domain = '.'.join(domain_parts[:-1])
                                            except ValueError:
                                                log.error(f"Invalid email format in {filepath} line {line_num}: {email}")
                                                error_count += 1
                                                continue
                                            
                                            # Parse URL components
                                            uri_subdomain, uri_domain, uri_tld = parse_url(url)
                                            if not uri_domain:  # If URL parsing failed, use email domain
                                                uri_domain = domain
                                                uri_tld = tld
                                            
                                            # Add to batch
                                            batch.append((
                                                username,
                                                domain,
                                                tld,
                                                password,
                                                uri_subdomain,
                                                uri_domain,
                                                uri_tld
                                            ))
                                            
                                            # Insert batch when it reaches the size limit
                                            if len(batch) >= batch_size:
                                                self.leaks_conn.execute(
                                                    'INSERT INTO credentials (mail_username, mail_domain, mail_tld, password, uri_subdomain, uri_domain, uri_tld) VALUES',
                                                    batch
                                                )
                                                imported_count += len(batch)
                                                batch = []
                                                log.info(f"Imported {imported_count} credentials so far...")
                                                
                                        except Exception as e:
                                            log.error(f"Error processing line {line_num} in {filepath}: {str(e)}")
                                            error_count += 1
                                            continue
                                    
                                    # Insert any remaining records
                                    if batch:
                                        self.leaks_conn.execute(
                                            'INSERT INTO credentials (mail_username, mail_domain, mail_tld, password, uri_subdomain, uri_domain, uri_tld) VALUES',
                                            batch
                                        )
                                        imported_count += len(batch)
                                        
                            except Exception as e:
                                log.error(f"Error processing file {filepath}: {str(e)}")
                                continue
                
                log.info(f"""
Data import completed:
- Successfully imported: {imported_count} credentials
- Errors encountered: {error_count}

To use this database with emploleaks:
1. Connect to it using: connect_leaks --user {args.user} --passwd {args.passwd} --dbname {args.dbname} --host {args.host} --port {args.port}
2. Start searching for credentials using: find_passwords find_all

Note: If you want to import more credential data later, you can use the --import-data option
with this command again, pointing to a directory containing credential files.
""")
            
        except Exception as e:
            log.critical(f"Database creation failed: {str(e)}")
            return

    @cmd2.with_argparser(parser_deletecompany)
    def do_delete_company(self, args):
        """Delete a company and all its associated data from the local database."""
        if not args.name:
            log.error("Company name is required")
            return
            
        cur = self.local_conn.cursor()
        try:
            # First check if company exists
            cur.execute("SELECT company_id FROM companies WHERE company_name = ?", (args.name,))
            company = cur.fetchone()
            
            if not company:
                log.error(f"Company '{args.name}' not found in database")
                return
                
            company_id = company['company_id']
            
            # If this is the currently selected company, deselect it
            if self.company_id == company_id:
                self.company_id = None
                self.company_name = ''
                self.prompt = f"{Fore.RED}emploleaks{Style.RESET_ALL}> "
            
            # Delete all associated data (using foreign key constraints)
            cur.execute("DELETE FROM companies WHERE company_id = ?", (company_id,))
            self.local_conn.commit()
            
            log.info(f"Company '{args.name}' and all associated data have been deleted")
            
        except sqlite3.Error as error:
            log.error(f"Database error: {error}")
            self.local_conn.rollback()
        finally:
            cur.close()

    @cmd2.with_argparser(parser_find_breaches)
    @plugin_activated
    @company_selected
    def do_find_breaches(self, args):
        """Search for breaches in all company emails using HaveIBeenPwned API."""
        if self.plugin_name != 'hibp':
            log.error("This command is only available in the HIBP plugin. Use 'use --plugin hibp' first.")
            return

        # Recreate breaches table with new structure
        cur = self.local_conn.cursor()
        try:
            # Drop existing table
            cur.execute("DROP TABLE IF EXISTS breaches")
            # Create new table with updated structure
            cur.execute("""
                CREATE TABLE breaches (
                    breach_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    breach_name TEXT NOT NULL,
                    breach_date TEXT,
                    breach_description TEXT,
                    breach_domain TEXT,
                    breach_data_classes TEXT,
                    breach_is_verified BOOLEAN,
                    breach_is_fabricated BOOLEAN,
                    breach_is_sensitive BOOLEAN,
                    breach_is_retired BOOLEAN,
                    breach_is_spam_list BOOLEAN,
                    breach_logo_path TEXT,
                    breach_email TEXT,
                    email_id INTEGER,
                    FOREIGN KEY (email_id) REFERENCES emails (email_id)
                )
            """)
            self.local_conn.commit()
            log.info("Breaches table recreated with new structure")
        except sqlite3.Error as e:
            log.error(f"Error recreating breaches table: {str(e)}")
            self.local_conn.rollback()
            return
        finally:
            cur.close()

        self.plugin_instance.find_breaches()

    @cmd2.with_argparser(parser_connect_leaks)
    def do_connect_leaks(self, args):
        """Connect to the ClickHouse leaks database.

        Without arguments, uses saved config from tokens.ini.
        Use --save to persist connection settings for future sessions.

        Examples:
            connect_leaks
            connect_leaks --host 192.168.1.10 --dbname my_leaks --save
        """
        host = args.host or self.ch_host
        port = args.port or self.ch_port
        user = args.user or self.ch_user
        passwd = args.passwd if args.passwd is not None else self.ch_passwd
        dbname = args.dbname or self.ch_dbname

        try:
            self.leaks_conn = clickhouse_driver.Client(
                host=host,
                port=int(port),
                user=user,
                password=passwd,
                secure=args.secure
            )
            self.leaks_conn.execute('SELECT 1')
            self.ch_host, self.ch_port = host, port
            self.ch_user, self.ch_passwd, self.ch_dbname = user, passwd, dbname
            self._ensure_credentials_db()
            log.info(f"Connected to ClickHouse {dbname} on {host}:{port}")

            if args.save:
                self._save_config_section('clickhouse', {
                    'host': host, 'port': port, 'user': user,
                    'passwd': passwd, 'dbname': dbname,
                })
                log.info("Connection settings saved to config")

        except Exception as e:
            log.error(f"Error connecting to ClickHouse: {str(e)}")
            self.leaks_conn = None

    @leaksdb_connected
    def do_disconnect_leaks(self, args):
        """Disconnect from the ClickHouse leaks database.
        
        This command will:
        1. Close the connection to the ClickHouse database
        2. Reset the connection object to None
        """
        if self.leaks_conn:
            self.leaks_conn.disconnect()
            self.leaks_conn = None
            log.info("[+] Disconnected from leaks database")
        else:
            log.warning("[!] Not connected to any database")

    @cmd2.with_argparser(parser_import_leaks)
    def do_import_leaks(self, args):
        """Import credential leak files into ClickHouse.

        Scans a directory for leak files (txt, csv, dat, zip, gz), auto-detects
        their format, and inserts parsed credentials into the ClickHouse database.

        Examples:
            import_leaks
            import_leaks /path/to/my/leaks
            import_leaks --no-ai
        """
        if not self.leaks_conn:
            log.warning("No ClickHouse connection. Run 'connect_leaks' first or configure in tokens.ini.")
            return

        base_dir = args.directory or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'leaks_data')
        if not os.path.isdir(base_dir):
            log.error(f"Directory not found: {base_dir}")
            return

        use_ai = not args.no_ai
        ai_endpoint = self.ai_endpoint if use_ai else None
        ai_key = self.ai_key if use_ai else None
        ai_model = self.ai_model if use_ai else None

        files = list(iter_leak_files(base_dir))
        if not files:
            log.warning(f"No parseable files found in {base_dir}")
            return

        log.info(f"Found {len(files)} file(s) to process in {base_dir}")
        total_inserted = 0
        total_skipped = 0
        batch_size = 50000

        spinner = Halo(text='Importing credentials...', spinner='dots')
        spinner.start()

        for file_idx, fpath in enumerate(files, 1):
            fname = os.path.basename(fpath)
            spinner.text = f'Processing file {file_idx}/{len(files)}: {fname}'
            log.info(f"[{file_idx}/{len(files)}] Parsing: {fname}")

            batch = []
            file_count = 0
            try:
                for record in parse_file(fpath, ai_endpoint, ai_key, ai_model):
                    batch.append(record)
                    if len(batch) >= batch_size:
                        self._insert_credentials_batch(batch)
                        file_count += len(batch)
                        spinner.text = f'File {file_idx}/{len(files)}: {fname} — {file_count:,} rows...'
                        batch = []

                if batch:
                    self._insert_credentials_batch(batch)
                    file_count += len(batch)

                total_inserted += file_count
                if file_count > 0:
                    log.info(f"  Imported {file_count:,} credentials from {fname}")
                else:
                    total_skipped += 1

            except Exception as e:
                log.error(f"  Error processing {fname}: {e}")
                total_skipped += 1

        spinner.stop()

        if total_inserted > 0:
            log.info("Deduplicating credentials...")
            try:
                self.leaks_conn.execute('OPTIMIZE TABLE credentials FINAL')
                final_count = self.leaks_conn.execute('SELECT count() FROM credentials')[0][0]
                log.info(f"Import complete: {total_inserted:,} rows processed, {final_count:,} unique credentials in database")
            except Exception as e:
                log.warning(f"Deduplication pending (background): {e}")
                log.info(f"Import complete: {total_inserted:,} credentials inserted, {total_skipped} files skipped")
        else:
            log.info(f"Import complete: no new credentials found, {total_skipped} files skipped")

    def _insert_credentials_batch(self, batch):
        """Insert a batch of credential tuples into ClickHouse."""
        if not batch:
            return
        self.leaks_conn.execute(
            'INSERT INTO credentials (mail_username, mail_domain, mail_tld, '
            'password, uri_subdomain, uri_domain, uri_tld) VALUES',
            batch,
            types_check=True
        )

    @cmd2.with_argparser(parser_set_ai)
    def do_set_ai(self, args):
        """Configure AI provider for role classification in reports.

        Supports any OpenAI-compatible API:
        - Ollama (local, default): --endpoint http://localhost:11434/v1 --model llama3
        - OpenAI: --endpoint https://api.openai.com/v1 --key sk-... --model gpt-4o-mini

        Settings are automatically saved to config/tokens.ini.
        """
        self.ai_endpoint = args.endpoint
        self.ai_key = args.key
        self.ai_model = args.model
        self._save_config_section('ai', {
            'endpoint': self.ai_endpoint,
            'key': self.ai_key,
            'model': self.ai_model,
        })
        log.info(f"AI configured and saved: endpoint={self.ai_endpoint}, model={self.ai_model}")

    @cmd2.with_argparser(parser_classify)
    @company_selected
    def do_classify(self, args):
        """Classify employees into departments using AI based on their job titles.

        Requires AI to be configured (use 'set_ai' first or configure in config/tokens.ini).
        Departments are saved to the local database and will appear in the HTML report and webapp.
        Use --force to re-classify employees that already have departments assigned.
        """
        if not self.ai_endpoint or not self.ai_key or not self.ai_model:
            log.warning("AI not configured. Use 'set_ai' command first.")
            return

        cur = self.local_conn.cursor()
        if args.force:
            cur.execute("SELECT employee_id, title FROM employees WHERE company_id = ? AND title IS NOT NULL AND title != ''",
                        (self.company_id,))
        else:
            cur.execute("SELECT employee_id, title FROM employees WHERE company_id = ? AND title IS NOT NULL AND title != '' AND (department IS NULL OR department = '')",
                        (self.company_id,))

        rows = cur.fetchall()
        if not rows:
            log.info("No employees to classify (all already have departments, use --force to re-classify).")
            cur.close()
            return

        titles = [r['title'] for r in rows]
        log.info(f"Classifying {len(titles)} employees...")

        mapping = classify_roles(titles, self.ai_endpoint, self.ai_key, self.ai_model)
        if not mapping:
            log.error("AI classification failed.")
            cur.close()
            return

        count = 0
        for row in rows:
            dept = mapping.get(row['title'], 'Other')
            cur.execute("UPDATE employees SET department = ? WHERE employee_id = ?",
                        (dept, row['employee_id']))
            count += 1

        self.local_conn.commit()
        cur.close()

        depts = set(mapping.values())
        log.info(f"Classified {count} employees into {len(depts)} departments: {', '.join(sorted(depts))}")

    @cmd2.with_argparser(parser_lookup)
    @company_selected
    def do_lookup_emails(self, args):
        """Check if employee emails are registered on social media platforms using Holehe.

        By default only checks confirmed emails. Use --include-potential to also check
        generated email addresses. Use --email to check a single specific email.
        Does not alert the target email address.
        """
        cur = self.local_conn.cursor()

        if args.email:
            emails_to_check = [{'email': args.email, 'email_id': None, 'employee_id': None, 'name': 'Manual'}]
        else:
            cur.execute("""
                SELECT em.email_id, em.email, e.employee_id, e.name
                FROM emails em
                INNER JOIN employees e ON em.employee_id = e.employee_id
                WHERE e.company_id = ?
            """, (self.company_id,))
            emails_to_check = [dict(r) for r in cur.fetchall()]

            if args.include_potential:
                cur.execute("""
                    SELECT pe.email_id, pe.email, e.employee_id, e.name
                    FROM potential_emails pe
                    INNER JOIN employees e ON pe.employee_id = e.employee_id
                    WHERE e.company_id = ?
                """, (self.company_id,))
                emails_to_check.extend([dict(r) for r in cur.fetchall()])

        if not emails_to_check:
            log.info("No emails found to lookup. Run LinkedIn scraping first or use --email.")
            cur.close()
            return

        log.info(f"Looking up {len(emails_to_check)} email(s) across social platforms...")
        total_found = 0

        for i, entry in enumerate(emails_to_check, 1):
            email = entry['email']
            name = entry.get('name', '')
            log.info(f"[{i}/{len(emails_to_check)}] Checking {email} ({name})...")

            results = lookup_email_sync(email)

            for r in results:
                if not r['exists']:
                    continue
                if entry.get('employee_id') and entry.get('email_id'):
                    try:
                        cur.execute("""
                            INSERT INTO social_profiles (platform, url, exists_flag, email_recovery, phone_recovery, email_id, employee_id)
                            VALUES (?, ?, 1, ?, ?, ?, ?)
                        """, (r['platform'], r['url'], r.get('email_recovery'), r.get('phone_recovery'),
                              entry['email_id'], entry['employee_id']))
                    except sqlite3.IntegrityError:
                        pass

                total_found += 1
                recovery_info = ""
                if r.get('email_recovery'):
                    recovery_info += f" | recovery email: {r['email_recovery']}"
                if r.get('phone_recovery'):
                    recovery_info += f" | recovery phone: {r['phone_recovery']}"
                log.info(f"  [+] {r['platform']}{recovery_info}")

        self.local_conn.commit()
        cur.close()
        log.info(f"Lookup complete. Found {total_found} platform registrations.")

    @cmd2.with_argparser(parser_findpasswords)
    @leaksdb_connected
    @company_selected
    def do_find_passwords(self, args):
        """Search for leaked credentials in ClickHouse database using emails and usernames from local database."""
        if not self.leaks_conn:
            log.warning("No connection to leaks database. Use 'connect_leaks' first.")
            return

        # Clean any quoted emails before starting the search
        self._clean_quoted_emails()

        cur = self.local_conn.cursor()
        
        def search_by_username(username):
            """Search for credentials using only the username."""
            if not username:
                return

            log.info(f"Searching credentials for username: {username}")
            try:
                # Query ClickHouse for credentials using only username
                query = """
                    SELECT DISTINCT password, uri_subdomain, uri_domain, uri_tld 
                    FROM credentials FINAL
                    WHERE mail_username = %(username)s
                """
                params = {'username': username}
                
                results = self.leaks_conn.execute(query, params, settings={'log_queries': 0})
                
                if not results:
                    return

                log.info(f"Found {len(results)} credentials for username: {username}")
                # Save found credentials to local database
                for password, uri_subdomain, uri_domain, uri_tld in results:
                    try:
                        # Store the password with additional context in username_passwords table
                        context = f"{uri_subdomain}.{uri_domain}.{uri_tld}" if uri_subdomain else f"{uri_domain}.{uri_tld}"
                        sql = """
                            INSERT OR IGNORE INTO username_passwords (username, password, breach_context, company_id)
                            VALUES (?, ?, ?, ?)
                        """
                        cur.execute(sql, (username, password, context, self.company_id))
                        self.local_conn.commit()
                    except sqlite3.IntegrityError:
                        # Skip duplicates
                        self.local_conn.rollback()
                    except sqlite3.Error as e:
                        log.error(f"Database error while saving password: {str(e)}")
                        self.local_conn.rollback()

            except Exception as e:
                log.error(f"Error searching credentials for username {username}: {str(e)}")

        def search_by_email(email_id, email):
            """Search for credentials using full email address."""
            username, domain, tld = parse_email(email)
            if not all([username, domain, tld]):
                return

            log.info(f"Searching credentials for: {email}")
            try:
                # Query ClickHouse for credentials
                query = """
                    SELECT password, uri_subdomain, uri_domain, uri_tld 
                    FROM credentials FINAL
                    WHERE mail_username = %(username)s 
                    AND mail_domain = %(domain)s 
                    AND mail_tld = %(tld)s
                """
                params = {
                    'username': username,
                    'domain': domain,
                    'tld': tld
                }
                
                results = self.leaks_conn.execute(query, params, settings={'log_queries': 0})
                
                if not results:
                    return

                log.info(f"Found {len(results)} credentials for: {email}")
                # Save found credentials to local database
                for password, uri_subdomain, uri_domain, uri_tld in results:
                    try:
                        # Store the password with additional context
                        context = f"{uri_subdomain}.{uri_domain}.{uri_tld}" if uri_subdomain else f"{uri_domain}.{uri_tld}"
                        sql = """
                            INSERT OR IGNORE INTO passwords (password, email_id, breach_context)
                            VALUES (?, ?, ?)
                        """
                        cur.execute(sql, (password, email_id, context))
                        self.local_conn.commit()
                    except sqlite3.IntegrityError:
                        # Skip duplicates
                        self.local_conn.rollback()
                    except sqlite3.Error as e:
                        log.error(f"Database error while saving password: {str(e)}")
                        self.local_conn.rollback()

            except Exception as e:
                log.error(f"Error searching credentials for {email}: {str(e)}")

        def parse_email(email):
            """Parse email into username, domain, and tld components."""
            try:
                username, domain = email.split('@')
                domain_parts = domain.split('.')
                tld = domain_parts[-1]
                domain = '.'.join(domain_parts[:-1])
                return username, domain, tld
            except Exception as e:
                log.error(f"Error parsing email {email}: {str(e)}")
                return None, None, None

        # First, ensure we have the breach_context column in passwords table
        try:
            cur.execute("ALTER TABLE passwords ADD COLUMN breach_context TEXT")
            self.local_conn.commit()
        except sqlite3.OperationalError:
            # Column might already exist
            pass

        spinner = Halo(text='Searching for leaked credentials...', spinner='dots')
        spinner.start()

        # Get all usernames if needed
        if args.mode in ['find_all', 'only_usernames']:
            # 1. Get usernames from potential_emails
            cur.execute("""
                SELECT DISTINCT SUBSTR(email, 1, INSTR(email, '@') - 1) as username
                FROM potential_emails pe
                INNER JOIN employees e ON pe.employee_id = e.employee_id
                WHERE e.company_id = ?
            """, (self.company_id,))
            potential_usernames = [row['username'] for row in cur.fetchall()]

            # 2. Get usernames from confirmed emails
            cur.execute("""
                SELECT DISTINCT SUBSTR(email, 1, INSTR(email, '@') - 1) as username
                FROM emails e
                INNER JOIN employees emp ON e.employee_id = emp.employee_id
                WHERE emp.company_id = ?
            """, (self.company_id,))
            confirmed_usernames = [row['username'] for row in cur.fetchall()]

            # 3. Get usernames from Twitter URLs
            cur.execute("""
                SELECT DISTINCT SUBSTR(twitter_url, INSTR(twitter_url, 'x.com/') + 6) as username
                FROM twitters t
                INNER JOIN employees e ON t.employee_id = e.employee_id
                WHERE e.company_id = ? AND twitter_url LIKE '%x.com/%'
            """, (self.company_id,))
            twitter_usernames = [row['username'] for row in cur.fetchall()]

            # Combine all unique usernames
            all_usernames = set(potential_usernames + confirmed_usernames + twitter_usernames)
            
            # Search for credentials using each username
            for username in all_usernames:
                search_by_username(username)

        # Get and process emails if needed
        if args.mode in ['find_all', 'only_emails']:
            # Get confirmed emails
            cur.execute("""
                SELECT email_id, email 
                FROM employees 
                INNER JOIN emails ON emails.employee_id = employees.employee_id 
                WHERE company_id = ?
            """, (self.company_id,))
            ids_and_emails = cur.fetchall()

            # Get potential emails
            cur.execute("""
                SELECT email_id, email 
                FROM employees 
                INNER JOIN potential_emails ON potential_emails.employee_id = employees.employee_id 
                WHERE company_id = ?
            """, (self.company_id,))
            potential_ids_and_emails = cur.fetchall()

            if len(ids_and_emails) == 0 and len(potential_ids_and_emails) == 0:
                log.info("There are no emails for this company yet, please find some first.")
                return

            # Process confirmed emails
            for row in ids_and_emails:
                email_id = row['email_id']
                email = row['email']
                search_by_email(email_id, email)

            # Process potential emails
            for row in potential_ids_and_emails:
                email_id = row['email_id']
                email = row['email']
                search_by_email(email_id, email)

        spinner.stop()
        cur.close()

        log.info("Credential search completed. Use 'print --data passwords' to view results.")

    def _clean_quoted_emails(self):
        """Clean any emails that might have quotes in them."""
        cur = self.local_conn.cursor()
        try:
            # Clean emails in emails table
            cur.execute("""
                UPDATE emails 
                SET email = REPLACE(REPLACE(email, '"', ''), '''', '')
                WHERE email LIKE '%"%' OR email LIKE '%''%'
            """)
            
            # Clean emails in potential_emails table
            cur.execute("""
                UPDATE potential_emails 
                SET email = REPLACE(REPLACE(email, '"', ''), '''', '')
                WHERE email LIKE '%"%' OR email LIKE '%''%'
            """)
            
            self.local_conn.commit()
        except sqlite3.Error as e:
            log.error(f"Error cleaning quoted emails: {str(e)}")
            self.local_conn.rollback()
        finally:
            cur.close()

def _launch_webapp(debug=False):
    """Launch the FastAPI backend and Next.js frontend for the web admin panel."""
    import subprocess
    import signal
    import webbrowser
    import time

    webapp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'webapp')
    backend_dir = os.path.join(webapp_dir, 'backend')
    frontend_dir = os.path.join(webapp_dir, 'frontend')

    if not os.path.isdir(backend_dir) or not os.path.isdir(frontend_dir):
        print("[!] webapp/ directory not found. Make sure the webapp is set up.")
        return

    venv_python = os.path.join(backend_dir, 'venv', 'bin', 'python')
    if not os.path.isfile(venv_python):
        print("[!] Backend virtualenv not found. Run:")
        print(f"    cd {backend_dir} && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt")
        return

    node_modules = os.path.join(frontend_dir, 'node_modules')
    if not os.path.isdir(node_modules):
        print("[!] Frontend dependencies not installed. Run:")
        print(f"    cd {frontend_dir} && npm install")
        return

    procs = []

    def cleanup(sig=None, frame=None):
        print("\n[*] Shutting down webapp...")
        for p in procs:
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                p.kill()

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print(f"""
{Fore.RED}emploleaks{Style.RESET_ALL} {Fore.CYAN}webapp{Style.RESET_ALL}
    
  Backend  → http://localhost:8000  (FastAPI)
  Frontend → http://localhost:3000  (Next.js)
  API Docs → http://localhost:8000/docs

  Press Ctrl+C to stop both servers.
""")

    uvicorn_cmd = [venv_python, '-m', 'uvicorn', 'main:app', '--port', '8000', '--host', '0.0.0.0']
    if debug:
        uvicorn_cmd.append('--reload')
    backend_proc = subprocess.Popen(uvicorn_cmd, cwd=backend_dir)
    procs.append(backend_proc)

    frontend_proc = subprocess.Popen(['npm', 'run', 'dev'], cwd=frontend_dir)
    procs.append(frontend_proc)

    time.sleep(3)
    webbrowser.open('http://localhost:3000')

    try:
        backend_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='cross api tool for osint.')
    parser.add_argument('-d', '--debug', action='store_true', help='enable debug messages')
    parser.add_argument('--webapp', action='store_true', help='launch the web admin panel instead of the CLI')
    args = parser.parse_args()

    if args.debug:
        log.setLevel(logging.DEBUG)
        for handler in log.handlers:
            handler.setLevel(logging.DEBUG)

    if args.webapp:
        _launch_webapp(debug=args.debug)
    else:
        queue = []
        c = EmploLeaksCLI()
        c.queue = queue
        c.prompt = f"{Fore.RED}emploleaks{Style.RESET_ALL}> "
        c.cmdloop()
