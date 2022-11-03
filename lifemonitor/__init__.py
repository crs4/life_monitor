# Copyright (c) 2020-2021 CRS4
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitatioån the rights
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


def get_version():
    import os
    import re
    from ._version import get_versions, run_command

    # try to read the version from the environment
    version = os.environ.get("LM_SW_VERSION", None)
    if not version:
        # if LM_SW_VERSION is not defined on the environment,
        # try to extract the software version from git metadata
        version = get_versions()['version']
        # if no tag can be extracted from git metadata,
        # try to use the git branch name to tag the software version
        branch, rc = run_command(["git"], ["branch", "--show-current"],
                                 cwd=os.path.dirname(__file__), hide_stderr=True)
        if rc == 0:
            # tag the version using the branch (normalized through removing '/' char)
            branch = branch.replace('/', '-')
            version = re.sub(r'(untagged)(\.1)?', branch, version)

    # try to read the LM_BUILD_NUMBER from the environment
    # and append it to the version tag
    build_number = os.environ.get("LM_BUILD_NUMBER", None)
    if build_number and version:
        version = f"{version}.build{build_number}"

    return version


__version__ = get_version()
