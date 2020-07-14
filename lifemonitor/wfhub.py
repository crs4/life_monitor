import os
from urllib.parse import urlsplit
from urllib.request import urlretrieve

import requests


HEADERS = {
    "Content-type": "application/vnd.api+json",
    "Accept": "application/vnd.api+json",
    "Accept-Charset": "ISO-8859-1"
}


# no authentication for now, get only public items
class Client():

    def __init__(self, url):
        self.url = url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

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
        urlretrieve(file_url, out_path)
        return out_path
