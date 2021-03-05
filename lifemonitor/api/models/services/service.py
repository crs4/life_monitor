
from __future__ import annotations

import logging
from typing import List

import lifemonitor.exceptions as lm_exceptions
from lifemonitor.api import models
from lifemonitor.api.models import db
from lifemonitor.models import UUID, ModelMixin
from lifemonitor.utils import ClassManager
from sqlalchemy.orm.exc import NoResultFound

# set module level logger
logger = logging.getLogger(__name__)


class TestingServiceToken:
    def __init__(self, key, secret):
        self.key = key
        self.secret = secret

    def __composite_values__(self):
        return self.key, self.secret

    def __repr__(self):
        return "<TestingServiceToken (key=%r, secret=****)>" % self.key

    def __eq__(self, other):
        return isinstance(other, TestingServiceToken) and other.key == self.key and other.secret == self.secret

    def __ne__(self, other):
        return not self.__eq__(other)


class TestingServiceTokenManager:
    __instance = None

    @classmethod
    def get_instance(cls) -> TestingServiceTokenManager:
        if not cls.__instance:
            cls.__instance = cls()
        return cls.__instance

    def __init__(self):
        if self.__instance:
            raise RuntimeError("TestingServiceTokenManager instance already exists!")
        self.__instance = self
        self.__token_registry = {}

    def add_token(self, service_url, token: TestingServiceToken):
        self.__token_registry[service_url] = token

    def remove_token(self, service_url):
        try:
            del self.__token_registry[service_url]
        except KeyError:
            logger.info("No token for the service '{}'", service_url)

    def get_token(self, service_url) -> TestingServiceToken:
        return self.__token_registry[service_url] if service_url in self.__token_registry else None


class TestingService(db.Model, ModelMixin):
    uuid = db.Column("uuid", UUID, db.ForeignKey(models.TestInstance.uuid), primary_key=True)
    _type = db.Column("type", db.String, nullable=False)
    url = db.Column(db.Text, nullable=False, unique=True)
    _token = None

    # configure relationships
    test_instances = db.relationship("TestInstance", back_populates="testing_service")

    # configure the class manager
    service_type_registry = ClassManager('lifemonitor.api.models.services', class_suffix='TestingService', skip=['__init__', 'service'])

    __mapper_args__ = {
        'polymorphic_on': _type,
        'polymorphic_identity': 'testing_service'
    }

    def __init__(self, url: str, token: models.TestingServiceToken = None) -> None:
        self.url = url
        self._token = token

    def __repr__(self):
        return f'<TestingService {self.url}, ({self.uuid})>'

    @property
    def token(self):
        if not self._token:
            logger.debug("Querying the token registry for the service %r...", self.url)
            self._token = models.TestingServiceTokenManager.get_instance().get_token(self.url)
        logger.debug("Set token for the testing service %r (type: %r): %r", self.url, self._type, self._token is not None)
        return self._token

    def check_connection(self) -> bool:
        raise lm_exceptions.NotImplementedException()

    def is_workflow_healthy(self, test_instance: models.TestInstance) -> bool:
        raise lm_exceptions.NotImplementedException()

    def get_last_test_build(self, test_instance: models.TestInstance) -> models.TestBuild:
        raise lm_exceptions.NotImplementedException()

    def get_last_passed_test_build(self, test_instance: models.TestInstance) -> models.TestBuild:
        raise lm_exceptions.NotImplementedException()

    def get_last_failed_test_build(self, test_instance: models.TestInstance) -> models.TestBuild:
        raise lm_exceptions.NotImplementedException()

    def get_test_build(self, test_instance: models.TestInstance, build_number) -> models.TestBuild:
        raise lm_exceptions.NotImplementedException()

    def get_test_builds(self, test_instance: models.TestInstance, limit=10) -> list:
        raise lm_exceptions.ßNotImplementedException()

    def get_test_builds_as_dict(self, test_instance: models.TestInstance, test_output):
        last_test_build = self.last_test_build
        last_passed_test_build = self.last_passed_test_build
        last_failed_test_build = self.last_failed_test_build
        return {
            'last_test_build': last_test_build.to_dict(test_output) if last_test_build else None,
            'last_passed_test_build':
                last_passed_test_build.to_dict(test_output) if last_passed_test_build else None,
            'last_failed_test_build':
                last_failed_test_build.to_dict(test_output) if last_failed_test_build else None,
            "test_builds": [t.to_dict(test_output) for t in self.test_builds]
        }

    def to_dict(self, test_builds=False, test_output=False) -> dict:
        data = {
            'uuid': str(self.uuid),
            'testing_service_url': self.url,
            'workflow_healthy': self.is_workflow_healthy,
        }
        if test_builds:
            data["test_build"] = self.get_test_builds_as_dict(test_output=test_output)
        return data

    @classmethod
    def all(cls) -> List[TestingService]:
        return cls.query.all()

    @classmethod
    def find_by_uuid(cls, uuid) -> TestingService:
        return cls.query.get(uuid)

    @classmethod
    def find_by_url(cls, url) -> TestingService:
        try:
            return cls.query.filter(TestingService.url == url).one()
        except NoResultFound as e:
            logger.debug(e)
            return None
        except Exception as e:
            raise lm_exceptions.LifeMonitorException(detail=str(e), stack=str(e))

    @classmethod
    def get_instance(cls, service_type, url: str) -> TestingService:
        try:
            # return the service obj if the service has already been registered
            instance = cls.find_by_url(url)
            logger.debug("Found service instance: %r", instance)
            if instance:
                return instance
            # try to instanciate the service if the it has not been registered yet
            return cls.service_type_registry.get_class(service_type)(url)
        except KeyError:
            raise lm_exceptions.TestingServiceNotSupportedException(f"Not supported testing service type '{service_type}'")
        except Exception as e:
            raise lm_exceptions.TestingServiceException(detail=str(e))
