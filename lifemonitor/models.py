
import uuid
from sqlalchemy.dialects.postgresql import UUID

from .config import db

class Workflow(db.Model):
    workflow_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(), nullable=False)

    def __repr__(self):
        return '<Workflow %r; name: %r>'.format(self.workflow_id, self.name)
