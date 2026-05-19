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

# Parser for internal PostgreSQL database connection
parser_connect_leaks = cmd2.Cmd2ArgumentParser()
parser_connect_leaks.add_argument('--user',
                                   required=True,
                                   help="the ClickHouse database user")
parser_connect_leaks.add_argument('--passwd',
                                   required=True,
                                   help='the ClickHouse database password')
parser_connect_leaks.add_argument('--dbname',
                                   required=True,
                                   help="the ClickHouse database name")
parser_connect_leaks.add_argument('--host',
                                   default="localhost",
                                   help="the ClickHouse database host")
parser_connect_leaks.add_argument('--port',
                                   default="9000",
                                   help="the ClickHouse database port")
parser_connect_leaks.add_argument('--secure',
                                   action='store_true',
                                   help="use secure connection (TLS)")

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
                FOREIGN KEY (email_id) REFERENCES potential_emails (email_id)
            )
        """)
        
        # Crear tabla de contraseñas de usuarios si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS username_passwords (
                password_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                breach_context TEXT,
                company_id INTEGER,
                FOREIGN KEY (company_id) REFERENCES companies (company_id)
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

    def __del__(self):
        """Cleanup database connections on object destruction"""
        if self.local_conn:
            self.local_conn.close()
        if self.conn:
            self.conn.close()
        if self.leaks_conn:
            self.leaks_conn.disconnect()  # ClickHouse specific cleanup

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
        """Generate an interactive HTML report with employee data and profile photos."""
        cur = self.local_conn.cursor()

        cur.execute("""
            SELECT e.employee_id, e.name, e.title, e.profile_photo_url
            FROM employees e
            WHERE e.company_id = ?
            ORDER BY e.name
        """, (self.company_id,))
        employees = cur.fetchall()

        if not employees:
            log.info("No employees found for this company.")
            cur.close()
            return

        role_to_dept = {}
        departments = {}
        if use_ai:
            titles = [emp['title'] for emp in employees if emp['title']]
            role_to_dept = classify_roles(titles, self.ai_endpoint, self.ai_key, self.ai_model) or {}

        def get_dept(title):
            if not use_ai or not role_to_dept:
                return None
            return role_to_dept.get(title, 'Other')

        cards_by_dept = {}
        card_count_with_email = 0
        card_count_breached = 0

        for emp in employees:
            eid = emp['employee_id']
            name = emp['name'] or ''
            title = emp['title'] or ''
            photo = emp['profile_photo_url'] or ''
            dept = get_dept(title)

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
                SELECT b.breach_name, b.breach_date FROM breaches b
                INNER JOIN emails em ON b.email_id = em.email_id
                WHERE em.employee_id = ?
            """, (eid,))
            breaches = [f"{r['breach_name']} ({r['breach_date'] or '?'})" for r in cur.fetchall()]

            cur.execute("""
                SELECT p.password, p.breach_context FROM passwords p
                INNER JOIN emails em ON p.email_id = em.email_id
                WHERE em.employee_id = ?
            """, (eid,))
            email_pwds = cur.fetchall()
            cur.execute("""
                SELECT p.password, p.breach_context FROM passwords p
                INNER JOIN potential_emails pe ON p.email_id = pe.email_id
                WHERE pe.employee_id = ?
            """, (eid,))
            pot_pwds = cur.fetchall()
            passwords = [f"{r['password']} ({r['breach_context'] or ''})" for r in list(email_pwds) + list(pot_pwds)]

            def make_list(items, css_class=''):
                if not items:
                    return ''
                return ''.join(f'<li class="{css_class}">{self._html_escape(i)}</li>' for i in items)

            details_sections = []
            if confirmed:
                details_sections.append(f'<div class="section"><h4>Confirmed Emails</h4><ul>{make_list(confirmed, "email")}</ul></div>')
            if potential:
                details_sections.append(f'<div class="section"><h4>Potential Emails</h4><ul>{make_list(potential, "email potential")}</ul></div>')
            if phones:
                details_sections.append(f'<div class="section"><h4>Phones</h4><ul>{make_list(phones)}</ul></div>')
            if websites:
                links = ''.join(f'<li><a href="{self._html_escape(w)}" target="_blank">{self._html_escape(w)}</a></li>' for w in websites)
                details_sections.append(f'<div class="section"><h4>Websites</h4><ul>{links}</ul></div>')
            if githubs:
                links = ''.join(f'<li><a href="{self._html_escape(g)}" target="_blank">{self._html_escape(g)}</a></li>' for g in githubs)
                details_sections.append(f'<div class="section"><h4>GitHub</h4><ul>{links}</ul></div>')
            if twitters:
                links = ''.join(f'<li><a href="{self._html_escape(t)}" target="_blank">{self._html_escape(t)}</a></li>' for t in twitters)
                details_sections.append(f'<div class="section"><h4>Twitter</h4><ul>{links}</ul></div>')
            if breaches:
                details_sections.append(f'<div class="section breach"><h4>Breaches</h4><ul>{make_list(breaches, "breach")}</ul></div>')
            if passwords:
                details_sections.append(f'<div class="section breach"><h4>Leaked Passwords</h4><ul>{make_list(passwords, "password")}</ul></div>')

            details_html = ''.join(details_sections) if details_sections else '<p class="no-data">No additional data found.</p>'
            photo_html = f'<img src="{self._html_escape(photo)}" alt="{self._html_escape(name)}" />' if photo else '<div class="no-photo">No Photo</div>'

            tags_html = ''
            if dept:
                tags_html += f'<span class="tag dept">{self._html_escape(dept)}</span>'
            if confirmed:
                tags_html += '<span class="tag confirmed">Email</span>'
                card_count_with_email += 1
            if breaches:
                tags_html += '<span class="tag breached">Breached</span>'
                card_count_breached += 1
            if passwords:
                tags_html += '<span class="tag leaked">Passwords</span>'
            if githubs:
                tags_html += '<span class="tag github">GitHub</span>'

            card = f'''
            <div class="card" data-name="{self._html_escape(name.lower())}" data-role="{self._html_escape(title.lower())}" data-dept="{self._html_escape((dept or '').lower())}">
                <div class="card-header">
                    <div class="photo">{photo_html}</div>
                    <div class="info">
                        <h3>{self._html_escape(name)}</h3>
                        <p class="role">{self._html_escape(title)}</p>
                        <div class="tags">{tags_html}</div>
                    </div>
                </div>
                <div class="card-details">{details_html}</div>
            </div>'''

            dept_key = dept or '_ungrouped'
            cards_by_dept.setdefault(dept_key, []).append(card)

        total = len(employees)

        if use_ai and role_to_dept:
            sorted_depts = sorted(d for d in cards_by_dept if d != '_ungrouped')
            if '_ungrouped' in cards_by_dept:
                sorted_depts.append('_ungrouped')
            
            dept_count = len([d for d in sorted_depts if d != '_ungrouped'])
            
            dept_nav_items = []
            for d in sorted_depts:
                label = d if d != '_ungrouped' else 'Uncategorized'
                count = len(cards_by_dept[d])
                dept_nav_items.append(
                    f'<button class="dept-btn" data-dept="{self._html_escape(d.lower())}">'
                    f'{self._html_escape(label)} <span class="dept-count">{count}</span></button>'
                )
            dept_nav_items.insert(0,
                '<button class="dept-btn active" data-dept="all">'
                f'All <span class="dept-count">{total}</span></button>'
            )
            dept_nav = f'<div class="dept-nav">{"".join(dept_nav_items)}</div>'

            grid_content = ''
            for d in sorted_depts:
                label = d if d != '_ungrouped' else 'Uncategorized'
                grid_content += f'<div class="dept-section" data-dept-section="{self._html_escape(d.lower())}">'
                grid_content += f'<h2 class="dept-title">{self._html_escape(label)} <span class="dept-badge">{len(cards_by_dept[d])}</span></h2>'
                grid_content += f'<div class="grid">{"".join(cards_by_dept[d])}</div>'
                grid_content += '</div>'
        else:
            dept_nav = ''
            dept_count = 0
            all_cards = []
            for cards in cards_by_dept.values():
                all_cards.extend(cards)
            grid_content = f'<div class="grid" id="grid">{"".join(all_cards)}</div>'

        dept_stat = f'<div class="stat"><div class="num">{dept_count}</div><div class="label">Departments</div></div>' if use_ai and role_to_dept else ''

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EmploLeaks Report - {self._html_escape(self.company_name)}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; min-height: 100vh; }}
.header {{ background: linear-gradient(135deg, #161b22 0%, #1a1e2e 100%); padding: 30px 40px; border-bottom: 1px solid #30363d; }}
.header h1 {{ font-size: 28px; color: #f0f6fc; margin-bottom: 5px; }}
.header h1 span {{ color: #f85149; }}
.header .subtitle {{ color: #8b949e; font-size: 14px; }}
.stats {{ display: flex; gap: 20px; margin-top: 15px; flex-wrap: wrap; }}
.stat {{ background: #21262d; padding: 10px 18px; border-radius: 8px; border: 1px solid #30363d; }}
.stat .num {{ font-size: 22px; font-weight: 700; color: #58a6ff; }}
.stat .label {{ font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; }}
.controls {{ padding: 20px 40px; background: #161b22; border-bottom: 1px solid #30363d; }}
.search {{ width: 100%; padding: 10px 16px; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; color: #c9d1d9; font-size: 14px; outline: none; }}
.search:focus {{ border-color: #58a6ff; }}
.dept-nav {{ padding: 16px 40px; background: #0d1117; border-bottom: 1px solid #30363d; display: flex; gap: 8px; flex-wrap: wrap; }}
.dept-btn {{ background: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: 6px 14px; border-radius: 20px; font-size: 13px; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 6px; }}
.dept-btn:hover {{ border-color: #58a6ff; color: #f0f6fc; }}
.dept-btn.active {{ background: #1f6feb; border-color: #1f6feb; color: #fff; }}
.dept-count {{ background: rgba(255,255,255,0.15); padding: 1px 7px; border-radius: 10px; font-size: 11px; }}
.dept-section {{ margin-bottom: 8px; }}
.dept-title {{ font-size: 20px; color: #f0f6fc; padding: 20px 40px 8px; display: flex; align-items: center; gap: 10px; }}
.dept-badge {{ background: #1f6feb; color: #fff; font-size: 13px; padding: 2px 10px; border-radius: 12px; font-weight: 600; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 16px; padding: 12px 40px 24px; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; overflow: hidden; transition: border-color 0.2s; }}
.card:hover {{ border-color: #58a6ff; }}
.card-header {{ display: flex; gap: 16px; padding: 20px; cursor: pointer; }}
.photo img {{ width: 64px; height: 64px; border-radius: 50%; object-fit: cover; border: 2px solid #30363d; }}
.no-photo {{ width: 64px; height: 64px; border-radius: 50%; background: #21262d; border: 2px solid #30363d; display: flex; align-items: center; justify-content: center; font-size: 11px; color: #484f58; }}
.info {{ flex: 1; min-width: 0; }}
.info h3 {{ font-size: 16px; color: #f0f6fc; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.info .role {{ font-size: 13px; color: #8b949e; margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.tags {{ margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; }}
.tag {{ padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
.tag.dept {{ background: #272d38; color: #a5d6ff; border: 1px solid #384860; }}
.tag.confirmed {{ background: #0d419d; color: #79c0ff; }}
.tag.breached {{ background: #6e3226; color: #f85149; }}
.tag.leaked {{ background: #5a3000; color: #f0883e; }}
.tag.github {{ background: #1b3a2d; color: #56d364; }}
.card-details {{ display: none; padding: 0 20px 20px; border-top: 1px solid #21262d; }}
.card.open .card-details {{ display: block; padding-top: 16px; }}
.section {{ margin-bottom: 12px; }}
.section h4 {{ font-size: 12px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }}
.section ul {{ list-style: none; }}
.section li {{ font-size: 13px; padding: 3px 0; color: #c9d1d9; word-break: break-all; }}
.section li.breach {{ color: #f85149; }}
.section li.password {{ color: #f0883e; font-family: monospace; }}
.section li.email {{ color: #79c0ff; }}
.section li.potential {{ color: #8b949e; font-style: italic; }}
.section a {{ color: #58a6ff; text-decoration: none; }}
.section a:hover {{ text-decoration: underline; }}
.no-data {{ color: #484f58; font-size: 13px; font-style: italic; }}
.hidden {{ display: none !important; }}
</style>
</head>
<body>
<div class="header">
    <h1><span>emploleaks</span> // {self._html_escape(self.company_name)}</h1>
    <p class="subtitle">Generated {time.strftime("%Y-%m-%d %H:%M:%S")}{' | AI-grouped by department' if use_ai and role_to_dept else ''}</p>
    <div class="stats">
        <div class="stat"><div class="num">{total}</div><div class="label">Employees</div></div>
        {dept_stat}
        <div class="stat"><div class="num">{card_count_with_email}</div><div class="label">With Email</div></div>
        <div class="stat"><div class="num">{card_count_breached}</div><div class="label">Breached</div></div>
    </div>
</div>
<div class="controls">
    <input type="text" class="search" placeholder="Filter by name, role or department..." id="search" />
</div>
{dept_nav}
<div id="content">
{grid_content}
</div>
<script>
document.querySelectorAll('.card-header').forEach(h => {{
    h.addEventListener('click', () => h.parentElement.classList.toggle('open'));
}});
const searchInput = document.getElementById('search');
searchInput.addEventListener('input', e => {{
    const q = e.target.value.toLowerCase();
    document.querySelectorAll('.card').forEach(c => {{
        const match = c.dataset.name.includes(q) || c.dataset.role.includes(q) || (c.dataset.dept && c.dataset.dept.includes(q));
        c.classList.toggle('hidden', !match);
    }});
    document.querySelectorAll('.dept-section').forEach(s => {{
        const visible = s.querySelectorAll('.card:not(.hidden)').length;
        s.classList.toggle('hidden', visible === 0);
    }});
}});
document.querySelectorAll('.dept-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
        document.querySelectorAll('.dept-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const dept = btn.dataset.dept;
        if (dept === 'all') {{
            document.querySelectorAll('.dept-section').forEach(s => s.classList.remove('hidden'));
        }} else {{
            document.querySelectorAll('.dept-section').forEach(s => {{
                s.classList.toggle('hidden', s.dataset.deptSection !== dept);
            }});
        }}
        searchInput.value = '';
        document.querySelectorAll('.card').forEach(c => c.classList.remove('hidden'));
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

            if cmd == 'stalk':
                if len(args) < 1:
                    log.error("Usage: run stalk <github_username>")
                    return
                self.plugin_instance.stalk(args[0])
            elif cmd == 'get_repos':
                if len(args) < 1:
                    log.error("Usage: run get_repos <github_username>")
                    return
                self.plugin_instance.get_repos(args[0])
            elif cmd == 'find_secrets':
                # Check for --download-all flag
                download_all = '--download-all' in args
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
                    uri_tld String,
                    -- Add a materialized column for the full email
                    mail_full String MATERIALIZED concat(mail_username, '@', mail_domain, '.', mail_tld),
                    -- Add a materialized column for the full URI
                    uri_full String MATERIALIZED concat(
                        if(uri_subdomain != '', concat(uri_subdomain, '.'), ''),
                        uri_domain, '.', uri_tld
                    )
                ) ENGINE = MergeTree()
                ORDER BY (mail_username, mail_domain, mail_tld)
                -- Add secondary indexes for common queries
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
        """Connect to the leaks database
        Usage: connect_leaks --user <username> --passwd <password> --dbname <database> --host <hostname> [--port <port>] [--secure]
        """
        try:
            # Intentar conectar a la base de datos ClickHouse
            self.leaks_conn = clickhouse_driver.Client(
                host=args.host,
                port=int(args.port),
                database=args.dbname,
                user=args.user,
                password=args.passwd,
                secure=args.secure
            )
            # Test the connection
            self.leaks_conn.execute('SELECT 1')
            log.info(f"[+] Successfully connected to ClickHouse database {args.dbname} on {args.host}:{args.port}")
        except Exception as e:
            log.error(f"[!] Error connecting to ClickHouse database: {str(e)}")
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
                    FROM credentials 
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
                            INSERT INTO username_passwords (username, password, breach_context, company_id) 
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
                    FROM credentials 
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
                            INSERT INTO passwords (password, email_id, breach_context) 
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

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='cross api tool for osint.')
    parser.add_argument('-d', '--debug', action='store_true', help='enable debug messages')
    args = parser.parse_args()

    if args.debug:
        log.setLevel(logging.DEBUG)
        for handler in log.handlers:
            handler.setLevel(logging.DEBUG)

    queue = []

    c = EmploLeaksCLI()
    c.queue = queue
    c.prompt = f"{Fore.RED}emploleaks{Style.RESET_ALL}> "
    c.cmdloop()
