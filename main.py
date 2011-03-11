#!/usr/bin/env python
import web
from web.contrib.template import render_jinja

try:
  import json
except:
  import simplejson as json

import logging, random, os, wsgiref, time, urllib
from urlparse import urlparse
from StringIO import StringIO

from rdio import Rdio, RdioProtocolException

logging.basicConfig(level=logging.DEBUG)

CONSUMER_TOKEN = 'CONSUMER_TOKEN'
CONSUMER_SECRET = 'CONSUMER_SECRET'

HR_EXPIRY = (60*60*24) # cache HR for one day
HR_LIMIT = 25
HR_CACHE = False

ALBUM_FIELDS = frozenset(('key', 'artist', 'icon', 'shortUrl', 'tracks'))


render = render_jinja('templates', encoding='utf-8')

class Cookies(object):
  def __setitem__(self, key, value):
    web.setcookie(key, urllib.quote(json.dumps(value)))

  def __getitem__(self, key):
    value = web.cookies().get(key)
    if value is not None:
      try:
        value = json.loads(urllib.unquote(value))
      except:
        value = None
    return value

  def has_key(self, key):
    return web.cookies().get(key) is not None

  def __delitem__(self, key):
    web.setcookie(key, '', expires=-1)

class RdioRequestHandler(object):
    __cached_cookies = None
    @property
    def cookies(self):
        if self.__cached_cookies is None:
            self.__cached_cookies = Cookies()
        return self.__cached_cookies

    __cached_rdio = None
    @property
    def rdio(self):
        if self.__cached_rdio is None:
            self.__cached_rdio = Rdio(CONSUMER_TOKEN,
                                      CONSUMER_SECRET,
                                      self.cookies)
        return self.__cached_rdio

    @property
    def secret(self):
        if not self.cookies.has_key('secret') or \
           self.cookies['secret'] is None or \
           self.cookies['secret'] == '':
            # 128 bits of randomness as a big hex
            self.cookies['secret'] = '%x' % random.getrandbits(128)
        return self.cookies['secret']

    @property
    def user(self):
        if self.rdio.authenticated:
            try:
                return self.rdio.currentUser()
            except:
                logging.warning("failed to make authed call, logging out")
                self.rdio.logout()
        else:
            return None


class MainHandler(RdioRequestHandler):
    def GET(self):
      web.header('content-type', 'text/html')
      return render.welcome(signed_in=(self.user is not None))

class GameHandler(RdioRequestHandler):
  def heavyRotation(self):
    raise NotImplementedError("you need to implement heavyRotation")

  def cacheKey(self):
    raise NotImplementedError("you need to implement cacheKey")

  def sourceName(self):
    raise NotImplementedError("you need to implement sourceName")

  def requiresAuth(self):
    return True

  def processHeavyRotation(self, heavy_rotation):
    # get all non-various-artist albums from heavy rotation
    albums = [album for album in heavy_rotation
              if album['artist'] != 'Various Artists']
    # only want one album per artist
    artists = []
    the_albums = []
    for album in albums:
        if album['artist'] in artists: continue
        the_albums.append(album)
        artists.append(album['artist'])
    # just get the album keys
    albums_keys = [album['key'] for album in the_albums]

    # now get all of those albums including their tracks,
    # because that's what we actually want
    albums = self.rdio.call('get',
                            keys=(','.join(albums_keys)),
                            extras='tracks').values()

    # eliminate the album fields we don't use
    albums = [dict([(k,v) for k,v in album.items() if k in ALBUM_FIELDS])
      for album in albums
    ]
    # collapse album track objects into just their ids
    for album in albums:
      album['tracks'] = [track['key'] for track in album['tracks']]

    return albums

  def cachedHeavyRotation(self):
    '''use a cached version of heavy rotation or fetch a new one'''
    memcache_key = self.cacheKey()
    hr = memcache.get(memcache_key)
    timestamp = memcache.get(memcache_key+'_ts')
    if hr is not None and timestamp is not None:
      # parse the json from memcache
      hr = json.loads(hr)
      # check the timestamp
      if int(timestamp) + HR_EXPIRY < time.time():
        hr = None
    if hr is None:
      hr = self.processHeavyRotation(self.heavyRotation())
      memcache.add(memcache_key, json.dumps(hr), HR_EXPIRY)
      memcache.add(memcache_key+'_ts', time.time())
    return hr

  def GET(self):
    if self.requiresAuth() and not self.rdio.authenticated:
      web.seeother('/signin')
      return
    web.header('content-type', 'text/html')
    if HR_CACHE:
      albums = self.cachedHeavyRotation()
    else:
      albums = self.processHeavyRotation(self.heavyRotation())

    domain = urlparse(wsgiref.util.request_uri(web.ctx.environ)).netloc
    if domain.find(':') != -1:
      domain = domain[:domain.find(':')]
    playback_token = self.rdio.getPlaybackToken(domain=domain)


    return render.index(**{'user': self.user,
                                 'source': self.sourceName(),
                                 'albums': albums,
                                 'albums_json': json.dumps(albums, indent=True),
                                 'api_swf': 'http://rd.io/api/swf/',
                                 'domain': domain,
                                 'playbackToken': playback_token,
                                 })

class EveryoneHandler(GameHandler):
  def cacheKey(self):
    return 'hr_everyone'
  def heavyRotation(self):
    return self.rdio.getHeavyRotation(limit=HR_LIMIT)
  def sourceName(self):
    return 'Top Albums on Rdio'
  def requiresAuth(self):
    return False

class UserHandler(GameHandler):
  def cacheKey(self):
    return 'hr_user_%s' % self.user
  def heavyRotation(self):
    return self.rdio.getHeavyRotation(user=self.user['key'],
                                      friends=False,
                                      limit=HR_LIMIT)
  def sourceName(self):
    return 'Your Top Albums on Rdio'

class FriendsHandler(GameHandler):
  def cacheKey(self):
    return 'hr_friends_%s' % self.user
  def heavyRotation(self):
    return self.rdio.getHeavyRotation(user=self.user['key'],
                                      friends=True,
                                      limit=HR_LIMIT)
  def sourceName(self):
    return 'Your Friends\' Top Albums on Rdio'


class LoginHandler(RdioRequestHandler):
    def GET(self):
        web.header('content-type', 'text/html')
        if self.rdio.authenticated:
            self.rdio.logout()

        if not self.rdio.authenticating:
            # obtain a request token
            callback_url = wsgiref.util.request_uri(web.ctx.environ)
            web.seeother(self.rdio.begin_authentication(callback_url))
        else:
            try:
              self.rdio.complete_authentication(web.input().get('oauth_verifier'))
              web.seeother('/')
            except RdioProtocolException, e:
              logging.exception('completing authentication')
              self.rdio.logout()
              web.seeother('/signin')


class LogoutHandler(RdioRequestHandler):
    def GET(self):
        web.header('content-type', 'text/html')
        self.rdio.logout()
        if self.cookies.has_key('hr'):
            del self.cookies['hr']
        web.seeother('/')

application = web.application(
        (
        r'/', 'MainHandler',
        r'/user', 'UserHandler',
        r'/friends', 'FriendsHandler',
        r'/everyone', 'EveryoneHandler',
        r'/signin', 'LoginHandler',
        r'/signout', 'LogoutHandler',
        ), globals())


if __name__ == '__main__':
  web.config.debug = False
  import os
  if os.environ.has_key('GATEWAY_INTERFACE'):
    # running as a CGI
    application.cgirun()
  else:
    # running standalone
    application.run()
