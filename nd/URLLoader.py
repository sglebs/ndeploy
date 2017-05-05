# Inspired by https://github.com/veselosky/jinja2_s3loader/blob/master/jinja2_s3loader/__init__.py
from jinja2 import BaseLoader, TemplateNotFound
import requests
from urllib.parse import urljoin
from requests_file import FileAdapter

class URLloader(BaseLoader):

    def __init__(self, base_url):
        self.base_url = base_url
        super(URLloader, self).__init__()

    def get_source(self, environment, template):
        try:
            session = requests.Session()
            session.mount('file://', FileAdapter())
            url = urljoin(self.base_url, template)
            resp = session.get(url)
        except requests.RequestException as e:
            raise TemplateNotFound(template)
        return resp.text, None, lambda: True