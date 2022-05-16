"""Add client_name property on OAuth2Provider

Revision ID: 770508273f01
Revises: 64564b96c9db
Create Date: 2022-05-12 20:09:43.177927

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '770508273f01'
down_revision = '64564b96c9db'
branch_labels = None
depends_on = None



def upgrade():
    bind = op.get_bind()
    providers = bind.execute("SELECT id, name FROM oauth2_identity_provider")
    op.add_column('oauth2_identity_provider', sa.Column('client_name', sa.String(), nullable=True))
    for p in providers:
        bind.execute(f"UPDATE oauth2_identity_provider SET client_name = '{p[1]}' WHERE id = {p[0]}")
    # set constraints
    op.alter_column('oauth2_identity_provider', 'client_name', nullable=False)
    op.create_unique_constraint(None, 'oauth2_identity_provider', ['client_name'])


def downgrade():
    op.drop_constraint(None, 'oauth2_identity_provider', type_='unique')
    op.drop_column('oauth2_identity_provider', 'client_name')
