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
from pathlib import Path
from typing import List, Optional

# set module level logger
logger = logging.getLogger(__name__)


def get_supported_workflow_types() -> List[str]:
    from repo2rocrate.cli import GEN_MAP
    return list(GEN_MAP.keys())


def generate_crate(workflow_type: str,
                   workflow_name: str,
                   workflow_version: str,
                   local_repo_path: str,
                   repo_url: Optional[str],
                   license: Optional[str] = None,
                   ci_workflow: Optional[str] = None,
                   lang_version: Optional[str] = None,
                   **kwargs):
    make_crate = get_crate_generator(workflow_type)
    if not make_crate:
        m = "Unable to find a generator for the workflow type '%s'" % workflow_type
        logger.error(m)
        raise RuntimeError(m)

    # TODO: generalize the config object to
    #       other types of CI instances.
    #       The current implementation only supports Github CI
    cfg = {
        "root": Path(local_repo_path),
        "repo_url": repo_url,
        "wf_name": workflow_name,
        "wf_version": workflow_version,
        "license": license,
        "ci_workflow": ci_workflow,
        "lang_version": lang_version
    }
    logger.debug("Config: %r", cfg)
    crate = make_crate(**cfg)
    crate.write(local_repo_path)
    return crate


def get_crate_generator(workflow_type: str):
    try:
        import repo2rocrate
        make_crate = repo2rocrate.LANG_MODULES[workflow_type].make_crate
        logger.debug("Found crate generator: %r", make_crate)
        return make_crate
    except ModuleNotFoundError:
        raise NotImplementedError('No RO-Crate generator for workflow type "%s"' % workflow_type)
    except AttributeError:
        logger.error("AttributeError: Unable to find function make_crate on module %s", workflow_type)
    return None


__all__ = [get_crate_generator, get_supported_workflow_types]
