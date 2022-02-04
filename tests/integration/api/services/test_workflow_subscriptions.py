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

from lifemonitor.auth.models import EventType, User, Subscription
from lifemonitor.api.services import LifeMonitor
from tests import utils

logger = logging.getLogger()


def test_submitter_workflow_subscription(app_client, lm: LifeMonitor, user1: dict, valid_workflow: str):
    _, workflow_version = utils.pick_and_register_workflow(user1, valid_workflow)
    user: User = user1['user']
    # check number of subscriptions
    assert len(user.subscriptions) == 1, "Unexpected number of subscriptions"
    # subscribe to the workflow
    s: Subscription = user.subscriptions[0]
    assert s, "Subscription should not be empty"
    assert s.resource.uuid == workflow_version.workflow.uuid, "Unexpected resource UUID"
    assert s.resource == workflow_version.workflow, "Unexpected resource instance"
    assert len(s.events) == 1, "Unexpected number of subscription events"


def test_submitter_workflow_unsubscription(app_client, lm: LifeMonitor, user1: dict, valid_workflow: str):
    _, workflow_version = utils.pick_and_register_workflow(user1, valid_workflow)
    user: User = user1['user']
    # check number of subscriptions
    assert len(user.subscriptions) == 1, "Unexpected number of subscriptions"
    # unsubscribe to workflow
    s: Subscription = lm.unsubscribe_user_resource(user, workflow_version.workflow)
    assert s, "Subscription should not be empty"
    # check number of subscriptions
    assert len(user.subscriptions) == 0, "Unexpected number of subscriptions"


def test_user_workflow_subscription(app_client, lm: LifeMonitor, user1: dict, user2: dict, valid_workflow: str):
    _, workflow = utils.pick_and_register_workflow(user1, valid_workflow)
    user: User = user2['user']
    # check number of subscriptions
    assert len(user.subscriptions) == 0, "Unexpected number of subscriptions"

    # subscribe to the workflow
    events = [EventType.BUILD_FAILED, EventType.BUILD_RECOVERED]
    s: Subscription = lm.subscribe_user_resource(user, workflow, events)
    assert s, "Subscription should not be empty"
    assert s.resource.uuid == workflow.uuid, "Unexpected resource UUID"
    assert s.resource == workflow, "Unexpected resource instance"
    assert len(s.events) == len(events), "Unexpected number of subscription events"
    for e in events:
        assert s.has_event(e), f"Subscription should be have event {e}"
    # check number of subscriptions
    assert len(user.subscriptions) == 1, "Unexpected number of subscriptions"

    # update subscription events
    events = [EventType.BUILD_FAILED]
    s: Subscription = lm.subscribe_user_resource(user, workflow, events)
    assert len(s.events) == len(events), "Unexpected number of subscription events"
    for e in events:
        assert s.has_event(e), f"Subscription should be have event {e}"

    # unsubscribe to workflow
    s: Subscription = lm.unsubscribe_user_resource(user, workflow)
    assert s, "Subscription should not be empty"
    # check number of subscriptions
    assert len(user.subscriptions) == 0, "Unexpected number of subscriptions"
