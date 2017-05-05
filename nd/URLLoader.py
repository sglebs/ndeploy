# Inspired by https://github.com/veselosky/jinja2_s3loader/blob/master/jinja2_s3loader/__init__.py
from jinja2 import BaseLoader, TemplateNotFound
import requests
from urllib.parse import urljoin
from requests_file import FileAdapter
from jinja2._compat import string_types

class URLloader(BaseLoader):

    def __init__(self, searchpath):
        if isinstance(searchpath, string_types):
            searchpath = [searchpath]
        self.searchpath = list(searchpath)
        super(URLloader, self).__init__()

    def get_source(self, environment, template):
        try:
            session = requests.Session()
            session.mount('file://', FileAdapter())
            for searchpath in self.searchpath:
                url = urljoin(searchpath, template)
                resp = session.get(url)
                if resp.status_code == 200:
                    return resp.text, None, lambda: True
        except requests.RequestException as e:
            raise TemplateNotFound(template)
        raise TemplateNotFound(template)
