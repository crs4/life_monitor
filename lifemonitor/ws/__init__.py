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
from socket import SocketIO
from typing import Optional

from flask import Flask, current_app

from .config import init_socket
from .socket import run

# initialize logger
logger = logging.getLogger(__name__)

# reference to the current SocketIO instance
current_socket = None


def initialise_ws(app: Flask, async_mode='threading') -> Optional[SocketIO]:
    global current_socket
    socketIO = init_socket(app)
    if socketIO:
        current_socket = socketIO
        from . import events
        logger.info("SocketIO events module loaded: %r", events)
        # if not app.config.get("WORKER", False):
        #     from . events import broadcast_redis_message
        #     from . io import subscribe
        #     subscribe(app, broadcast_redis_message)
        return socketIO

    return None


def start_websocket_server(app: Flask = None, port=8001):
    app = app or current_app
    # init SocketIO middleware
    socketIO = initialise_ws(app)
    if app.config.get("WORKER", False):
        # start app server with SocketIO server enabled
        socketIO.run(app, host="0.0.0.0", port=port,
                     keyfile=os.environ.get("LIFEMONITOR_TLS_KEY", './certs/lm.key'),
                     certfile=os.environ.get("LIFEMONITOR_TLS_CERT", './certs/lm.crt'))


__all__ = ['initialise_ws', 'run', 'current_socket', 'start_websocket_server']
