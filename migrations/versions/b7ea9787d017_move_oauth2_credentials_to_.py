"""Move oauth2 credentials to HostingService model

Revision ID: b7ea9787d017
Revises: 7e9e009f4dbb
Create Date: 2022-03-10 16:23:11.034346

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7ea9787d017'
down_revision = '7e9e009f4dbb'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # get existing workflow registries
    registries = bind.execute("SELECT id,_client_id,_server_id from workflow_registry")
    # extend hosting service table with Oauth2 credentials
    op.add_column('hosting_service', sa.Column('client_id', sa.Integer(), nullable=True))
    op.add_column('hosting_service', sa.Column('server_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'hosting_service', 'oauth2_client', ['client_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'hosting_service', 'oauth2_identity_provider', ['server_id'], ['id'], ondelete='CASCADE')
    # copy registry credentials to hosting_service table
    for r in registries:
        bind.execute(f"UPDATE hosting_service SET client_id = {r[1]}, server_id = {r[2]} WHERE id = {r[0]}")
    op.drop_constraint('workflow_registry__client_id_fkey', 'workflow_registry', type_='foreignkey')
    op.drop_constraint('workflow_registry__server_id_fkey', 'workflow_registry', type_='foreignkey')
    op.drop_column('workflow_registry', '_server_id')
    op.drop_column('workflow_registry', '_client_id')


def downgrade():
    bind = op.get_bind()
    # get existing hosting services
    hosting_services = bind.execute("SELECT id, client_id, server_id from hosting_service")
    # update schema
    op.add_column('workflow_registry', sa.Column('_client_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('workflow_registry', sa.Column('_server_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key('workflow_registry__server_id_fkey', 'workflow_registry', 'oauth2_identity_provider', ['_server_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('workflow_registry__client_id_fkey', 'workflow_registry', 'oauth2_client', ['_client_id'], ['id'], ondelete='CASCADE')
    # copy registry credentials to workflow_registry table
    for h in hosting_services:
        bind.execute(f"UPDATE workflow_registry SET _client_id = {h[1]}, _server_id = {h[2]} WHERE id = {h[0]}")
    op.drop_column('hosting_service', 'server_id')
    op.drop_column('hosting_service', 'client_id')
