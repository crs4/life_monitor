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

import glob
import logging
from importlib import import_module
from os.path import basename, dirname, isfile, join

from flask.app import Flask

# set module level logger
logger = logging.getLogger(__name__)


def register_commands(app: Flask):
    modules_files = glob.glob(join(dirname(__file__), "*.py"))
    modules = ['{}.{}'.format(__name__, basename(f)[:-3])
               for f in modules_files if isfile(f) and not f.endswith('__init__.py')]
    # Load modules and register their blueprints
    errors = []
    for m in modules:
        try:
            # Try to load the command module 'm'
            mod = import_module(m)
            blueprint = None
            commands = None
            try:
                logger.debug("Looking for commands in %s.blueprint", m)
                # Lookup 'blueprint' object
                blueprint = getattr(mod, "blueprint")
                # Register the blueprint object
                app.register_blueprint(blueprint)
                logger.debug("Registered %s commands.", m)
            except AttributeError:
                logger.debug("Unable to find the 'blueprint' attribute in module %s", m)
            try:
                logger.debug("Looking for commands in '%s' module", m)
                # Lookup 'commands' object
                commands = getattr(mod, "commands")
                for c in commands:
                    app.cli.add_command(c)
            except AttributeError:
                logger.debug("Unable to find the 'commands' attribute in module %s", m)
            if not blueprint and not commands:
                errors.append(m)
        except ModuleNotFoundError:
            logger.error("ModuleNotFoundError: Unable to load module %s", m)
            errors.append(m)
    if len(errors) > 0:
        logger.error("** There were some errors loading application modules.**")
        if logger.isEnabledFor(logging.DEBUG):
            logger.error("** Unable to configure commands from %s", ", ".join(errors))
        else:
            logger.error("** Some commands may not be available.")
