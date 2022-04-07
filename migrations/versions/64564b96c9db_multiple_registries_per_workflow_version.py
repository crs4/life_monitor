"""Multiple registries per workflow version

Revision ID: 64564b96c9db
Revises: fc06761a2da4
Create Date: 2022-04-06 16:47:46.820983

"""
import logging
from alembic import op
import sqlalchemy as sa


# set logger
logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision = '64564b96c9db'
down_revision = 'fc06761a2da4'
branch_labels = None
depends_on = None


def upgrade():
    # init DB connction
    bind = op.get_bind()
    # fetch existing registry workflow versions
    wvs = bind.execute('SELECT rw.id, rw.uuid, rw.uri, rv.id, rv.uuid, rv.uri, rv.version, v.registry_id, rv.created, rv.modified '
                       'FROM resource rw NATURAL JOIN workflow w JOIN workflow_version v ON w.id = v.workflow_id JOIN resource rv ON rv.id = v.id '
                       'WHERE v.registry_id IS NOT NULL;')

    # update schema
    op.create_table('registry_workflow_version',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('workflow_version_id', sa.Integer(), nullable=True),
                    sa.Column('registry_id', sa.Integer(), nullable=True),
                    sa.ForeignKeyConstraint(['id'], ['resource.id'], ),
                    sa.ForeignKeyConstraint(['registry_id'], ['workflow_registry.id'], ),
                    sa.ForeignKeyConstraint(['workflow_version_id'], ['workflow_version.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.drop_constraint('workflow_version_registry_id_fkey', 'workflow_version', type_='foreignkey')
    op.drop_column('workflow_version', 'registry_id')

    # map existing registry workflow version to the new schema
    for wv in wvs:
        logger.info("%r %r", wv[0], wv[1])
        r_id = bind.execute("SELECT nextval('resource_id_seq')").fetchall()[0][0]
        bind.execute(f"INSERT INTO resource (id, uuid, type, uri, version, created, modified) "
                     f"VALUES('{r_id}','{wv[1]}','registry_workflow_version','{wv[2]}', '{wv[6]}', '{wv[8]}', now())")
        bind.execute(f"INSERT INTO registry_workflow_version (id, workflow_version_id, registry_id) VALUES ('{r_id}', '{wv[3]}', '{wv[7]}')")


def downgrade():
    # init DB connction
    bind = op.get_bind()
    # fetch existing registry workflow versions
    wvs = bind.execute('SELECT rv.id, rv.uuid, rv.uri, v.registry_id, v.workflow_version_id, rv.created, rv.modified '
                       'FROM resource rv NATURAL JOIN registry_workflow_version v ;')

    # downgrade schema version
    op.add_column('workflow_version', sa.Column('registry_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key('workflow_version_registry_id_fkey', 'workflow_version', 'workflow_registry', ['registry_id'], ['id'])
    op.drop_table('registry_workflow_version')

    # map existing registry workflow version to the old schema
    for wv in wvs:
        logger.info("%r %r", wv[0], wv[1])
        bind.execute(f"UPDATE workflow_version SET registry_id = {wv[3]} WHERE id = {wv[4]}")
        bind.execute(f"UPDATE resource SET modified = now() WHERE id = {wv[4]}")
    bind.execute("DELETE FROM resource WHERE type = 'registry_workflow_version'")
