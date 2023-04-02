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

import uuid
from typing import List
from datetime import datetime, timezone

from sqlalchemy import VARCHAR, types, inspect

from lifemonitor.cache import CacheMixin
from lifemonitor.db import db


class ModelMixin(CacheMixin):

    def refresh(self, **kwargs):
        db.session.refresh(self, **kwargs)

    def save(self, commit: bool = True, flush: bool = True):
        if hasattr(self, 'modified'):
            setattr(self, 'modified', datetime.now(tz=timezone.utc))
        with db.session.begin_nested():
            db.session.add(self)
        if commit:
            db.session.commit()
        if flush:
            db.session.flush()

    def delete(self, commit: bool = True, flush: bool = True):
        with db.session.begin_nested():
            db.session.delete(self)
        if commit:
            db.session.commit()
        if flush:
            db.session.flush()

    def detach(self):
        db.session.expunge(self)

    @property
    def _object_state(self):
        return inspect(self)

    def is_transient(self) -> bool:
        return self._object_state.transient

    def is_pending(self) -> bool:
        return self._object_state.pending

    def is_detached(self) -> bool:
        return self._object_state.detached

    def is_persistent(self) -> bool:
        return self._object_state.persistent

    @classmethod
    def all(cls) -> List:
        return cls.query.all()


class UUID(types.TypeDecorator):
    """Platform-independent UUID type.

    Uses PostgreSQL's UUID type, otherwise uses
    CHAR(32), storing as stringified hex values.

    """
    impl = types.CHAR

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import UUID as _UUID
            return dialect.type_descriptor(_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(types.CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return "%.32x" % uuid.UUID(value).int
            else:
                # hexstring
                return "%.32x" % value.int

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value


class JSON(types.TypeDecorator):
    """Platform-independent JSON type.

    Uses PostgreSQL's JSONB type,
    otherwise uses the standard JSON

    """
    impl = types.JSON

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import JSONB
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(types.JSON())


class CustomSet(types.TypeDecorator):
    """Represents an immutable structure as a json-encoded string."""
    impl = VARCHAR

    def process_bind_param(self, value, dialect):
        if value is not None:
            if not isinstance(value, set):
                raise ValueError("Invalid value type. Got %r", type(value))
            value = ",".join(value)
        return value

    def process_result_value(self, value, dialect):
        return set() if value is None or len(value) == 0 \
            else set(value.split(','))


class StringSet(CustomSet):
    """Represents an immutable structure as a json-encoded string."""
    pass


class IntegerSet(CustomSet):
    """Represents an immutable structure as a json-encoded string."""

    def process_bind_param(self, value, dialect):
        if value is not None:
            if not isinstance(value, set):
                raise ValueError("Invalid value type. Got %r", type(value))
            value = ",".join([str(_) for _ in value])
        return value

    def process_result_value(self, value, dialect):
        return set() if value is None or len(value) == 0 \
            else set({int(_) for _ in value.split(',')})
