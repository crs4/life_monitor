# Copyright (c) 2020-2024 CRS4
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
