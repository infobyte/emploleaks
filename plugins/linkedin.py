import requests
import re
import urllib
import json
from urllib.parse import urlparse
from urllib.parse import unquote

from colorama import Fore, Style
from utils.logging_format import log

class NameMutator():
    """
    This class handles all name mutations.

    Init with a raw name, and then call the individual functions to return a mutation.
    """
    def __init__(self, name):
        self.name = self.clean_name(name)
        self.name = self.split_name(self.name)

    @staticmethod
    def clean_name(name):
        """
        Removes common punctuation.

        LinkedIn users tend to add credentials to their names to look special.
        This function is based on what I have seen in large searches, and attempts
        to remove them.
        """
        # Lower-case everything to make it easier to de-duplicate.
        name = name.lower()

        # Use case for tool is mostly standard English, try to standardize common non-English
        # characters.
        name = re.sub("[àáâãäå]", 'a', name)
        name = re.sub("[èéêë]", 'e', name)
        name = re.sub("[ìíîï]", 'i', name)
        name = re.sub("[òóôõö]", 'o', name)
        name = re.sub("[ùúûü]", 'u', name)
        name = re.sub("[ýÿ]", 'y', name)
        name = re.sub("[ß]", 'ss', name)
        name = re.sub("[ñ]", 'n', name)

        # Get rid of all things in parenthesis. Lots of people put various credentials, etc
        name = re.sub(r'\([^()]*\)', '', name)

        # The lines below basically trash anything weird left over.
        # A lot of users have funny things in their names, like () or ''
        # People like to feel special, I guess.
        allowed_chars = re.compile('[^a-zA-Z -]')
        name = allowed_chars.sub('', name)

        # Next, we get rid of common titles. Thanks ChatGPT for the help.
        titles = ['mr', 'miss', 'mrs', 'phd', 'prof', 'professor', 'md', 'dr', 'mba']
        pattern = "\\b(" + "|".join(titles) + ")\\b"
        name = re.sub(pattern, '', name)

        # The line below tries to consolidate white space between words
        # and get rid of leading/trailing spaces.
        name = re.sub(r'\s+', ' ', name).strip()

        return name

    @staticmethod
    def split_name(name):
        """
        Takes a name (string) and returns a list of individual name-parts (dict).

        Some people have funny names. We assume the most important names are:
        first name, last name, and the name right before the last name (if they have one)
        """
        # Split on spaces and dashes (included repeated)
        parsed = re.split(r'[\s-]+', name)

        # Iterate and remove empty strings
        parsed = [part for part in parsed if part]

        # Discard people without at least a first and last name
        if len(parsed) < 2:
            return None

        if len(parsed) > 2:
            split_name = {'first': parsed[0], 'second': parsed[-2], 'last': parsed[-1]}
        else:
            split_name = {'first': parsed[0], 'second': '', 'last': parsed[-1]}

        # Final sanity check to not proceed without first and last name
        if not split_name['first'] or not split_name['last']:
            return None

        return split_name

    def f_last(self):
        """jsmith"""
        names = set()
        names.add(self.name['first'][0] + self.name['last'])

        if self.name['second']:
            names.add(self.name['first'][0] + self.name['second'])

        return names

    def f_dot_last(self):
        """j.smith"""
        names = set()
        names.add(self.name['first'][0] + '.' + self.name['last'])

        if self.name['second']:
            names.add(self.name['first'][0] + '.' + self.name['second'])

        return names

    def last_f(self):
        """smithj"""
        names = set()
        names.add(self.name['last'] + self.name['first'][0])

        if self.name['second']:
            names.add(self.name['second'] + self.name['first'][0])

        return names

    def first_dot_last(self):
        """john.smith"""
        names = set()
        names.add(self.name['first'] + '.' + self.name['last'])

        if self.name['second']:
            names.add(self.name['first'] + '.' + self.name['second'])

        return names

    def first_l(self):
        """johns"""
        names = set()
        names.add(self.name['first'] + self.name['last'][0])

        if self.name['second']:
            names.add(self.name['first'] + self.name['second'][0])

        return names

    def first(self):
        """john"""
        names = set()
        names.add(self.name['first'])

        return names

    def generate_from_format(self, format_str):
        """Generate email usernames based on a custom format string."""
        if not self.name:
            return set()

        names = set()
        try:
            # Replace format placeholders with actual values and ensure no quotes
            username = format_str.format(
                n=self.name['first'][0],  # first initial
                s=self.name['last'],      # last name
                name=self.name['first'],  # first name
                l=self.name['last'][0]    # last initial
            ).strip('"\'')  # Remove any quotes that might be in the format string
            
            # Ensure the username is clean
            username = re.sub(r'[^a-zA-Z0-9._-]', '', username)
            names.add(username)
        except (KeyError, IndexError):
            # If format is invalid, return empty set
            pass

        return names


