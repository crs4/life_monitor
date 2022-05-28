# Copyright (c) 2020-2021 CRS4
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
import inspect
import logging
import os
from importlib import import_module
from pathlib import Path
from typing import Dict, List

# set module level logger
logger = logging.getLogger(__name__)


__modules_files__ = glob.glob(os.path.join(os.path.dirname(__file__), "*.py"))
__modules__ = {os.path.basename(f)[:-3]: '{}.{}'.format(__name__, os.path.basename(f)[:-3])
               for f in __modules_files__ if os.path.isfile(f) and not f.endswith('__init__.py')}
logger.debug("Loaded modules of RO-Crate generators: %r", __modules__)


class GenCrateConfig:
    def __init__(self, opts: Dict) -> None:
        for k, v in opts.items():
            setattr(self, k, v)


def get_supported_workflow_types() -> List[str]:
    return list(__modules__.keys())


def generate_crate(workflow_type: str, workflow_version: str,
                   local_repo_path: str,
                   repo_url: str = None, license: str = "MIT", **kwargs):

    make_crate = get_crate_generator(workflow_type)
    if not make_crate:
        m = "Unable to find a generator for the workflow type '%s'" % workflow_type
        logger.error(m)
        raise RuntimeError(m)

    # TODO: generalize the config object to
    #       other types of generators and CI instances.
    #       The current implementation only supports Snakemake and Github CI
    cfg = {
        "root": Path(local_repo_path),
        "output": local_repo_path,
        "repo_url": repo_url,
        "version": workflow_version,
        "license": license,
        "ci_workflow": kwargs.get('ci_workflow', 'main.yml'),
        "lang_version": kwargs.get('lan_version', '0.6.5')
    }
    opts = GenCrateConfig(cfg)
    logger.warning("Config: %r", cfg)
    make_crate(opts)


def get_crate_generator(workflow_type: str):
    mod_name = __modules__.get(workflow_type, None)
    if not mod_name:
        raise NotImplementedError('No RO-Crate generator for workflow type "%s"', workflow_type)
    try:
        mod = import_module(mod_name)
        make_crate = getattr(mod, "make_crate")
        logger.debug("Found make_crate: %r", make_crate)
        if not inspect.isfunction(make_crate):
            logger.warning("'make_crate' in %r is not a function")
        return make_crate
    except ModuleNotFoundError:
        logger.error("ModuleNotFoundError: Unable to load module %s", mod_name)
    except AttributeError:
        logger.error("AttributeError: Unable to find function make_crate on module %s", mod)
    return None


__all__ = [get_crate_generator, get_supported_workflow_types]
