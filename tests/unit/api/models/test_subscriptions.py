
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

from lifemonitor.auth.models import Subscription, User, EventType
from tests import utils

logger = logging.getLogger()


def test_workflow_subscription(user1: dict, valid_workflow: str):
    _, workflow_version = utils.pick_and_register_workflow(user1, valid_workflow)
    user: User = user1['user']

    # check default subscription
    s = user.get_subscription(workflow_version.workflow)
    assert s, "The submitter subscription should be automatically registered"
    # check default events
    assert len(s.events) == 1, "Invalid number of events"
    assert s.has_event(EventType.ALL), f"Event '{EventType.ALL.name}' not registered on the subscription"
    for event in EventType.list():
        assert s.has_event(event), f"Event '{event.name}' should be included"

    # check delete all events
    s.events = None
    assert len(s.events) == 0, "Invalid number of events"
    s.save()

    # check event udpate
    s.events = [EventType.BUILD_FAILED, EventType.BUILD_RECOVERED]
    s.save()
    assert len(s.events) == 2, "Invalid number of events"
    assert not s.has_event(EventType.ALL), f"Event '{EventType.ALL.name}' should not be registered on the subscription"


def test_workflow_unsubscription(user1: dict, valid_workflow: str):
    _, workflow_version = utils.pick_and_register_workflow(user1, valid_workflow)
    user: User = user1['user']

    # check default subscription
    s = user.get_subscription(workflow_version.workflow)
    assert s, "The submitter subscription should be automatically registered"

    # test unsubscription
    user.unsubscribe(workflow_version.workflow)
    user.save()
    assert len(user.subscriptions) == 0, "Unexpected number of subscriptions"
    s = user.get_subscription(workflow_version.workflow)
    assert s is None, "Subscription should be empty"
