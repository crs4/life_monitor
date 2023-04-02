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
from typing import Dict

from flask import request
from flask_socketio import disconnect, emit, join_room

from lifemonitor.cache import cache

from .config import socketIO

# configure logger
logger = logging.getLogger(__name__)

# initialize SocketIO
if not socketIO:
    raise RuntimeError("SocketIO not initialized yet")


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
    logger.info("Connected (%s)", "anonymous" if not auth else "authenticated")
    emit('connection accepted', {})
    currentSocketId = request.sid
    logger.warning(f"Client connected with ID: {currentSocketId}")
    logger.warning(f"Registered client {request.remote_addr} with clientId {request.sid}")


@socketIO.on('disconnect')
def on_disconnect():
    logger.info("Disconnected %s", request.sid)
    user_id = cache.get(request.sid)
    if isinstance(user_id, str):
        cache.delete(user_id)
    cache.delete(request.sid)


@socketIO.on('message')
def handle_message(message):
    logger.debug('received message: %r' % message)
    # emit("message", {"type": "echo", "data": message})
    if message['type'] == 'join':
        logger.debug(f"Joining SID {request.sid} to room {message['data']['user']}")
        join_room(str(message['data']['user']))
        logger.warning(f"SID {request.sid} joined to room {message['data']['user']}")
