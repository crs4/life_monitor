# Copyright (c) 2020-2024 CRS4
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
from urllib.parse import urlsplit

import requests

HEADERS = {
    "Content-type": "application/vnd.api+json",
    "Accept": "application/vnd.api+json",
    "Accept-Charset": "ISO-8859-1"
}


class Client():

    def __init__(self, url, token=None):
        self.url = url.rstrip("/")
        self.session = requests.Session()
        headers = HEADERS.copy()
        # with no authentication, client will only get public items
        if token:
            headers['Authorization'] = f'Bearer {token}'
        self.session.headers.update(headers)

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def get_workflows(self):
        r = self.session.get(f"{self.url}/workflows")
        r.raise_for_status()
        return r.json()["data"]

    def get_workflow(self, id_):
        r = self.session.get(f"{self.url}/workflows/{id_}")
        r.raise_for_status()
        return r.json()["data"]

    def download_workflow(self, wf, out_dir):
        blob = wf["attributes"]["content_blobs"][0]
        path = urlsplit(blob["link"]).path
        r = self.session.get(f"{self.url}/{path}")
        r.raise_for_status()
        data = r.json()["data"]
        file_url = self.url + data["links"]["download"]
        out_path = os.path.join(out_dir, blob["original_filename"])
        with self.session.get(file_url, stream=True) as r:
            r.raise_for_status()
            with open(out_path, 'wb') as fd:
                for chunk in r.iter_content(chunk_size=8192):
                    fd.write(chunk)
        return out_path
