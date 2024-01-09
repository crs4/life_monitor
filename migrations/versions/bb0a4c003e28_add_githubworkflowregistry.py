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

"""Add GithubWorkflowRegistry

Revision ID: bb0a4c003e28
Revises: 770508273f01
Create Date: 2022-05-16 23:05:07.211915

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bb0a4c003e28'
down_revision = '770508273f01'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('github_workflow_registry',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('application_id', sa.Integer(), nullable=False),
                    sa.Column('installation_id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('application_id', 'installation_id', 'user_id')
                    )
    op.create_table('github_workflow_version',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('registry_id', sa.Integer(), nullable=False),
                    sa.Column('workflow_version_id', sa.Integer(), nullable=False),
                    sa.Column('repo_identifier', sa.String(), nullable=False),
                    sa.Column('repo_ref', sa.String(), nullable=True),
                    sa.ForeignKeyConstraint(['registry_id'], ['github_workflow_registry.id'], ),
                    sa.ForeignKeyConstraint(['workflow_version_id'], ['workflow_version.id'], ),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('registry_id', 'repo_identifier', 'workflow_version_id')
                    )


def downgrade():
    op.drop_table('github_workflow_version')
    op.drop_table('github_workflow_registry')
