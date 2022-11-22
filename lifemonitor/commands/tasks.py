# Copyright (c) 2020-2022 CRS4
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


import logging
from flask.blueprints import Blueprint
from flask.cli import with_appcontext

# set module level logger
logger = logging.getLogger()

# define the blueprint for DB commands
blueprint = Blueprint('task-queue', __name__)

# set CLI help
blueprint.cli.help = "Manage task queue"


@blueprint.cli.command('reset')
@with_appcontext
def reset():
    """
    Reset task-queue status
    """
    from lifemonitor.cache import clear_cache
    from lifemonitor.tasks.config import REDIS_NAMESPACE
    try:
        clear_cache(client_scope=False, prefix=REDIS_NAMESPACE)
    except Exception as e:
        print("Error when deleting cache: %s" % (str(e)))
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
