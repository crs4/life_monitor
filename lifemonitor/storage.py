# Copyright (c) 2020-2021 CRS4
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

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

import boto3
import botocore
from flask import Flask, current_app

from lifemonitor.cache import Timeout, cache
from lifemonitor.tasks.scheduler import Scheduler

# set module level logger
logger = logging.getLogger(__name__)


class RemoteStorage():

    __bucket = None
    __s3 = None
    __client = None
    _config = None
    _bucket_name = None

    def __init__(self, app: Flask = None, config: Optional[Dict] = None) -> None:
        self.app = app = app or current_app
        try:
            self._config: Dict[str, str] = config if config is not None else {
                'endpoint_url': app.config['S3_ENDPOINT_URL'],
                'aws_access_key_id': app.config['S3_ACCESS_KEY'],
                'aws_secret_access_key': app.config['S3_SECRET_KEY'],
                'bucket_name': app.config.get('S3_BUCKET', 'lifemonitor-bucket')
            }
            self._bucket_name = self._config.pop('bucket_name')
            self._enabled = True

        except KeyError as e:
            logger.warning("S3 Storage not property configured: %s", str(e))
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def _s3(self):
        if not self.__s3 and self._config:

            self.__s3 = boto3.resource('s3', **self._config)
        return self.__s3

    @property
    def _client(self):
        if not self.__client and self._config:
            self.__client = boto3.client('s3', **self._config)
        return self.__client

    @property
    def bucket_name(self) -> str:
        return self._bucket_name  # type: ignore

    def _get_bucket_file(self, file_path, bucket_name: Optional[str] = None) -> str:
        return f'{bucket_name or self.bucket_name}/{file_path}'

    def _get_bucket(self):
        if not self.__bucket:
            # create bucket if it doesn't exist
            self._client.create_bucket(Bucket=self.bucket_name)
            # set a reference to the bucket resource
            self.__bucket = self._s3.Bucket(self.bucket_name)
        return self.__bucket

    def exists(self, path: str) -> bool:
        if not self._enabled:
            logger.warning("S3 Storage not properly configured")
            return False
        else:
            try:
                self._s3.Object(self.bucket_name, path).load()
                return True
            except botocore.exceptions.ClientError as e:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.exception(e)
                if e.response['Error']['Code'] == "404":
                    return False
        return False

    def get_file(self, remote_path: str, local_path: str) -> bool:
        if not self._enabled:
            logger.warning("S3 Storage not properly configured")
        else:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            try:
                self._get_bucket().download_file(remote_path, local_path)
                return True
            except Exception as e:
                logger.error("Local path: %r", local_path)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.exception(e)
        return False

    def put_file_as_job(self, local_path: str, remote_path: str):
        scheduler: Scheduler = self.app.scheduler
        logger.debug("Current app scheduler: %r", scheduler)
        scheduler.run_job('put_file', self.bucket_name, local_path, remote_path)

    def put_file(self, local_path: str, remote_path: str):
        if not self._enabled:
            logger.warning("S3 Storage not properly configured")
        else:
            if not self.exists(remote_path):
                with cache.lock(remote_path, timeout=Timeout.NONE) as lock:
                    if not self.exists(remote_path):
                        try:
                            self._get_bucket().upload_file(local_path, remote_path)
                        except Exception as e:
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.exception(e)
                            raise RuntimeError(e)

    def delete_folder(self, remote_path: str) -> bool:
        if not self._enabled:
            logger.warning("S3 Storage not properly configured")
        else:
            try:
                self._get_bucket().objects.filter(Prefix=remote_path).delete()
                return True
            except Exception as e:
                logger.error("Error when deleting path: %r", remote_path)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.exception(e)
        return False

    def delete_file(self, remote_path: str) -> bool:
        if not self._enabled:
            logger.warning("S3 Storage not properly configured")
        else:
            try:
                self._get_bucket().Object(remote_path).delete()
                return True
            except Exception as e:
                logger.error("Error when deleting path: %r", remote_path)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.exception(e)
        return False
