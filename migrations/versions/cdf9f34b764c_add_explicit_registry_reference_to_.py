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

"""Add explicit registry reference to WorkflowVersion model

Revision ID: cdf9f34b764c
Revises: b7ea9787d017
Create Date: 2022-03-10 17:19:26.986500

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cdf9f34b764c'
down_revision = 'b7ea9787d017'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # reference to the existing RO Crates
    ro_crates = bind.execute("SELECT id,hosting_service_id FROM ro_crate")
    # add registry reference to workflow_registry table
    op.add_column('workflow_version', sa.Column('registry_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'workflow_version', 'workflow_registry', ['registry_id'], ['id'])
    # copy hosting_service to workflow_version as registry
    for c in ro_crates:
        if c[1]:
            bind.execute(f"UPDATE workflow_version SET registry_id = {c[1]} WHERE id = {c[0]}")


def downgrade():
    bind = op.get_bind()
    # reference to the existing workflow versions
    versions = bind.execute("SELECT id,registry_id FROM workflow_version")
    # update scheme
    op.drop_constraint(None, 'workflow_version', type_='foreignkey')
    op.drop_column('workflow_version', 'registry_id')
    # copy registry to ro-crate as hosting_service
    for v in versions:
        bind.execute(f"UPDATE ro_crate SET hosting_service_id = {v[1]} WHERE id = {v[0]}")
