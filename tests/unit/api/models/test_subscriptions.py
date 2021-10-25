
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


import logging

from lifemonitor.auth.models import Subscription, User
from tests import utils

logger = logging.getLogger()


def test_workflow_subscription(user1: dict, valid_workflow: str):
    _, workflow = utils.pick_and_register_workflow(user1, valid_workflow)
    user: User = user1['user']
    s: Subscription = user.subscribe(workflow)
    logger.debug("Subscription: %r", s)
    assert s, "Subscription should not be empty"
    assert len(user.subscriptions) == 1, "Unexpected number of subscriptions"

    s: Subscription = user.unsubscribe(workflow)
    logger.debug("Subscription: %r", s)
    assert s, "Subscription should not be empty"
    assert len(user.subscriptions) == 0, "Unexpected number of subscriptions"
