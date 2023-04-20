"""Track sync of builds

Revision ID: 6bb84f8b8c77
Revises: 94fa885a5808
Create Date: 2023-03-06 10:18:43.563006

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '6bb84f8b8c77'
down_revision = '94fa885a5808'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('oauth2_identity', 'tokens',
                    existing_type=postgresql.JSONB(astext_type=sa.Text()),
                    nullable=True)
    op.drop_constraint('ro_crate_hosting_service_id_fkey', 'ro_crate', type_='foreignkey')
    op.create_foreign_key(None, 'ro_crate', 'resource', ['hosting_service_id'], ['id'])
    op.add_column('test_instance', sa.Column('last_builds_update', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('test_instance', 'last_builds_update')
    op.drop_constraint(None, 'ro_crate', type_='foreignkey')
    op.create_foreign_key('ro_crate_hosting_service_id_fkey', 'ro_crate', 'hosting_service', ['hosting_service_id'], ['id'])
    op.alter_column('oauth2_identity', 'tokens',
                    existing_type=postgresql.JSONB(astext_type=sa.Text()),
                    nullable=False)
