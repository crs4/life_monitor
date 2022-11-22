"""Allow to register multiple tokens for each oauth identity

Revision ID: 94fa885a5808
Revises: bb0a4c003e28
Create Date: 2022-09-13 08:00:39.523139

"""
import logging

import json
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from lifemonitor.models import JSON


logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision = '94fa885a5808'
down_revision = 'bb0a4c003e28'
branch_labels = None
depends_on = None

# upgrade:
# op.drop_constraint('ro_crate_hosting_service_id_fkey', 'ro_crate', type_='foreignkey')
# op.create_foreign_key(None, 'ro_crate', 'resource', ['hosting_service_id'], ['id'])

# downgrade
# op.drop_constraint(None, 'ro_crate', type_='foreignkey')
# op.create_foreign_key('ro_crate_hosting_service_id_fkey', 'ro_crate', 'hosting_service', ['hosting_service_id'], ['id'])


def upgrade():

    # init DB connction
    bind = op.get_bind()
    # fetch existing tokens
    tokens = bind.execute('SELECT i.id, p.name, i.provider_user_id, i.token FROM oauth2_identity i JOIN oauth2_identity_provider p ON p.id = i.provider_id')
    # add new 'tokens' column
    op.add_column('oauth2_identity', sa.Column('tokens', JSON(), nullable=True))

    # set existing tokens on 'tokens' column
    for token in tokens:
        logger.info(f"Updating token {token[3]['scope']} for '{token[1]}' identity of user '{token[2]}'")
        scoped_token = {
            "__default__": token[3]['scope'],
            token[3]['scope']: token[3]
        }
        bind.execute(f"UPDATE oauth2_identity SET tokens = '{json.dumps(scoped_token)}' WHERE id = {token[0]}")
    # drop old token column
    op.drop_column('oauth2_identity', 'token')
    # set the NOT NULL constraint
    op.alter_column('oauth2_identity', 'tokens', nullable=False)


def downgrade():
    # init DB connction
    bind = op.get_bind()
    # fetch existing tokens
    tokens = bind.execute('SELECT i.id, p.name, i.provider_user_id, i.tokens FROM oauth2_identity i JOIN oauth2_identity_provider p ON p.id = i.provider_id')

    op.add_column('oauth2_identity', sa.Column('token', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True))
    # restore default token
    for token in tokens:
        default_token = token[3][token[3]['__default__']] if '__default__' in token[3] else None
        if default_token:
            logger.info(f"Updating token __default__ for '{token[1]}' identity of user '{token[2]}'")
            bind.execute(f"UPDATE oauth2_identity SET token = '{json.dumps(default_token)}' WHERE id = {token[0]}")
    op.drop_column('oauth2_identity', 'tokens')
    # set the NOT NULL constraint
    op.alter_column('oauth2_identity', 'token', nullable=False)
