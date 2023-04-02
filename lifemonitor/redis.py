
from flask import Flask
from redis import Redis

__redis__ = None


def get_connection() -> Redis:
    global __redis__
    return __redis__


def init(app: Flask) -> Redis:
    global __redis__
    if not __redis__:
        # Connessione a Redis su localhost, porta 6379, database 0
        __redis__ = Redis(host=app.config.get("REDIS_HOST", "redis"),
                          port=int(app.config.get("REDIS_PORT_NUMBER", 6379)),
                          password=app.config.get("REDIS_PASSWORD", "foobar"),
                          db=0)
    return __redis__
