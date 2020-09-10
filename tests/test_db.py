import pytest
import logging
import lifemonitor.db as lm_db

logger = logging.getLogger()

db_settings = {
    "POSTGRESQL_DATABASE": "just_another_db"
}


@pytest.mark.parametrize("parametric_app_context", [db_settings], indirect=True)
def test_db_connection_uri(parametric_app_context):
    app_config = parametric_app_context.app.config
    logger.debug("DB URI from app config: %r", app_config["SQLALCHEMY_DATABASE_URI"])
    assert app_config.get("SQLALCHEMY_DATABASE_URI") == lm_db.db_uri(db_settings), \
        "The SQLAlchemy instance is not using the expected URI"
