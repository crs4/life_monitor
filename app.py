# Copyright (c) 2020-2022 CRS4
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
import ssl

from lifemonitor.app import create_app

# initialise logger
logger = logging.getLogger(__name__)


# create an app instance
application = create_app(init_app=True)


def start_websocket_server():
    from lifemonitor.ws import initialise_ws

    # init SocketIO middleware
    socketIO = initialise_ws(application)
    # start app server with SocketIO server enabled
    socketIO.run(application, host="0.0.0.0", port=8000,
                 keyfile=os.environ.get("LIFEMONITOR_TLS_KEY", './certs/lm.key'),
                 certfile=os.environ.get("LIFEMONITOR_TLS_CERT", './certs/lm.crt'))


def start_app_server():
    """ Start Flask App"""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(
        os.environ.get("LIFEMONITOR_TLS_CERT", './certs/lm.crt'),
        os.environ.get("LIFEMONITOR_TLS_KEY", './certs/lm.key'))
    application.run(host="0.0.0.0", port=8000, ssl_context=context)


def start():
    from lifemonitor.utils import boolean_value
    if boolean_value(os.environ.get("WEBSOCKET_SERVER", True)) \
            and application.config.get("ENV") not in ("testing", "testingSupport"):
        logger.info("Starting App+WebSocket Server...")
        start_websocket_server()
    else:
        logger.info("Starting App Server...")
        start_app_server()


if __name__ == '__main__':
    start()
