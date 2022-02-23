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

no_user_in_session = "No user nor registry found in the current session"
no_registry_uri_provided = "The user should provide a 'registry_uri'"
unexpected_registry_uri = "The 'registry_uri' should not be provided by a client registry"
missing_registry_param = "Missing registry parameter"
no_registry_found = "Unable to find the registry {}"
no_submitter_id_provided = "The registry client should provide a 'submitter_id'"
no_user_oauth_identity_on_registry = "Unable to link the identity of user '{}' on the registry '{}' (not authorized yet)"
no_test_suite = "No test suite configured for this workflow"
no_build_found_for_instance = "No build found for instance {}"
no_test_instance_for_suite = "No test instances configured for suite {}"
not_authorized_registry_access = "User not authorized to access the registry '{}'"
not_authorized_workflow_access = "User not authorized to get workflow data"
input_data_missing = "One or more input data are missing"
decode_ro_crate_error = "Unable to decode the RO Crate: it should be encoded using base64"
invalid_ro_crate = "RO Crate processing exception"
workflow_not_found = "Workflow '{}' (ver.{}) not found"
workflow_version_conflict = "Workflow '{}' (ver.{}) already exists"
suite_not_found = "Suite '{}' not found"
instance_not_found = "Test instance '{}' not found"
instance_build_not_found = "Unable to find the build '{}' on test instance '{}'"
unauthorized_workflow_access = "Unauthorized to access workflow '{}'"
unauthorized_user_suite_access = "The user '{}' cannot access suite '{}'"
unauthorized_registry_suite_access = "The registry '{}' cannot access suite '{}'"
unauthorized_user_instance_access = "The user '{}' cannot access test instance '{}'"
unauthorized_registry_instance_access = "The registry '{}' cannot access test instance '{}'"
unable_to_delete_workflow = "Unable to delete the workflow '{}'"
unable_to_delete_suite = "Unable to delete the suite '{}'"
unauthorized_no_user_nor_registry = "No user nor registry found in the current session"
unauthorized_user_without_registry_identity = ("The current user has not authorized LifeMonitor "
                                               "to use his account on the registry '{}'. "
                                               "Please redirect the user to the 'authorization_url' "
                                               "to start the authorization flow")
unauthorized_user_with_expired_registry_token = ("The current token issued by the registry '{}' "
                                                 "has expired. Please reauthorize the user '{}'"
                                                 "Please redirect the user to the 'authorization_url' "
                                                 "to start the authorization flow")
invalid_log_offset = "Invalid offset: it should be a positive integer"
invalid_log_limit = "Invalid limit: it should be a positive integer"
invalid_event_type = "Invalid event type. Accepted values are {}"
notification_not_found = "Notification '{}' not found"
forbidden_roclink_or_rocrate_for_registry_workflows = "Registry workflows cannot be updated through external roc_link or rocrate"
