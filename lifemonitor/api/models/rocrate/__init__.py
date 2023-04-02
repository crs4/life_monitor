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

from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid as _uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import lifemonitor.exceptions as lm_exceptions
from flask import current_app
from github.GithubException import GithubException, RateLimitExceededException
from lifemonitor.api.models import db, repositories
from lifemonitor.api.models.repositories.base import (
    WorkflowRepository, WorkflowRepositoryMetadata)
from lifemonitor.api.models.repositories.github import (
    GithubRepositoryRevision, GithubWorkflowRepository)
from lifemonitor.api.models.repositories.local import LocalWorkflowRepository
from lifemonitor.auth.models import (ExternalServiceAuthorizationHeader,
                                     HostingService, Resource)
from lifemonitor.config import BaseConfig
from lifemonitor.models import JSON
from lifemonitor.storage import RemoteStorage
from lifemonitor.utils import download_url, get_current_ref
from sqlalchemy import inspect
from sqlalchemy.ext.hybrid import hybrid_property

from rocrate import rocrate

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
    __crate_reader__: WorkflowRepositoryMetadata = None
    __storage: RemoteStorage = None  # type: ignore

    __mapper_args__ = {
        'polymorphic_identity': 'ro_crate',
        "inherit_condition": id == Resource.id
    }

    def __init__(self, uri, uuid=None, name=None,
                 version=None, hosting_service=None,
                 repository: repositories.WorkflowRepository = None) -> None:
        super().__init__(uri, uuid=uuid, name=name, version=version)
        self.hosting_service = hosting_service  # type: ignore
        self._repository: repositories.WorkflowRepository = repository

    @property
    def _storage(self) -> RemoteStorage:
        if not self.__storage:
            self.__storage = RemoteStorage()
        return self.__storage

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

    def _get_storage_path(self, local_path: str) -> str:
        assert local_path, "local_path should not be empty"
        root_path = current_app.config.get('DATA_WORKFLOWS', '/data_workflows')
        return local_path.replace(f"{root_path}/", '')

    @property
    def storage_path(self) -> str:
        return self._get_storage_path(self.local_path)

    @property
    def revision(self) -> Optional[GithubRepositoryRevision]:
        if self._is_github_crate_(self.uri) and isinstance(self.repository, GithubWorkflowRepository):
            return self.repository.get_revision(self.version)
        return None

    def has_revision(self) -> bool:
        try:
            branch = self.revision.main_ref.shorthand
            assert branch, "Branch cannot be empty"
            return True
        except Exception:
            return False

    @hybrid_property
    def crate_metadata(self):
        if self._metadata:
            return self._metadata
        return self.repository.metadata.to_json()

    @property
    def _crate_reader(self) -> rocrate.ROCrate:
        if not self.__crate_reader__:
            if self._metadata:
                with tempfile.TemporaryDirectory(dir='/tmp') as tmp_dir:
                    with open(os.path.join(
                            tmp_dir,
                            WorkflowRepositoryMetadata.DEFAULT_METADATA_FILENAME), 'w') as out:
                        json.dump(self._metadata, out)
                    self.__crate_reader__ = WorkflowRepositoryMetadata(
                        LocalWorkflowRepository(tmp_dir), init=False)
            else:
                self.__crate_reader__ = self.repository.metadata
        return self.__crate_reader__

    @property
    def repository(self) -> repositories.WorkflowRepository:
        logger.debug("Getting repository object bound to the ROCrate %r", self)
        if not self.uri:
            raise lm_exceptions.IllegalStateException("URI (roc_link) not set")
        if not self._repository:
            logger.debug("Initializing repository object bound to the ROCrate %r", self)
            # download the RO-Crate if it is not locally stored
            ref = None
            if not os.path.exists(self.local_path):
                logger.debug(f"{self.local_path} archive of {self} not found locally!!!")
                logger.debug("Remote storage enabled: %r", self._storage.enabled)
                logger.debug("File exists on remote storage: %r", self._storage.exists(self._get_storage_path(self.local_path)))
                # download the workflow ROCrate and store it into the remote storage
                if not inspect(self).persistent or not self._storage.exists(self._get_storage_path(self.local_path)):
                    _, ref, _ = self.download_from_source(self.local_path)
                    logger.debug(f"RO-Crate downloaded from {self.uri} to {self.storage_path}!")
                    if self._storage.enabled and not self._storage.exists(self._get_storage_path(self.local_path)):
                        self._storage.put_file_as_job(self.local_path, self._get_storage_path(self.local_path))
                        logger.debug(f"Scheduled job to store {self.storage_path} into the remote storage!")
                else:
                    # download the RO-Crate archive from the remote storage
                    logger.warning(f"Getting path {self.storage_path} from remote storage!!!")
                    if self._storage.enabled and not self._storage.exists(self._get_storage_path(self.local_path)):
                        self._storage.get_file(self._get_storage_path(self.local_path), self.local_path)
                        logger.warning(f"Getting path {self.storage_path} from remote storage.... DONE!!!")

            # instantiate a local ROCrate repository
            if self._is_github_crate_(self.uri):
                authorizations = self.authorizations + [None]
                token = None
                for authorization in authorizations:
                    if not authorization or isinstance(authorization, ExternalServiceAuthorizationHeader):
                        token = authorization.auth_token if authorization else None
                        try:
                            self._repository = repositories.GithubWorkflowRepository.from_zip(self.local_path, self.uri, token=token, ref=ref)
                            logger.debug("The loaded repository: %r", self._repository)
                        except RateLimitExceededException as e:
                            raise lm_exceptions.RateLimitExceededException(detail=str(e))
                        except Exception as e:
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.exception(e)
                        if self._repository is not None:
                            break
            else:
                self._repository = repositories.ZippedWorkflowRepository(self.local_path)

            # set metadata
            self._metadata = self._repository.metadata.to_json()
            self._metadata_loaded = True
        return self._repository

    @property
    def authors(self) -> List[Dict]:
        return self.get_authors()

    def __get_attribute_from_crate_reader__(self,
                                            attributeName: str, attributedType: str = 'method',
                                            *args, **kwargs) -> object | None:
        try:
            attr = getattr(self._crate_reader, attributeName)
            if attributedType == 'method':
                return attr(*args, **kwargs)
            else:
                return attr
        except lm_exceptions.NotValidROCrateException as e:
            logger.warning("Unable to process ROCrate archive: %s", str(e))
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
        except Exception as e:
            logger.error(str(e))
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(e)
        return None

    def get_authors(self, suite_id: str = None) -> List[Dict] | None:
        return self.__get_attribute_from_crate_reader__('get_authors', suite_id=suite_id)

    @hybrid_property
    def roc_suites(self):
        return self.__get_attribute_from_crate_reader__('get_roc_suites')

    def get_roc_suite(self, roc_suite_identifier):
        return self.__get_attribute_from_crate_reader__('get_get_roc_suite', roc_suite_identifier)

    @property
    def based_on(self) -> str | None:
        return self.__get_attribute_from_crate_reader__('isBasedOn', attributedType='property')

    @property
    def based_on_link(self) -> str:
        return self.__get_attribute_from_crate_reader__('isBasedOn', attributedType='property')

    @property
    def dataset_name(self):
        return self.__get_attribute_from_crate_reader__('dataset_name', attributedType='property')

    @property
    def main_entity_name(self):
        return self.__get_attribute_from_crate_reader__('main_entity_name', attributedType='property')

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
            local_path, ref, commit = self.download_from_source(target_path.name, uri=roc_link, extra_auth=extra_auth)
            logger.debug("Temp local path of crate to compare: %r (ref: %r, commit: %r)", local_path, ref, commit)
            repo = repositories.ZippedWorkflowRepository(local_path)
            return self.repository.compare_to(repo)

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

    @staticmethod
    def _is_github_crate_(uri: str) -> str:
        # FIXME: replace with a better detection mechanism
        if uri.startswith('https://github.com'):
            # normalize uri as clone URL
            if not uri.endswith('.git'):
                uri += '.git'
            return uri
        return None

    @staticmethod
    def _find_git_ref_(repo: GithubWorkflowRepository, version: str) -> str:
        assert isinstance(repo, WorkflowRepository)
        ref = repo.ref
        commit = repo.get_commit(ref) if ref else None
        try:
            branch = repo.get_branch(version)
            ref, commit = f"refs/remotes/origin/{branch.name}", branch.commit
        except GithubException as e:
            logger.debug(f"Unable to get branch {version}: %s", str(e))
            for tag in repo.get_tags():
                if tag.name == version:
                    ref, commit = f"refs/tags/{tag.name}", tag.commit
                    break
        logger.debug("Detected ref: %r", ref)
        return ref, commit

    def download_from_source(self, target_path: str = None, uri: str = None, version: str = None,
                             extra_auth: ExternalServiceAuthorizationHeader = None) -> Tuple[str, str, str]:
        errors = []

        # set URI
        uri = uri or self.uri

        # set version
        version = version or self.version

        # set target_path
        if not target_path:
            target_path = tempfile.mktemp(dir=BaseConfig.BASE_TEMP_FOLDER)
        try:
            # try either with authorization header and without authorization
            for authorization in self._get_authorizations(extra_auth=extra_auth):
                try:
                    git_url = self._is_github_crate_(uri)
                    if git_url:
                        token = None
                        if authorization and isinstance(authorization, ExternalServiceAuthorizationHeader):
                            token = authorization.auth_token
                        with repositories.RepoCloneContextManager(git_url, auth_token=token) as tmp_path:
                            repo = repositories.GithubWorkflowRepository.from_local(tmp_path, git_url, token=token)
                            ref, commit = self._find_git_ref_(repo, version)
                            repo.checkout_ref(ref)  # , branch_name=version)
                            logger.debug("Checkout DONE")
                            logger.debug(get_current_ref(tmp_path))
                            archive = repo.write_zip(target_path)
                            logger.debug("Zip file written to: %r", archive)
                            return archive, ref, commit
                    else:
                        auth_header = authorization.as_http_header() if authorization else None
                        logger.debug(auth_header)
                        local_zip = download_url(uri,
                                                 target_path=target_path,
                                                 authorization=auth_header)
                        logger.debug("ZIP Archive: %s", local_zip)
                        return target_path, None, None
                except lm_exceptions.NotAuthorizedException as e:
                    logger.info("Caught authorization error exception while downloading and processing RO-crate: %s", e)
                    errors.append(str(e))
        except lm_exceptions.IllegalStateException as e:
            logger.exception(e)
            raise lm_exceptions.NotValidROCrateException(detail=e.detail)
        raise lm_exceptions.NotAuthorizedException(detail=f"Not authorized to download {uri}", original_errors=errors)
