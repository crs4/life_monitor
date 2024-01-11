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

import datetime
import json
import logging
import time
from typing import List
from uuid import UUID

from flask import Flask

from lifemonitor.redis import get_connection

# from .config import socketIO

# default redis channeld
__CHANNEL__ = "ws_messages"

# default max age of messages
__MAX_AGE__ = 10


# set module level logger
logger = logging.getLogger(__name__)


def __format_timestamp__(timestamp: datetime) -> str:
    tz_offset = timestamp.strftime('%z')
    return timestamp.strftime('%a %b %d %Y %H:%M:%S ') + 'GMT' + tz_offset[:3] + ':' + tz_offset[3:]


class _CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


def publish_message(message, channel: str = __CHANNEL__,
                    target_ids: List[str] = None, target_rooms: List[str] = None, delay: int = 0):
    now = datetime.datetime.now(datetime.timezone.utc)
    timestamp_as_str = __format_timestamp__(now)
    logger.debug(f"Pushing message @ {timestamp_as_str}")
    get_connection().publish(channel, json.dumps({
        "timestamp": now.timestamp(),
        "delay": delay,
        "target_ids": target_ids,
        "target_rooms": target_rooms,
        # "timestamp": datetime_as_timestamp_with_msecs(now),
        "payload": message
    }, cls=_CustomEncoder))


def start_reading(app: Flask, channel: str = __CHANNEL__, max_age: int = __MAX_AGE__):
    pubsub = get_connection().pubsub()
    pubsub.subscribe(channel)
    for message in pubsub.listen():
        try:
            logger.debug(f"Received message of type {message['type']}")
            if message['type'] in ['subscribe', 'unsubscribe']:
                continue
            data = json.loads(message['data'])
            logger.debug("Processing message: %r", data['timestamp'])
            logger.debug("Decoded data: %r", data)
            if datetime.datetime.now(datetime.timezone.utc).timestamp() - data['timestamp'] > max_age:
                logger.warn(f"Message {data['timestamp']} skipped: too old")
            else:
                if data['delay'] > 0:
                    time.sleep(data['delay'])
                    # app.socketIO.sleep(data['delay'])
                message_targets = data.get('target_ids', None)
                if message_targets:
                    for message_target in message_targets:
                        logger.warning("Message target: %r", message_target)
                        app.socketIO.emit("message", data, to=message_target)
                        logger.info(f"Message with timestamp {data['timestamp']} sent as {__format_timestamp__(datetime.datetime.utcnow())} to {message_target}")

                message_rooms = data.get('target_rooms', None)
                if message_rooms:
                    for message_room in message_rooms:
                        logger.warning("Message target room: %r", message_room)
                        app.socketIO.emit("message", data, room=message_room)
                        logger.info(f"Message with timestamp {data['timestamp']} sent as {__format_timestamp__(datetime.datetime.utcnow())}  room {message_room}")

                if not message_rooms and not message_targets:
                    # logger.warning("Broadcasting message target: %r", message_target)
                    app.socketIO.emit("message", data)
                    logger.info(f"Message with timestamp {data['timestamp']} broadcasted as {__format_timestamp__(datetime.datetime.utcnow())}")
        except Exception as e:
            logger.error("Invalid message: %s", str(e))
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
    pubsub.unsubscribe()


def start_brodcaster(app: Flask, channel: str = __CHANNEL__, max_age: int = __MAX_AGE__):
    logger.info(f"Started vroadcasting Redis channel {channel} to the websocket")
    app.socketIO.start_background_task(
        target=start_reading, app=app, channel=channel, max_age=max_age)
