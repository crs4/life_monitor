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

import functools
import logging
import os
import ssl
from typing import Dict

from flask_socketio import SocketIO, disconnect

from lifemonitor.app import create_app

logger = logging.getLogger(__name__)

# create an app instance
application = create_app()

if __name__ == '__main__':
    """ Start development server"""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(
        os.environ.get("LIFEMONITOR_TLS_CERT", './certs/lm.crt'),
        os.environ.get("LIFEMONITOR_TLS_KEY", './certs/lm.key'))

    # init SocketIO middleware
    socketIO = SocketIO(application, cors_allowed_origins="*")

    def authenticated_only(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            logger.debug("args: %r", args)
            logger.debug("kwargs: %r", kwargs)
            payload: Dict = args[0] if len(args) > 0 else None  # type: ignore
            if 'token' not in payload:
                logger.debug("Disconnecting...")
                disconnect()
            else:
                logger.debug("Connection accepted....")
                return f(payload)
        return wrapped

    @socketIO.on('connect')
    def connect(auth):
        logger.debug("Connected: %r", auth)
        return True

    @socketIO.on('message')
    def handle_message(data):
        logger.error('received message: %r' % data)
        from flask_socketio import emit
        emit("server message", ({"data": 12}), namespace="/", broadcast=True)

    from eventlet.green.OpenSSL import SSL

    # insecure context, only for example purposes
    context = SSL.Context(SSL.SSLv23_METHOD)
    # Pass server's private key created
    context.use_privatekey_file(os.environ.get("LIFEMONITOR_TLS_KEY", './certs/lm.key'))
    # Pass self-signed certificate created
    context.use_certificate_file(os.environ.get("LIFEMONITOR_TLS_CERT", './certs/lm.crt'))

    # Start Flask App + SocketIO
    socketIO.run(application, host="0.0.0.0", port=8000, debug=True,
                 keyfile=os.environ.get("LIFEMONITOR_TLS_KEY", './certs/lm.key'),
                 certfile=os.environ.get("LIFEMONITOR_TLS_CERT", './certs/lm.crt'))
