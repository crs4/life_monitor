"""Automatically register submitter subscription to workflows

Revision ID: 296634f13bc4
Revises: a46c90bedbbf
Create Date: 2022-01-24 14:07:00.098626

"""
import logging
from datetime import datetime

from alembic import op

# set logger
logger = logging.getLogger('alembic.env')


# revision identifiers, used by Alembic.
revision = '296634f13bc4'
down_revision = 'a46c90bedbbf'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    res = bind.execute('SELECT * from workflow_version WHERE workflow_id NOT IN (SELECT resource_id FROM subscription)')
    logger.info(res)
    for wdata in res:
        logger.info("(v_id,submitter,wf_id)=(%d,%d,%d)", wdata[0], wdata[1], wdata[2])
        now = datetime.utcnow()
        bind.execute(f"INSERT INTO subscription (user_id,created,modified,resource_id,events) VALUES ({wdata[1]},TIMESTAMP '{now}',TIMESTAMP '{now}',{wdata[2]},'0')")


def downgrade():
    pass
