import requests
import json
import subprocess
import tempfile
import os
from datetime import datetime
from colorama import Style, Fore
from utils.logging_format import log
import sqlite3

class GithubModule:
    def __init__(self, queue=None, local_conn=None, company_id=None):
        self.options = [{
                'name': 'token',
                'value': '',
                'required': True,
                'description': "github token to request"
            }, {
                'name': 'blur',
                'value': 'yes',
                'required': True,
                'description': "get fruit over the token"    
            }, {
                'name': 'gitleaks_path',
                'value': 'gitleaks',
                'required': False,
                'description': "path to gitleaks binary (default: assumes it's in PATH)"
            }, {
                'name': 'max_repo_size',
                'value': '15',
                'required': False,
                'description': "maximum repository size in megabytes (default: 15MB)"
            }]
        self.session = requests.Session()
        self.queue = queue
        self.local_conn = local_conn
        self.company_id = company_id
        self.large_repos = []  # List to track repositories that exceed size limit

    def get_token(self):
        return self.options[0]['value']

    def do_show(self, args):
        print("Module options:\n")
        table = [['Name', 'Current Setting', 'Required', 'Description']]        
        blur = self.options[1]['value'] == 'yes'

        for opt in self.options:
            table.append([ opt['name'], opt['value'], 'yes' if opt['required'] else 'no', opt['description']])
        
        return table

    def find_mail(self, username):
        mails = []

        headers = {'Authorization': 'Bearer ' + self.options[0]['value']}
        user_url = "https://api.github.com/users/" + username
        response = self.session.get(user_url, headers=headers)
        if response.status_code == 200:
            data = json.loads(response.text)
            mails.append({'user': username, 'email': data["email"]})
        else:
            print(f"[{Fore.RED}-{Style.RESET_ALL}] Error getting the information")
            return []

        return mails

    def get_repos(self, username):
        repos_url = "https://api.github.com/users/{}/repos".format(username)

        headers = {'Authorization': 'Bearer ' + self.options[0]['value']}
        response = self.session.get(repos_url, headers=headers)
        if response.status_code == 200:
            data = json.loads(response.text)
            return data
        else:
            print(f"[{Fore.RED}-{Style.RESET_ALL} Error getting the repos")

    def _get_repo_urls_from_profile(self, profile_url):
        """Get all repository URLs from a GitHub profile URL"""
        try:
            # Extract username from profile URL
            username = profile_url.rstrip('/').split('/')[-1]
            if username.startswith('@'):
                username = username[1:]
            
            # Get repositories using GitHub API
            token = self.get_token()
            if not token:
                log.error("GitHub token not set. Use 'set token YOUR_GITHUB_TOKEN' to set it")
                return []
                
            headers = {
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            api_url = f"https://api.github.com/users/{username}/repos"
            response = self.session.get(api_url, headers=headers)
            
            if response.status_code == 200:
                repos = response.json()
                return [repo['clone_url'] for repo in repos]
            elif response.status_code == 401:
                log.error("Invalid GitHub token. Please check your token and try again")
                return []
            elif response.status_code == 404:
                log.error(f"GitHub user {username} not found")
                return []
            else:
                log.error(f"Error getting repositories for {username}: {response.status_code}")
                if response.text:
                    log.error(f"GitHub API response: {response.text}")
                return []
        except Exception as e:
            log.error(f"Error processing GitHub profile {profile_url}: {str(e)}")
            return []

    def _parse_gitleaks_output(self, output):
        """Parse Gitleaks verbose output into structured data"""
        findings = []
        current_finding = {}
        
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                if current_finding:
                    findings.append(current_finding)
                    current_finding = {}
                continue
                
            if line.startswith('Finding:'):
                if current_finding:
                    findings.append(current_finding)
                current_finding = {'finding': line.split('=', 1)[1].strip() if '=' in line else ''}
            elif line.startswith('Secret:'):
                current_finding['secret'] = line.split(':', 1)[1].strip()
            elif line.startswith('RuleID:'):
                current_finding['rule_id'] = line.split(':', 1)[1].strip()
            elif line.startswith('File:'):
                current_finding['file'] = line.split(':', 1)[1].strip()
            elif line.startswith('Line:'):
                current_finding['line'] = line.split(':', 1)[1].strip()
            elif line.startswith('Commit:'):
                current_finding['commit'] = line.split(':', 1)[1].strip()
            elif line.startswith('Author:'):
                current_finding['author'] = line.split(':', 1)[1].strip()
            elif line.startswith('Email:'):
                current_finding['email'] = line.split(':', 1)[1].strip()
            elif line.startswith('Date:'):
                current_finding['date'] = line.split(':', 1)[1].strip()
            elif line.startswith('Link:'):
                current_finding['link'] = line.split(':', 1)[1].strip()
        
        if current_finding:
            findings.append(current_finding)
            
        return findings

    def _analyze_repository(self, repo_url, employee_id, cur, download_all=False):
        """Analyze a single repository for secrets"""
        # Create a temporary directory for cloning
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Clone the repository silently
                subprocess.run(
                    ['git', 'clone', '--depth', '1', repo_url, temp_dir],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # Get repository size
                repo_size = 0
                for dirpath, _, filenames in os.walk(temp_dir):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        repo_size += os.path.getsize(fp)
                
                repo_size_mb = repo_size / (1024 * 1024)
                max_size = int(self.options[3]['value'])  # max_repo_size option
                
                if repo_size_mb > max_size and not download_all:
                    self.large_repos.append({
                        'url': repo_url,
                        'size_mb': repo_size_mb,
                        'employee_id': employee_id
                    })
                    return False  # Return False to indicate skipped repo
                
                # Create a temporary file for the report
                with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as report_file:
                    report_path = report_file.name
                
                try:
                    # Run gitleaks on the cloned repository
                    gitleaks_path = self.options[2]['value']
                    result = subprocess.run(
                        [
                            gitleaks_path, 'detect',
                            '--source', temp_dir,
                            '--verbose',
                            '--max-target-megabytes', str(max_size),
                            '--report-format', 'json',
                            '--report-path', report_path
                        ],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    
                    # Check if gitleaks found secrets
                    if result.returncode == 1 and os.path.exists(report_path):
                        try:
                            with open(report_path, 'r') as f:
                                findings = json.load(f)
                                
                            if not isinstance(findings, list):
                                findings = [findings]
                                
                            secrets_found = 0
                            for finding in findings:
                                try:
                                    cur.execute("""
                                        INSERT INTO secrets_repos (
                                            repo_url, secret_type, secret_value,
                                            file_path, commit_hash, commit_date,
                                            employee_id, company_id, line_number,
                                            author, author_email, finding_link
                                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, (
                                        repo_url,
                                        finding.get('RuleID', 'Unknown'),
                                        finding.get('Secret', ''),
                                        finding.get('File', ''),
                                        finding.get('Commit', ''),
                                        finding.get('Date', ''),
                                        employee_id,
                                        self.company_id,
                                        str(finding.get('StartLine', '')),
                                        finding.get('Author', ''),
                                        finding.get('Email', ''),
                                        finding.get('Link', '')
                                    ))
                                    self.local_conn.commit()
                                    secrets_found += 1
                                    
                                except sqlite3.Error as e:
                                    log.error(f"Database error while saving secret: {str(e)}")
                                    self.local_conn.rollback()
                            
                            if secrets_found > 0:
                                log.success(f"Found {secrets_found} secrets in {repo_url.split('/')[-1]}")
                                return True  # Return True to indicate secrets found
                                    
                        except (json.JSONDecodeError, IOError) as e:
                            log.error(f"Error processing Gitleaks report: {str(e)}")
                            
                    elif result.returncode != 0 and result.stderr.strip():
                        log.error(f"Error running gitleaks on {repo_url}: {result.stderr.strip()}")
                        
                finally:
                    try:
                        if os.path.exists(report_path):
                            os.unlink(report_path)
                    except OSError:
                        pass
                    
            except subprocess.CalledProcessError as e:
                log.error(f"Error cloning repository {repo_url}: {str(e)}")
            
            return False  # Return False if no secrets found or error occurred

    def find_secrets(self, download_all=False):
        """Search for secrets in repositories using gitleaks"""
        if not self.local_conn or not self.company_id:
            log.error("Database connection and company selection required")
            return

        # Reset large repos list
        self.large_repos = []
        
        # Ensure secrets_repos table has all needed columns
        cur = self.local_conn.cursor()
        try:
            # Add new columns if they don't exist, one at a time
            new_columns = [
                'line_number TEXT',
                'author TEXT',
                'author_email TEXT',
                'finding_link TEXT'
            ]
            
            for column_def in new_columns:
                try:
                    cur.execute(f"ALTER TABLE secrets_repos ADD COLUMN {column_def}")
                    self.local_conn.commit()
                except sqlite3.OperationalError:
                    pass

        except sqlite3.Error as e:
            log.error(f"Error adding columns to secrets_repos table: {str(e)}")
            return

        try:
            # Get all repository URLs
            cur.execute("""
                SELECT DISTINCT g.github_url, e.employee_id
                FROM githubs g
                INNER JOIN employees e ON g.employee_id = e.employee_id
                WHERE e.company_id = ?
                UNION
                SELECT DISTINCT w.website_url, e.employee_id
                FROM websites w
                INNER JOIN employees e ON w.employee_id = e.employee_id
                WHERE e.company_id = ? AND (
                    w.website_url LIKE '%github.com%' OR
                    w.website_url LIKE '%gitlab.com%' OR
                    w.website_url LIKE '%.git'
                )
            """, (self.company_id, self.company_id))
            
            repos = cur.fetchall()
            
            if not repos:
                log.info("No repositories found for this company")
                return

            total_repos = len(repos)
            log.info(f"Starting scan of {total_repos} repositories...")
            
            # Track progress
            processed = 0
            secrets_found = 0
            skipped = 0
            last_progress = 0
            
            for repo_url, employee_id in repos:
                processed += 1
                
                # Show progress every 25%
                current_progress = (processed * 100) // total_repos
                if current_progress >= last_progress + 25:
                    log.info(f"Progress: {current_progress}% ({processed}/{total_repos} repositories)")
                    last_progress = current_progress
                
                try:
                    # Check if this is a GitHub profile URL
                    if 'github.com' in repo_url and not any(repo_url.endswith(ext) for ext in ['.git', '/repos', '/projects', '/stars']):
                        profile_repos = self._get_repo_urls_from_profile(repo_url)
                        if profile_repos:
                            log.info(f"Found {len(profile_repos)} repositories in profile {repo_url.split('/')[-1]}")
                            for profile_repo in profile_repos:
                                if self._analyze_repository(profile_repo, employee_id, cur, download_all):
                                    secrets_found += 1
                                elif profile_repo in [r['url'] for r in self.large_repos]:
                                    skipped += 1
                        continue
                    
                    # If it's a direct repository URL, analyze it
                    if self._analyze_repository(repo_url, employee_id, cur, download_all):
                        secrets_found += 1
                    elif repo_url in [r['url'] for r in self.large_repos]:
                        skipped += 1
                            
                except Exception as e:
                    log.error(f"Error processing repository {repo_url}: {str(e)}")
                    continue

            # Final summary
            log.info("\nScan completed!")
            log.info(f"Processed {processed} repositories")
            if secrets_found > 0:
                log.success(f"Found secrets in {secrets_found} repositories")
            if skipped > 0:
                log.warning(f"Skipped {skipped} repositories due to size limit")
            if self.large_repos and not download_all:
                log.warning("\nThe following repositories were skipped due to size limit:")
                for repo in self.large_repos:
                    log.warning(f"- {repo['url'].split('/')[-1]} ({repo['size_mb']:.2f}MB)")
                log.warning("\nUse 'run find_secrets --download-all' to analyze these repositories regardless of size")

            log.info("\nUse 'print --data secrets' to view the findings")
            
        except sqlite3.Error as e:
            log.error(f"Database error: {str(e)}")
        finally:
            cur.close()

    def help(self):
        print("plugin commands:")
        print("stalk github_username\tget email address from account.")
        print("get_repos github_username\tretrieve all public repos of the user.")
        print("find_secrets\tsearch for secrets in all repositories associated with the company using gitleaks.")
        print("find_secrets --download-all\tsearch for secrets in all repositories, ignoring size limits.")
        print("\nExample usage:")
        print("  run find_secrets\tsearch for secrets in repositories under size limit")
        print("  run find_secrets --download-all\tsearch for secrets in all repositories")
        print("  run stalk username\tget email from GitHub account")
        print("  run get_repos username\tget all public repositories")
