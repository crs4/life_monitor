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

import logging
import os

from flask import Flask, request, abort
from flask import send_file

app = Flask(__name__)

logger = logging.getLogger(__name__)

server_auth_token = os.environ['WEB_SERVER_AUTH_TOKEN'].strip('"')
data_path = os.environ.get('DATA_PATH', '/data')


@app.route('/download')
def downloadFile():
    logger.debug("HEADERS: %r", request.headers)
    file = request.args.get("file", None)
    if file is None:
        abort(400, description="Missing file argument")
    auth_token = request.headers.get("Authorization", None)
    logger.debug("Authorization header: %s", auth_token)
    logger.debug("Comparing tokens: %s -- %s", auth_token, server_auth_token)
    if auth_token != server_auth_token:
        abort(401, description="Invalid token")
    path = os.path.join(data_path, file)
    if not os.path.isfile(path):
        abort(404, description=f"{path} not found on this server")
    return send_file(path, as_attachment=True)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    app.run(host="0.0.0.0", port=5000, debug=True)
