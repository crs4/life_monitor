class LifeMonitorException(Exception):
    pass


class NotImplementedException(LifeMonitorException):
    pass


class UnsupportedOperationException(LifeMonitorException):
    pass


class SpecificationNotDefinedException(LifeMonitorException):
    pass


class SpecificationNotValidException(LifeMonitorException):
    pass


class EntityNotFoundException(LifeMonitorException):

    def __init__(self, entity_class, entity_id=None) -> None:
        super().__init__()
        self.entity_class = entity_class
        self.entity_id = entity_id

    def __str__(self):
        if self.entity_id:
            return "{} with id {} not found".format(self.entity_class.__name__, self.entity_id)
        return "{} not found".format(self.entity_class.__name__)


class TestingServiceNotSupportedException(LifeMonitorException):
    pass