class LinkedinModule:
    def __init__(self, queue=None, local_conn=None, company_id=None):
        self.options = [{
                'name': 'hide',
                'value': 'yes',
                'required': False,
                'description': "hide the JSESSIONID field"
            }, {
                'name': 'JSESSIONID',
                'value': '',
                'required': False,
                'description': "active cookie session in browser #1"
            }, {
                'name': 'li-at',
                'value': '',
                'required': False,
                'description': "active cookie session in browser #1"
            }]
            
        self.session = None
        self.queue = queue
        self.local_conn = local_conn
        self.company_id = company_id

    def do_show(self, args):
        print("Module options:\n")
        table = [['Name', 'Current Setting', 'Required', 'Description']]        
        hide_pass = self.options[0]['value'] == 'yes'

        for opt in self.options:
            if hide_pass and opt['name'] == 'JSESSIONID':
                table.append([ opt['name'], '*' * len(self.options[1]['value']), 'yes' if opt['required'] else 'no', opt['description']])
                continue
            table.append([ opt['name'], opt['value'], 'yes' if opt['required'] else 'no', opt['description']])
        
        return table

    def impersonate(self):
        self.session = requests.session()

        mobile_agent = ('Mozilla/5.0 (Linux; U; Android 4.4.2; en-us; SCH-I535 '
                        'Build/KOT49H) AppleWebKit/534.30 (KHTML, like Gecko) '
                        'Version/4.0 Mobile Safari/534.30')

        self.session.headers.update({'User-Agent': mobile_agent,
                                'X-RestLi-Protocol-Version': '2.0.0'})

        print("Setting for first time JSESSIONID")
        self.session.cookies.set("JSESSIONID", self.options[1]['value'], domain='.www.linkedin.com', secure=True)

        print("Setting for first time li_at")
        self.session.cookies.set("li_at", self.options[2]['value'], domain='.www.linkedin.com', secure=True)

        self.set_csrf_token()

    def set_csrf_token(self):
        try:
            csrf_token = self.session.cookies['JSESSIONID'].replace('"', '')
            self.session.headers.update({'Csrf-Token': csrf_token})
        except KeyError:
            print("JSESSION is not setted")
        
    @staticmethod
    def _build_photo_url(vector_image):
        """Build a photo URL from a vectorImage dict.
        Handles two LinkedIn formats:
        - rootUrl + relative segment (connections)
        - empty rootUrl with full URL in segment (search results)
        """
        if not isinstance(vector_image, dict):
            return ''
        root_url = vector_image.get('rootUrl', '')
        artifacts = vector_image.get('artifacts', [])
        if not artifacts:
            return ''
        best = max(artifacts, key=lambda a: a.get('width', 0))
        seg = best.get('fileIdentifyingUrlPathSegment', '')
        if not seg:
            return ''
        if seg.startswith('http'):
            return seg
        if root_url:
            return root_url + seg
        return ''

    def _extract_company_logo(self, company_data):
        """Extract company logo URL from the LinkedIn company API response.
        Recursively searches for vectorImage in logo-related fields."""
        import logging
        log = logging.getLogger(__name__)

        def find_best_image_url(obj):
            """Recursively find vectorImage with rootUrl+artifacts or full URL artifacts."""
            if not isinstance(obj, dict):
                return ''
            if 'rootUrl' in obj and 'artifacts' in obj:
                root = obj['rootUrl']
                artifacts = obj['artifacts']
                if artifacts:
                    best = max(artifacts, key=lambda a: a.get('width', 0))
                    seg = best.get('fileIdentifyingUrlPathSegment', '')
                    if seg.startswith('http'):
                        return seg
                    if root:
                        return root + seg
            for v in obj.values():
                if isinstance(v, dict):
                    result = find_best_image_url(v)
                    if result:
                        return result
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            result = find_best_image_url(item)
                            if result:
                                return result
            return ''

        for field in ['logo', 'logoV2', 'squareLogoV2', 'squareLogo', 'heroImage']:
            data = company_data.get(field)
            if data:
                url = find_best_image_url(data)
                if url:
                    log.debug(f"Company logo found in '{field}': {url[:80]}...")
                    return url

        url = find_best_image_url(company_data)
        if url:
            log.debug(f"Company logo found via deep search: {url[:80]}...")
            return url

        log.debug(f"Company logo not found. Available keys: {list(company_data.keys())}")
        return ''

    def _extract_photo_from_entity(self, entity):
        """Extract profile photo URL from a search result entity by recursively
        looking for vectorImage in the image field."""
        image_data = entity.get('image')
        if not image_data:
            return ''

        # Recursive search for vectorImage in the image structure
        def find_vector_image(obj):
            if not isinstance(obj, dict):
                return None
            if 'rootUrl' in obj and 'artifacts' in obj:
                return obj
            for v in obj.values():
                if isinstance(v, dict):
                    result = find_vector_image(v)
                    if result:
                        return result
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            result = find_vector_image(item)
                            if result:
                                return result
            return None

        try:
            vector = find_vector_image(image_data)
            if vector:
                return self._build_photo_url(vector)
        except Exception:
            pass
        return ''

    def get_contact_info(self, public_id):
        """Fetch contact info for a profile using the GraphQL endpoint."""
        if not self.session:
            print("Run impersonate first")
            return None

        if not public_id:
            return None

        url = (
            f'https://www.linkedin.com/voyager/api/graphql'
            f'?includeWebMetadata=true'
            f'&variables=(memberIdentity:{public_id})'
            f'&queryId=voyagerIdentityDashProfiles.c7452e58fa37646d09dae4920fc5b4b9'
        )
        try:
            response = self.session.get(url)
            log.debug(f"Contact info for '{public_id}': HTTP {response.status_code}")
            if response.status_code != 200:
                return None

            data = response.json()

            elements = (data.get('data', {})
                        .get('identityDashProfilesByMemberIdentity', {})
                        .get('elements', []))

            if not elements:
                return None

            profile = elements[0]
            contact_info = {}

            # Email (nested: emailAddress -> emailAddress)
            email_data = profile.get('emailAddress')
            if isinstance(email_data, dict):
                email = email_data.get('emailAddress')
                if email:
                    contact_info['email_address'] = email

            # Phone numbers (nested: phoneNumber -> number)
            phones = profile.get('phoneNumbers', [])
            if phones and isinstance(phones, list):
                parsed_phones = []
                for p in phones:
                    phone_obj = p.get('phoneNumber', {})
                    if isinstance(phone_obj, dict) and phone_obj.get('number'):
                        parsed_phones.append({'number': phone_obj['number']})
                if parsed_phones:
                    contact_info['phone_numbers'] = parsed_phones

            # Websites
            websites = profile.get('websites', [])
            if websites:
                parsed_websites = [{'url': w['url']} for w in websites if w.get('url')]
                if parsed_websites:
                    contact_info['websites'] = parsed_websites

            # Twitter handles (top-level field)
            twitter_handles_data = profile.get('twitterHandles', [])
            if twitter_handles_data:
                parsed_twitter = [{'name': t.get('name', '')} for t in twitter_handles_data if t.get('name')]
                if parsed_twitter:
                    contact_info['twitter'] = parsed_twitter

            # Instant Messengers (fallback for twitter if not in twitterHandles)
            if 'twitter' not in contact_info:
                ims = profile.get('instantMessengers', [])
                if ims:
                    twitter_handles = []
                    for im in ims:
                        provider = im.get('provider', '').lower()
                        handle = im.get('id', '')
                        if 'twitter' in provider and handle:
                            twitter_handles.append({'name': handle})
                    if twitter_handles:
                        contact_info['twitter'] = twitter_handles

            # Profile photo URL (from memberRelationship connection data, higher res)
            try:
                member_rel = profile.get('memberRelationship', {})
                connection = (member_rel.get('memberRelationship', {})
                              .get('connection', {}))
                if connection:
                    connected_member = connection.get('connectedMemberResolutionResult', {})
                    pic_data = connected_member.get('profilePicture', {})
                    img_ref = pic_data.get('displayImageReferenceResolutionResult', {})
                    vector_img = img_ref.get('vectorImage')
                    if vector_img:
                        url = self._build_photo_url(vector_img)
                        if url:
                            contact_info['profile_photo_url'] = url
            except (AttributeError, TypeError, ValueError):
                pass

            return contact_info if contact_info else None

        except Exception as e:
            log.error(f"Error getting contact info for {public_id}: {str(e)}")
            return None

    def get_company_info(self, name):
        if self.session.cookies.get('JSESSIONID', '') == '':
            print("Run impersonate first")
            return

        escaped_name = urllib.parse.quote_plus(name)

        response = self.session.get(('https://www.linkedin.com'
                                    '/voyager/api/organization/companies?'
                                    'q=universalName&universalName=' + escaped_name))

        #print(response)
        if response.status_code == 404:
            print(f"\n[{Fore.RED}-{Style.RESET_ALL}] Could not find that company name. Please double-check LinkedIn and try again.")
            return

        if response.status_code != 200:
            print(f"[{Fore.RED}-{Style.RESET_ALL}] Unexpected HTTP repsonse code {response.status_code} when trying to get the company info:")
            return

        if 'mwlite' in response.text:
            print("\tA permanent fix is being researched. Sorry about that!")
            return

        try:
            response_json = json.loads(response.text)
        except json.decoder.JSONDecodeError:
            print(f"[{Fore.RED}-{Style.RESET_ALL}] Broke processing JSON, RAROOOO!")
            return

        company = response_json['elements'][0]
        found_name = company.get('name', 'NOT FOUND')
        found_desc = company.get('tagline', 'NOT FOUND')
        found_staff = company['staffCount']
        found_website = company.get('companyPageUrl', "NOT FOUND")

        found_id = company['trackingInfo']['objectUrn'].split(':')[-1]

        logo_url = ''
        try:
            logo_url = self._extract_company_logo(company)
        except Exception:
            pass
        
        return (found_id, found_staff, logo_url)

    def do_loops(self, company_id, company_domain, outer_loops, depth, email_format=None):
        profiles_list = []

        try:
            for current_loop in outer_loops:
                current_region = ''
                current_keyword = ''

                for page in range(0, depth):
                    new_names = 0

                    result = self.get_results(company_id, page, current_region, current_keyword)
                    if result.status_code != 200:
                        print(f"\n[{Fore.RED}-{Style.RESET_ALL}] Yikes, got an HTTP {result.status_code}. This is not normal")
                        print("Bailing from loops, but you should troubleshoot.")
                        break
                    if "UPSELL_LIMIT" in result.text:
                        print("[{Fore.RED}-{Style.RESET_ALL}] You've hit the commercial search limit! "
                              "Try again on the 1st of the month. Sorry. :(")
                        return profiles_list

                    found_profiles = self.find_employees(result.text, company_domain, email_format)

                    if not found_profiles:
                        print(f"[{Fore.GREEN}+{Style.RESET_ALL}] We have hit the end of the road! Moving on...")
                        break

                    new_names += len(found_profiles)
                    profiles_list.extend(found_profiles)

                    print(f"[{Fore.GREEN}+{Style.RESET_ALL}] Added {new_names} new names.")

        except KeyboardInterrupt:
            print("\n\n[!] Caught Ctrl-C. Breaking loops and writing files")

        return profiles_list
    
    def get_results(self, company_id, page, region, keyword):
        if region:
            region = re.sub(':', '%3A', region)  # must URL encode this parameter

        # Build the base search URL.
        url = ('https://www.linkedin.com/voyager/api/graphql?variables=('
        f'start:{page * 50},'
        f'query:('
        f'{f"keywords:{keyword}," if keyword else ""}'
        'flagshipSearchIntent:SEARCH_SRP,'
        f'queryParameters:List((key:currentCompany,value:List({company_id})),'
        f'{f"(key:geoUrn,value:List({region}))," if region else ""}'
        '(key:resultType,value:List(PEOPLE))'
        '),'
        'includeFiltersInResponse:false'
        '),count:50)'
        '&queryId=voyagerSearchDashClusters.66adc6056cf4138949ca5dcb31bb1749')

        headers = {
            'X-Li-Track': '{"clientVersion":"1.13.1793"}'
        }
        result = self.session.get(url, headers=headers)
        return result

    def find_employees(self, result, company_domain, email_format=None):
        """
        Takes the text response of an HTTP query, converts to JSON, and extracts employee details.

        Returns a list of dictionary items, or False if none found.
        """
        found_employees = []

        try:
            result_json = json.loads(result)
        except json.decoder.JSONDecodeError:
            print("\n[!] Yikes! Could not decode JSON when scraping this loop! :(")
            print("I'm going to bail on scraping names now, but this isn't normal. You should "
                  "troubleshoot or open an issue.")
            print("Here's the first 200 characters of the HTTP reply which may help in debugging:\n\n")
            print(result[:200])
            return False

        data = result_json.get('data', {})
        search_clusters = data.get('searchDashClustersByAll', {})
        elements = paging = search_clusters.get('elements', [])
        paging = search_clusters.get('paging', {})
        total = paging.get('total', 0)

        # If we've ended up with empty dicts or zero results left, bail out
        if total == 0:
            return False

        # The "elements" list is the mini-profile you see when scrolling through a
        # company's employees. It does not have all info on the person, like their
        # entire job history. It only has some basics.
        found_employees = []
        for element in elements:
            # For some reason it's nested
            for item_body in element.get('items', []):
                # Info we want is all under 'entityResult'
                entity = item_body.get('item', {}).get('entityResult', {})

                # There's some useless entries we need to skip over
                if not entity:
                    continue

                # There is no first/last name fields anymore so we're taking the full name
                full_name = entity['title']['text'].strip()

                # The name may include extras like "Dr" at the start, so we do some basic stripping
                if full_name[:3] == 'Dr ':
                    full_name = full_name[4:]

                # Some users are missing a primary subtitle
                occupation = entity.get('primarySubtitle', {}).get('text', '') if entity.get('primarySubtitle') else ''

                navigation_url = entity.get('navigationUrl', {}) if entity.get('navigationUrl', {}) else ''
                n_url = urlparse(navigation_url)

                # Extract public_id from URL path (e.g. /in/john-smith -> john-smith)
                public_id = ''
                path_parts = n_url.path.strip('/').split('/')
                if len(path_parts) >= 2 and path_parts[0] == 'in':
                    public_id = path_parts[1]

                mini_profile = unquote(n_url.query).split("fs_miniProfile:")
                if(len(mini_profile) != 2):
                    mini_profile = ''
                else:
                    mini_profile = mini_profile[1]

                # Extract profile photo from search result
                search_photo_url = self._extract_photo_from_entity(entity)

                #getting potential corporate emails
                potential_emails = []
                if 'linkedin' not in full_name.lower():
                    mutator = NameMutator(full_name)
                    if mutator.name:
                        if email_format:
                            # Use custom email format if provided
                            usernames = mutator.generate_from_format(email_format)
                            for username in usernames:
                                potential_emails.append(username + '@' + company_domain)
                        else:
                            # Use default formats if no custom format provided
                            name_funcs = ['f_last', 'f_dot_last']
                            for i in name_funcs:
                                for name in getattr(mutator, i)():
                                    potential_emails.append(name + '@' + company_domain)

                found_employees.append({
                    'full_name': full_name,
                    'occupation': occupation,
                    'public_id': public_id,
                    'mini_profile': mini_profile,
                    'potential_emails': potential_emails,
                    'search_photo_url': search_photo_url
                })

        return found_employees 
