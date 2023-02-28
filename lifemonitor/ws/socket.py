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
import os

logger = logging.getLogger(__name__)


def run(app: None, port=8001, host: str = "0.0.0.0"):
    from lifemonitor.app import create_app

    from . import initialise_ws

    # create an app instance
    application = app or create_app(load_jobs=False)

    # init ws middleware
    socketIO = initialise_ws(application)

    # Start Flask App + SocketIO
    socketIO.run(application, host="0.0.0.0", port=8001, engineio_logger=False,
                 keyfile=os.environ.get("LIFEMONITOR_TLS_KEY", './certs/lm.key'),
                 certfile=os.environ.get("LIFEMONITOR_TLS_CERT", './certs/lm.crt'))


if __name__ == '__main__':
    run()
