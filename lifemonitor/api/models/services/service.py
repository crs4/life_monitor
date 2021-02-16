
from __future__ import annotations

import logging

import lifemonitor.api.models as models
from lifemonitor.common import (NotImplementedException,
                                TestingServiceException,
                                TestingServiceNotSupportedException)
from lifemonitor.db import db
from lifemonitor.utils import to_camel_case
from sqlalchemy.dialects.postgresql import UUID

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


class TestingService(db.Model):
    uuid = db.Column("uuid", UUID(as_uuid=True), db.ForeignKey(models.TestInstance.uuid), primary_key=True)
    _type = db.Column("type", db.String, nullable=False)
    url = db.Column(db.Text, nullable=False, unique=True)
    _token = None

    # configure relationships
    test_instances = db.relationship("TestInstance", back_populates="testing_service")

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
        raise NotImplementedException()

    def is_workflow_healthy(self, test_instance: models.TestInstance) -> bool:
        raise NotImplementedException()

    def get_last_test_build(self, test_instance: models.TestInstance) -> models.TestBuild:
        raise NotImplementedException()

    def get_last_passed_test_build(self, test_instance: models.TestInstance) -> models.TestBuild:
        raise NotImplementedException()

    def get_last_failed_test_build(self, test_instance: models.TestInstance) -> models.TestBuild:
        raise NotImplementedException()

    def get_test_build(self, test_instance: models.TestInstance, build_number) -> models.TestBuild:
        raise NotImplementedException()

    def get_test_builds(self, test_instance: models.TestInstance, limit=10) -> list:
        raise NotImplementedException()

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

    def save(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @classmethod
    def all(cls):
        return cls.query.all()

    @classmethod
    def find_by_id(cls, uuid) -> TestingService:
        return cls.query.get(uuid)

    @classmethod
    def find_by_url(cls, url) -> TestingService:
        return cls.query.filter(TestingService.url == url).first()

    @classmethod
    def get_instance(cls, service_type, url: str):
        try:
            # return the service obj if the service has already been registered
            instance = cls.find_by_url(url)
            logger.debug("Found service instance: %r", instance)
            if instance:
                return instance
            # try to instanciate the service if the it has not been registered yet
            service_class = globals()["{}TestingService".format(to_camel_case(service_type))]
            return service_class(url)
        except KeyError:
            raise TestingServiceNotSupportedException(f"Not supported testing service type '{service_type}'")
        except Exception as e:
            raise TestingServiceException(detail=str(e))
