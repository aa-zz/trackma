# -*- coding: utf-8 -*-
# This file is part of Trackma.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import re
import urllib.parse
import urllib.request
import datetime
import base64
import gzip
import json
import time

from trackma.lib.lib import lib
from trackma import utils

class libmal(lib):
    """
    API class to communicate with MyAnimeList
    Should inherit a base library interface.

    Website: http://www.myanimelist.net
    API documentation: none

    """
    name = 'libmal'

    username = '' # TODO Must be filled by check_credentials
    logged_in = False
    opener = None

    api_info =  { 'name': 'MyAnimeList', 'shortname': 'mal', 'version': '', 'merge': False }

    default_mediatype = 'anime'
    mediatypes = dict()
    mediatypes['anime'] = {
        'has_progress': True,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_tag': True,
        'can_update': True,
        'can_play': True,
        'can_date': True,
        'status_start': 1,
        'status_finish': 2,
        'statuses':  [1, 2, 3, 4, 6],
        'statuses_dict': { 1: 'Watching', 2: 'Completed', 3: 'On Hold', 4: 'Dropped', 6: 'Plan to Watch' },
        'score_max': 10,
        'score_step': 1,
    }
    mediatypes['manga'] = {
        'has_progress': True,
        'has_volumes': True,
        'can_add': True,
        'can_delete': True,
        'can_score': True,
        'can_status': True,
        'can_tag': True,
        'can_update': True,
        'can_play': False,
        'can_date': True,
        'status_start': 1,
        'status_finish': 2,
        'statuses': [1, 2, 3, 4, 6],
        'statuses_dict': { 1: 'Reading', 2: 'Completed', 3: 'On Hold', 4: 'Dropped', 6: 'Plan to Read' },
        'score_max': 10,
        'score_step': 1,
    }

    # 'Authorized' User-Agent for Trackma
    url = 'https://myanimelist.net/'
    useragent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36'

    image_re = re.compile(r'images/(?:anime|manga)/([^/]+)/([^\.]+)(\.[a-zA-Z]+)')

    def __init__(self, messenger, account, userconfig):
        """Initializes the useragent through credentials."""
        # Since MyAnimeList uses a cookie we just create a HTTP Auth handler
        # together with the urllib opener.
        super(libmal, self).__init__(messenger, account, userconfig)

        self.username = account['username']
        self.password = account['password']
        self.cookies = urllib.request.HTTPCookieProcessor()
        self.opener = urllib.request.build_opener(self.cookies)
        self.opener.addheaders = [
            ('User-Agent', self.useragent),
        ]

    def _request(self, url, data=None, jsondata=None, post=False, tries=1, retry_codes=(404,429)):
        """
        Requests the page as gzip and uncompresses it

        Returns a stream object

        """
        data = data or jsondata
        if post:
            data = data or {}
            data['csrf_token'] = self._get_userconfig('csrf_token')
        if data:
            if not post:
                url += "?" + urllib.parse.urlencode(data)
                data = jsondata = None
            else:
                data = (json.dumps(data) if jsondata else urllib.parse.urlencode(data)).encode('utf-8')

        for i in range(tries):
            try:
                #print(url, data.decode('utf-8') if data else data)
                request = urllib.request.Request(url, data=data)
                request.add_header('Accept-Encoding', 'gzip')
                if jsondata:
                    request.add_header('Content-Type', 'application/json')
                response = self.opener.open(request, timeout = 10)
                break
            except urllib.request.HTTPError as e:
                if tries > 1 and e.code in retry_codes:
                    time.sleep(min(0.1 * (i+1), 0.3))
                elif e.code == 401:
                    raise utils.APIError(
                            "Unauthorized. Please check if your username and password are correct."
                            "\n\nPlease note that you might also be getting this error if you have "
                            "non-alphanumeric characters in your password due to an upstream "
                            "MAL bug (#138).")
                else:
                    raise utils.APIError("HTTP error %d: %s" % (e.code, e.reason))
            except urllib.request.URLError as e:
                raise utils.APIError("Connection error: %s" % e)

        if response.info().get('content-encoding') == 'gzip':
            ret = gzip.decompress(response.read())
        else:
            # If the content is not gzipped return it as-is
            ret = response.read()
        if isinstance(ret, bytes):
            ret = ret.decode('utf-8')
        if response.info().get('content-type').startswith('application/json'):
            ret = json.loads(ret)
        return ret

    def check_credentials(self):
        """Checks if credentials are correct; returns True or False."""
        if self.logged_in:
            return True     # Already logged in

        self.msg.info(self.name, 'Logging in...')

        response = self._request(self.url + "login.php")
        csrf = re.search(r'csrf_token.*content=[\'"]([^\'"]+)[\'"]', response)
        if not csrf:
            raise utils.APIError("Could not find the CSRF token.")
        csrf_token = csrf.group(1)
        self._set_userconfig('csrf_token', csrf_token)
        self.msg.info(self.name, 'got csrf ' + csrf_token)

        login_data = {
            'user_name': self.username, 'password': self.password, 'cookie': '1',
            'sublogin': 'Login', 'submit': '1'
        }
        response = self._request(self.url + "login.php", data=login_data, post=True)
        if '"og:url" content="https://myanimelist.net/login.php"' in response:
            raise utils.APIError(
                "Unauthorized. Please check if your username and password are correct."
                "\n\nPlease note that you might also be getting this error if you have "
                "non-alphanumeric characters in your password due to an upstream "
                "MAL bug (#138).")

        self._set_userconfig('username', self.username)
        self._emit_signal('userconfig_changed')

        self.logged_in = True
        return True

    def fetch_list(self):
        """Queries the full list from the remote server.
        Returns the list if successful, False otherwise."""
        self.check_credentials()
        self.msg.info(self.name, 'Downloading list...')

        try:
            # Get the list
            data = {'status': 7}
            url = "{}{}list/{}/load.json".format(self.url, self.mediatype, self.username)
            result = response = self._request(url, data=data)
            while response:
                data['offset'] = len(result)
                response = self._request(url, data=data, tries=5)
                result += response

            if self.mediatype == 'anime':
                self.msg.info(self.name, 'Parsing anime list...')
                return self._parse_anime(result)
            elif self.mediatype == 'manga':
                self.msg.info(self.name, 'Parsing manga list...')
                return self._parse_manga(result)
            else:
                raise utils.APIFatal('Attempted to parse unsupported media type.')
        except urllib.request.HTTPError as e:
            raise utils.APIError("Error getting list.")
        except IOError as e:
            raise utils.APIError("Error reading list: %s" % e)

    def add_show(self, item):
        """Adds a new show in the server"""
        self.check_credentials()
        self.msg.info(self.name, "Adding show %s..." % item['title'])

        data = self._build_crup(item)

        # Post the request
        try:
            self._request('{}ownlist/{}/add.json'.format(self.url, self.mediatype), jsondata=data, post=True)
        except utils.APIError as e:
            raise utils.APIError('Error adding %s: %s' % (item['title'], str(e))) from e

    def update_show(self, item, show):
        """Sends a show update to the server"""
        self.check_credentials()
        self.msg.info(self.name, "Updating show %s..." % item['title'])

        data = self._build_crup(item, show)

        # Post the request
        try:
            resp = self._request('{}ownlist/{}/edit.json'.format(self.url, self.mediatype), jsondata=data, post=True)
        except utils.APIError as e:
            raise utils.APIError('Error updating %s: %s' % (item['title'], str(e))) from e

    def delete_show(self, item):
        """Sends a show delete to the server"""
        self.check_credentials()
        self.msg.info(self.name, "Deleting show %s..." % item['title'])

        try:
            self._request('{}ownlist/{}/{}/delete'.format(self.url, self.mediatype, item['id']), post=True)
        except utils.APIError as e:
            raise utils.APIError('Error deleting %s: %s' % (item['title'], str(e))) from e

    def search(self, criteria):
        """Searches MyAnimeList database for the queried show"""
        self.msg.info(self.name, "Searching for %s..." % criteria)

        # Send the urlencoded query to the search API
        query = {'keyword': criteria, 'type': self.mediatype, 'v': 1}
        data = self._request(self.url + 'search/prefix.json', data=query)
        items = (y for x in data['categories'] for y in x['items'])

        # Since the MAL API returns the status as a string, and
        # we handle statuses as integers, we need to convert them
        if self.mediatype == 'anime':
            status_key = 'aired'
            status_translate = {'Currently Airing': utils.STATUS_AIRING,
                    'Finished Airing': utils.STATUS_FINISHED,
                    'Not yet aired': utils.STATUS_NOTYET}
        elif self.mediatype == 'manga':
            status_key = 'published'
            status_translate = {'Publishing': utils.STATUS_AIRING,
                    'Finished': utils.STATUS_AIRING}

        entries = list()
        for item in items:
            show = utils.show()
            showid = item['id']
            show.update({
                'id':           showid,
                'title':        item['name'],
                'type':         item['type'],
                'status':       status_translate[item['payload']['status']], # TODO : This should return an int!
                #'total':        int(child.find(episodes_str).text),
                'image':        self._get_image_url(self.mediatype, item['image_url']),
                'url':          item['url'],
                #'start_date':   self._str2date( child.find('start_date').text ),
                #'end_date':     self._str2date( child.find('end_date').text ),
                'extra': [
                    #('English',  child.find('english').text),
                    #('Synonyms', child.find('synonyms').text),
                    #('Synopsis', self._translate_synopsis(child.find('synopsis').text)),
                    #(episodes_str.title(), child.find(episodes_str).text),
                    ('Type',     item['type']),
                    ('Score',    item['payload']['score']),
                    ('Status',   item['payload']['status']),
                    ('Start date', item['payload'][status_key]),
                    #('End date', child.find('end_date').text),
                    ]
            })
            entries.append(show)

        self._emit_signal('show_info_changed', entries)
        return entries

    def _translate_synopsis(self, string):
        if string is None:
            return None
        else:
            return string.replace('<br />', '')

    def request_info(self, itemlist):
        resultdict = dict()
        for item in itemlist:
            # Search for it only if it hasn't been found earlier
            if item['id'] not in resultdict:
                infos = self.search(item['title'])
                for info in infos:
                    showid = info['id']
                    resultdict[showid] = info

        itemids = [ show['id'] for show in itemlist ]

        try:
            reslist = [ resultdict[itemid] for itemid in itemids ]
        except KeyError:
            raise utils.APIError('There was a problem getting the show details.')

        return reslist

    def _parse_anime(self, items):
        """Converts a JSON anime list to a dictionary"""
        showlist = dict()

        for item in items:
            show = utils.show()
            show_id = item['anime_id']
            show.update({
                'id':           show_id,
                'title':        item['anime_title'],
                'my_progress':  item['num_watched_episodes'],
                'my_status':    item['status'],
                'my_score':     item['score'],
                'my_start_date':  self._str2date( item['start_date_string'] ),
                'my_finish_date': self._str2date( item['finish_date_string'] ),
                'my_tags':         item['tags'],
                'total':        item['anime_num_episodes'],
                'status':       item['anime_airing_status'],
                'start_date':   self._str2date( item['anime_start_date_string'] ),
                'end_date':     self._str2date( item['anime_end_date_string'] ),
                'image':        self._get_image_url('anime', item['anime_image_path']),
                'url':          self.url + item['anime_url'][1:],
            })
            showlist[show_id] = show
        return showlist

    def _parse_manga(self, items):
        """Converts a JSON manga list to a dictionary"""
        mangalist = dict()

        for item in items:
            show = utils.show()
            show_id = item['manga_id']
            show.update({
                'id':           show_id,
                'title':        item['manga_title'],
                'my_progress':  item['num_read_chapters'],
                'my_volumes':   item['num_read_volumes'],
                'my_status':    item['status'],
                'my_score':     item['score'],
                'my_start_date':  self._str2date( item['start_date_string'] ),
                'my_finish_date': self._str2date( item['finish_date_string'] ),
                'total':        item['manga_num_chapters'],
                'total_volumes': item['manga_num_volumes'],
                'status':       item['manga_publishing_status'],
                'start_date':   self._str2date( item['manga_start_date_string'] ),
                'end_date':     self._str2date( item['manga_end_date_string'] ),
                'image':        self._get_image_url('manga', item['manga_image_path']),
                'url':          self.url + item['manga_url'][1:],
            })
            mangalist[show_id] = show
        return mangalist

    def _build_crup(self, item, show=None):
        """
        Converts an "anime|manga data" entry into the format
        that MAL expects.

        Fun fact:
          They apparently use Composer:
          https://github.com/composer/composer
        """

        # Use the correct name depending on mediatype
        if self.mediatype == 'anime':
            idname = 'anime_id'
            progressname = 'num_watched_episodes'
        else:
            idname = 'manga_id'
            progressname = 'num_read_chapters'

        # Start building the result
        result = {idname: item['id']}

        # Update *required* keys
        if 'my_status' in item:
            result['status'] = item['my_status']
        elif show is not None and 'my_status'in show:
            result['status'] = show['my_status']

        # Update necessary keys
        if 'my_progress' in item:
            result[progressname] = item['my_progress']
        if self.mediatype == 'manga' and 'my_volumes' in item:
            result['num_read_volumes'] = item['my_volumes']
        if 'my_score' in item:
            result['score'] = item['my_score']
        if 'my_start_date' in item and item['my_start_date']:
            result['start_date'] = {
                'year': item['my_start_date'].year,
                'month': item['my_start_date'].month,
                'day': item['my_start_date'].day,
            }
        if 'my_finish_date' in item and item['my_finish_date']:
            result['finish_date'] = {
                'year': item['my_finish_date'].year,
                'month': item['my_finish_date'].month,
                'day': item['my_finish_date'].day,
            }
        if 'my_tags' in item:
            result['tags'] = str(item['my_tags'])

        return result

    def _get_image_url(self, list_type, raw_url):
        m = self.image_re.search(raw_url)
        if m:
            return 'https://myanimelist.cdn-dena.com/images/{}/{}/{}{}'.format(
                list_type, m.group(1), m.group(2), m.group(3)
            )
        return raw_url

    def _str2date(self, string):
        if string:
            # Guessaroo
            for fmt in ('%Y-%m-%d', '%m-%d-%y', '%d-%m-%y'):
                try:
                    return datetime.datetime.strptime(string, fmt)
                except ValueError:
                    pass # Ignore date if it's invalid
        return None
