from __future__ import annotations

from typing import List

from lifemonitor.db import db
from sqlalchemy.ext.declarative import declared_attr


class ModelMixin(object):

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    def save(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @classmethod
    def all(cls) -> List:
        return cls.query.all()
