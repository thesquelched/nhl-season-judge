import os.path
from os import makedirs
from hashlib import md5
import requests

class UrlCache(object):
  def __init__(self, url, cachedir = None):
    self._url = url

    self._cachedir = './cache' if cachedir is None else cachedir
    pathsum = md5(url.encode('utf-8')).hexdigest()

    self._cachefile = os.path.join(self._cachedir, pathsum)

  def read(self):
    if not os.path.isfile(self._cachefile):
      self.refresh()

    with open(self._cachefile, 'r') as f:
      return f.read()

  def refresh(self):
    try:
      makedirs(self._cachedir)
    except FileExistsError:
      pass

    resp = requests.get(self._url)

    if resp.ok:
      with open(self._cachefile, 'wb') as f:
        f.write(resp.content)
    else:
      raise ValueError('Could not read %s' % self._url)
