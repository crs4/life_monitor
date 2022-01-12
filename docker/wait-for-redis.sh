#!/usr/bin/env bash

HOST=${REDIS_HOST:-redis}
PORT=${REDIS_PORT:-6379}
PASSWORD=${REDIS_PASSWORD:-foobar}

echo "Waiting for Redis @$HOST:$PORT ..."
echo "Try ping Redis... "
PONG=`redis-cli -h $HOST -p $PORT -a $PASSWORD ping | grep PONG`
while [ -z "$PONG" ]; do
    sleep 1
    echo "Retry Redis ping... "
    PONG=`redis-cli -h $HOST -p $PORT -a $PASSWORD ping | grep PONG`
done
echo "Redis at host '$HOST', port '$PORT' fully started."