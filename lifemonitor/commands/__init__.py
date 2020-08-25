import glob
import logging
from importlib import import_module
from os.path import dirname, basename, isfile, join

# set module level logger
logger = logging.getLogger(__name__)


def register_commands(app):
    modules_files = glob.glob(join(dirname(__file__), "*.py"))
    modules = ['{}.{}'.format(__name__, basename(f)[:-3])
               for f in modules_files if isfile(f) and not f.endswith('__init__.py')]
    # Load modules and register their blueprints
    we_had_errors = False
    for m in modules:
        try:
            # Try to load the command module 'm'
            mod = import_module(m)
            try:
                logger.debug("Lookup blueprint on commands.%s", m)
                # Lookup 'blueprint' object
                blueprint = getattr(mod, "blueprint")
                # Register the blueprint object
                app.register_blueprint(blueprint)
                logger.info("Registered %s commands.", m)
            except AttributeError:
                logger.error("Unable to find the 'blueprint' attribute in module %s", m)
                we_had_errors = True
        except ModuleNotFoundError:
            logger.error("ModuleNotFoundError: Unable to load module %s", m)
            we_had_errors = True
    if we_had_errors:
        logger.error("** There were some errors loading application modules.**")
        logger.error("Some commands may not be available.")
