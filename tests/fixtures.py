import json
import os
import sys
import uuid
import connexion
import pytest
import logging
from dotenv import load_dotenv
from lifemonitor import model, config
from lifemonitor.model import db

# set the module level logger
logger = logging.getLogger(__name__)

# add lifemonitor and tests to the Python PATH
base_path = os.path.dirname(__file__)
sys.path.extend((base_path, os.path.abspath("lifemonitor")))

# load env
env_path = os.path.join(base_path, 'settings.conf')
env = load_dotenv(dotenv_path=env_path)

# global test data
workflow_uuid = str(uuid.uuid4())
workflow_version = "1.0"
workflow_name = "Test Workflow"
workflow_roc_link = "http://172.30.10.100:3000/workflows/2/ro_crate?version=1"


@pytest.fixture
def clean_db():
    for table in reversed(db.metadata.sorted_tables):
        db.session.execute(table.delete())
    db.session.commit()


@pytest.fixture
def client():
    base_dir = os.path.abspath("lifemonitor")
    connex_app = connexion.App('LM', specification_dir=base_dir)
    flask_app = connex_app.app
    flask_app.config['TESTING'] = True
    # db_fd, db_path = tempfile.mkstemp(dir="db_tmp")
    # db_path = "db_tmp/tests.db"
    # os.environ['DATABASE_URI'] = "sqlite:///{}".format(db_path)
    with flask_app.test_client() as client:
        with flask_app.app_context():
            model.config_db_access(flask_app)
            config.configure_logging(flask_app)
            connex_app.add_api('api.yaml', validate_responses=True)
            logger.info("Starting application")
            yield client

    # os.close(db_fd)
    # os.unlink(db_path)
    # print("DataBase path: %s" % db_path)


@pytest.fixture
def headers():
    return {'Content-type': 'application/json', 'Accept': 'text/plain'}


@pytest.fixture
def test_suite_metadata():
    with open(os.path.join(base_path, "test-suite-definition.json")) as df:
        return json.load(df)


@pytest.fixture
def suite_uuid():
    return str(model.TestSuite.all()[0].uuid)
