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
import tempfile
import uuid as _uuid
from pathlib import Path
from typing import Dict, List, Tuple

import lifemonitor.exceptions as lm_exceptions
from flask import current_app
from lifemonitor.api.models import db, repositories
from lifemonitor.auth.models import (ExternalServiceAuthorizationHeader,
                                     HostingService, Resource)
from lifemonitor.config import BaseConfig
from lifemonitor.models import JSON
from lifemonitor.utils import download_url
from sqlalchemy.ext.hybrid import hybrid_property

# set module level logger
logger = logging.getLogger(__name__)


class ROCrate(Resource):

    id = db.Column(db.Integer, db.ForeignKey(Resource.id), primary_key=True)
    hosting_service_id = db.Column(db.Integer, db.ForeignKey("resource.id"), nullable=True)
    hosting_service: HostingService = db.relationship("HostingService", uselist=False,
                                                      backref=db.backref("ro_crates", cascade="all, delete-orphan"),
                                                      foreign_keys=[hosting_service_id])
    _metadata = db.Column("metadata", JSON, nullable=True)
    _local_path = db.Column("local_path", db.String, nullable=True)
    _metadata_loaded = False
    _repository: repositories.WorkflowRepository = None

    __mapper_args__ = {
        'polymorphic_identity': 'ro_crate',
        "inherit_condition": id == Resource.id
    }

    def __init__(self, uri, uuid=None, name=None,
                 version=None, hosting_service=None) -> None:
        super().__init__(uri, uuid=uuid, name=name, version=version)
        self.hosting_service = hosting_service
        self._repository: repositories.WorkflowRepository = None

    @property
    def local_path(self):
        if not self._local_path:
            root_path = current_app.config.get('DATA_WORKFLOWS', '/data_workflows')
            try:
                if not self.workflow.uuid:
                    self.workflow.uuid = _uuid.uuid4()
                base_path = os.path.join(root_path, str(self.workflow.uuid))
            except Exception:
                base_path = os.path.join(root_path, str(_uuid.uuid4()))
            if not self.uuid:
                self.uuid = _uuid.uuid4()
            os.makedirs(base_path, exist_ok=True)
            self._local_path = os.path.join(base_path, f"{self.uuid}.zip")
        return self._local_path

    @hybrid_property
    def crate_metadata(self):
        return self.repository.metadata.to_json()

    def load_metadata(self) -> dict:
        return self.repository.metadata.to_json()

    @property
    def repository(self) -> repositories.WorkflowRepository:
        if not self.uri:
            raise lm_exceptions.IllegalStateException("URI (roc_link) not set")
        if not self._repository:
            # download the RO-Crate if it is not locally stored
            if not os.path.exists(self.local_path):
                self.download_from_source(self.local_path)
            # instantiate a local ROCrate repository
            self._repository = repositories.ZippedWorkflowRepository(self.local_path)
            # set metadata
            self._metadata = self.repository.metadata.to_json()
            self._metadata_loaded = True
        return self._repository

    @property
    def authors(self) -> List[Dict]:
        return self.repository.metadata.get_authors()

    def get_authors(self, suite_id: str = None) -> List[Dict]:
        return self.repository.metadata.get_authors(suite_id=suite_id)

    @hybrid_property
    def roc_suites(self):
        return self.repository.metadata.get_roc_suites()

    def get_roc_suite(self, roc_suite_identifier):
        return self.repository.metadata.get_get_roc_suite(roc_suite_identifier)

    @property
    def based_on(self) -> str:
        return self.repository.metadata.isBasedOn

    @property
    def based_on_link(self) -> str:
        return self.repository.metadata.isBasedOn

    @property
    def dataset_name(self):
        return self.repository.metadata.dataset_name

    @property
    def main_entity_name(self):
        return self.repository.metadata.main_entity_name

    def _get_authorizations(self, extra_auth: ExternalServiceAuthorizationHeader = None):
        authorizations = []
        if extra_auth:
            authorizations.append(extra_auth)
        authorizations.extend(self.authorizations)
        authorizations.append(None)
        return authorizations

    def check_for_changes(self, roc_link: str, extra_auth: ExternalServiceAuthorizationHeader = None) -> Tuple:
        # try either with authorization header and without authorization
        with tempfile.NamedTemporaryFile(dir=BaseConfig.BASE_TEMP_FOLDER) as target_path:
            local_path = self.download_from_source(target_path.name, uri=roc_link, extra_auth=extra_auth)
            logger.debug("Temp local path of crate to compare: %r", local_path)
            repo = repositories.ZippedWorkflowRepository(local_path)
            return self.repository.compare(repo)

    def download(self, target_path: str) -> str:
        # load ro-crate if not locally stored
        metadata = self.crate_metadata

        # report an error if the workflow is not locally available
        if metadata and not self._local_path:
            raise lm_exceptions.DownloadException(detail="RO-Crate unavailable", status=410)

        tmpdir_path = Path(target_path)
        local_zip = download_url(self.local_path,
                                 target_path=(tmpdir_path / 'rocrate.zip').as_posix())
        logger.debug("ZIP Archive: %s", local_zip)
        return (tmpdir_path / 'rocrate.zip').as_posix()

    def download_from_source(self, target_path: str = None, uri: str = None,
                             extra_auth: ExternalServiceAuthorizationHeader = None) -> str:
        errors = []

        # set URI
        uri = uri or self.uri

        # set target_path
        if not target_path:
            target_path = tempfile.mktemp(dir=BaseConfig.BASE_TEMP_FOLDER)
        try:
            # try either with authorization header and without authorization
            for authorization in self._get_authorizations(extra_auth=extra_auth):
                try:
                    # FIXME: replace with a better detection mechanism
                    if uri.startswith('https://github.com'):
                        token = None
                        # normalize uri as clone URL
                        if not uri.endswith('.git'):
                            uri += '.git'
                        if authorization and isinstance(authorization, ExternalServiceAuthorizationHeader):
                            token = authorization.auth_token
                        with repositories.RepoCloneContextManager(uri, auth_token=token) as tmp_path:
                            repo = repositories.LocalWorkflowRepository(tmp_path)
                            archive = repo.write_zip(target_path)
                            logger.debug("Zip file written to: %r", archive)
                            return archive
                    else:
                        auth_header = authorization.as_http_header() if authorization else None
                        logger.debug(auth_header)
                        local_zip = download_url(uri,
                                                 target_path=target_path,
                                                 authorization=auth_header)
                        logger.debug("ZIP Archive: %s", local_zip)
                        return target_path
                except lm_exceptions.NotAuthorizedException as e:
                    logger.info("Caught authorization error exception while downloading and processing RO-crate: %s", e)
                    errors.append(str(e))
        except lm_exceptions.IllegalStateException as e:
            logger.exception(e)
            raise lm_exceptions.NotValidROCrateException(detail=e.detail)
        raise lm_exceptions.NotAuthorizedException(detail=f"Not authorized to download {uri}", original_errors=errors)
