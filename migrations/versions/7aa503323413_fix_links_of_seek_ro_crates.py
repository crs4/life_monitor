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
