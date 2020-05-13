
import logging
import os

import connexion

from flask_sqlalchemy import SQLAlchemy

logger = logging.getLogger('lm')

def db_uri():
    if os.getenv('DATABASE_URI'):
        uri = os.getenv('DATABASE_URI')
    else:
        uri = "postgresql://{user}:{passwd}@{host}/{dbname}".format(
            user=os.getenv('POSTGRESQL_USERNAME', 'lm'),
            passwd=os.getenv('POSTGRESQL_PASSWORD', ''),
            host=os.getenv('POSTGRESQL_HOST', 'db'),
            dbname=os.getenv('POSTGRESQL_DATABASE'))
    return uri


base_dir = os.path.abspath(os.path.dirname(__file__))
connex_app = connexion.App('LM', specification_dir=base_dir)
flask_app = connex_app.app
flask_app.config['SQLALCHEMY_DATABASE_URI'] = db_uri()

# FSADeprecationWarning: SQLALCHEMY_TRACK_MODIFICATIONS adds significant
# overhead and will be disabled by default in the future.  Set it to True
# or False to suppress this warning.
flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(flask_app)
