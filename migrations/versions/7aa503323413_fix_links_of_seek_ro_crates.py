"""Fix links of Seek RO-Crates

Revision ID: 7aa503323413
Revises: bbe1397dc8a9
Create Date: 2021-10-06 14:16:09.851731

"""

import logging
from lifemonitor.api import models

# revision identifiers, used by Alembic.
revision = '7aa503323413'
down_revision = 'bbe1397dc8a9'
branch_labels = None
depends_on = None

# set logger
logger = logging.getLogger('alembic.env')


def upgrade():
    workflows = models.WorkflowVersion.all()
    for w in workflows:
        if w.hosting_service and w.hosting_service.type == 'seek_registry':
            w.uri = w.hosting_service.get_rocrate_external_link(w.workflow.external_id, w.version)
            w.save()
            logger.info(f"URI of seek workflow {w.workflow.uuid} upgraded to: {w.uri}")


def downgrade():
    pass
