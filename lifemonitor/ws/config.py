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
import os
import logging

from flask_socketio import SocketIO

from lifemonitor.utils import boolean_value

# configure logger
logger = logging.getLogger(__name__)

# current SocketIO instance
socketIO = None


def init_socket(app, **kwargs) -> SocketIO:
    global socketIO
    if not socketIO:
        debug = boolean_value(app.config.get("DEBUG", os.environ.get("DEBUG", False)))
        socketIO = SocketIO(app=app, logger=debug, async_mode='gevent',  # async_mode='eventlet',  # async_mode=kwargs.get('async_mode', None),
                            # engineio_logger=debug,
                            cors_allowed_origins="*")
        logger.info("SocketIO initialized")
        # import eventlet
        # eventlet.monkey_patch()
        app.socketIO = socketIO
        return socketIO
    else:
        logger.warning("SocketIO initialisation skipped: already initialized")
        return None
