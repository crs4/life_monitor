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
