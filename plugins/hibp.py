import requests
import time
import json
from urllib.parse import urlparse
from urllib.parse import unquote
import pyhibp
from pyhibp import pwnedpasswords as pw
from utils.logging_format import log
import sqlite3

class HaveIBeenPwnedModule:
    def __init__(self, local_conn, company_id):
        self.local_conn = local_conn
        self.company_id = company_id
        self.apikey = None
        self.options = [
            {'name': 'apikey', 'value': None, 'description': 'HaveIBeenPwned API key'},
            {'name': 'rate_limit', 'value': '2.0', 'description': 'Rate limit delay in seconds between API calls'}
        ]

    def set_apikey(self, apikey):
        """Set the HIBP API key"""
        self.apikey = apikey
        for opt in self.options:
            if opt['name'] == 'apikey':
                opt['value'] = apikey
                break

    def _insert_breach_data(self, email, breaches):
        """Insert breach data into the database"""
        if not breaches:
            return

        cur = self.local_conn.cursor()
        try:
            # Get email_id for the email
            cur.execute("""
                SELECT email_id FROM emails 
                WHERE email = ? AND employee_id IN (
                    SELECT employee_id FROM employees WHERE company_id = ?
                )
            """, (email, self.company_id))
            result = cur.fetchone()
            
            if not result:
                # Try potential_emails if not found in emails
                cur.execute("""
                    SELECT email_id FROM potential_emails 
                    WHERE email = ? AND employee_id IN (
                        SELECT employee_id FROM employees WHERE company_id = ?
                    )
                """, (email, self.company_id))
                result = cur.fetchone()
            
            if not result:
                log.warning(f"[!] Could not find email_id for {email}")
                return

            email_id = result[0]

            # Insert each breach
            for breach in breaches:
                try:
                    # Ensure all required fields exist with defaults
                    breach_data = {
                        'Name': breach.get('Name', 'Unknown'),
                        'BreachDate': breach.get('BreachDate', ''),
                        'Description': breach.get('Description', ''),
                        'Domain': breach.get('Domain', ''),
                        'DataClasses': json.dumps(breach.get('DataClasses', [])),
                        'IsVerified': breach.get('IsVerified', False),
                        'IsFabricated': breach.get('IsFabricated', False),
                        'IsSensitive': breach.get('IsSensitive', False),
                        'IsRetired': breach.get('IsRetired', False),
                        'IsSpamList': breach.get('IsSpamList', False),
                        'LogoPath': breach.get('LogoPath', ''),
                        'email': email,
                        'email_id': email_id
                    }

                    cur.execute("""
                        INSERT OR IGNORE INTO breaches (
                            breach_name, breach_date, breach_description,
                            breach_domain, breach_data_classes, breach_is_verified,
                            breach_is_fabricated, breach_is_sensitive, breach_is_retired,
                            breach_is_spam_list, breach_logo_path, breach_email,
                            email_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        breach_data['Name'],
                        breach_data['BreachDate'],
                        breach_data['Description'],
                        breach_data['Domain'],
                        breach_data['DataClasses'],
                        breach_data['IsVerified'],
                        breach_data['IsFabricated'],
                        breach_data['IsSensitive'],
                        breach_data['IsRetired'],
                        breach_data['IsSpamList'],
                        breach_data['LogoPath'],
                        breach_data['email'],
                        breach_data['email_id']
                    ))
                    self.local_conn.commit()
                    log.info(f"[+] Saved breach {breach_data['Name']} for {email}")
                except sqlite3.Error as e:
                    log.error(f"[!] Database error while saving breach: {str(e)}")
                    log.error(f"[!] Failed breach data: {json.dumps(breach_data, indent=2)}")
                    self.local_conn.rollback()
                except Exception as e:
                    log.error(f"[!] Error processing breach data: {str(e)}")
                    log.error(f"[!] Failed breach data: {json.dumps(breach_data, indent=2)}")
                    self.local_conn.rollback()
        finally:
            cur.close()

    def get_breaches_for_email(self, email):
        """Get breaches for a single email from HIBP API"""
        if not self.apikey:
            return []

        headers = {
            'hibp-api-key': self.apikey,
            'user-agent': 'EmploLeaks',
            'Accept': 'application/json'
        }

        try:
            url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}?truncateResponse=false"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 404:
                return []
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 30))
                log.warning(f"[!] Rate limit hit, waiting {retry_after} seconds...")
                time.sleep(retry_after)
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    return response.json()
                return []
            elif response.status_code == 200:
                breaches = response.json()
                # Validate breach data structure
                valid_breaches = []
                for breach in breaches:
                    if not isinstance(breach, dict):
                        log.warning(f"[!] Invalid breach data type for {email}: {type(breach)}")
                        continue
                    if 'Name' not in breach:
                        log.warning(f"[!] Breach missing 'Name' field for {email}: {breach}")
                        continue
                    valid_breaches.append(breach)
                return valid_breaches
            else:
                log.error(f"[!] Error checking {email}: HTTP {response.status_code}")
                log.error(f"[!] Response headers: {dict(response.headers)}")
                log.error(f"[!] Response body: {response.text}")
                return []
                
        except Exception as e:
            log.error(f"[!] Error checking {email}: {str(e)}")
            return []

    def find_breaches(self):
        """Find breaches for all emails in the database"""
        if not self.apikey:
            log.error("[!] No API key set. Use 'setopt apikey YOUR_API_KEY' first.")
            return

        cur = self.local_conn.cursor()
        try:
            # Get all emails for current company
            cur.execute("""
                SELECT DISTINCT e.email 
                FROM emails e
                JOIN employees emp ON e.employee_id = emp.employee_id
                WHERE emp.company_id = ?
                UNION
                SELECT DISTINCT pe.email 
                FROM potential_emails pe
                JOIN employees emp ON pe.employee_id = emp.employee_id
                WHERE emp.company_id = ?
            """, (self.company_id, self.company_id))
            
            emails = [row[0] for row in cur.fetchall()]
            if not emails:
                log.warning("[!] No emails found for current company")
                return

            log.info(f"[+] Checking breaches for {len(emails)} emails...")
            
            # Process each email
            for email in emails:
                try:
                    breaches = self.get_breaches_for_email(email)
                    if breaches:
                        log.info(f"[+] Found {len(breaches)} breaches for {email}:")
                        for breach in breaches:
                            breach_date = breach.get('BreachDate', 'Unknown date')
                            log.info(f"[+]     - {breach['Name']} ({breach_date})")
                        self._insert_breach_data(email, breaches)
                    else:
                        log.info(f"[+] No breaches found for {email}")
                    # Rate limiting
                    time.sleep(2)  # Wait 2 seconds between API calls
                except Exception as e:
                    log.error(f"[!] Error checking breaches for {email}: {str(e)}")
                    continue

            log.info("[+] Breach check completed")
            
        except Exception as e:
            log.error(f"[!] Error in find_breaches: {str(e)}")
        finally:
            cur.close()

    def help(self):
        print("plugin commands:")
        print("setopt apikey YOUR_API_KEY\tset the HaveIBeenPwned API key")
        print("setopt rate_limit SECONDS\tset the rate limit delay between API calls")
        print("run find_breaches\tcheck for breaches in all company emails")
        print("\nExample usage:")
        print("  setopt apikey YOUR_API_KEY\tset your HIBP API key")
        print("  run find_breaches\tcheck for breaches in all company emails")
        print("  print --data breaches\tview breach findings")
