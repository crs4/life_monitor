
# Register and query a workflow with the LifeMonitor CLI

You can register a workflow with the LifeMonitor service so that it can help you
maintain it over time.  Currently, LifeMonitor's main feature is monitoring
periodically executed workflow tests to detect when things stop working as
expected.

We're going to show you how to register a workflow included
with LifeMonitor.

Before proceeding, you need to configure your [Restish CLI to access
LifeMonitor](restish-cli).  In the examples below we have configured the
LifeMonitor API in Restish to be called `lm` -- i.e.,

    restish api configure lm https://api.lifemonitor.eu

Follow the full instructions on configuring [Restish to access
LifeMonitor](restish-cli) so that you properly configure the authentication
mechanism.


## Example workflow

We're going to use an example [Workflow Testing
  RO-crate](https://www.lifemonitor.eu/workflow_testing_ro_crate) provided in the [LifeMonitor
repository](https://github.com/crs4/life_monitor/tree/master/examples).  The
RO-crate contains the simple `sort-and-change-case.ga` Galaxy workflow and
defines a testing instance that runs on the [TravisCI](https://travis-ci.org/)
service:
```
  {
      "@id": "#test1_1",
      "name": "test1_1",
      "@type": "TestInstance",
      "runsOn": {"@id": "https://w3id.org/ro/terms/test#TravisService"},
      "url": "https://api.travis-ci.org",
      "resource": "repo/1002447"
  }
```

The RO-crate is [hosted on
Github](https://github.com/crs4/life_monitor/raw/master/examples/example-wf-crate.zip)
and is accessible to the public; LifeMonitor will download it from there.

## Registering the workflow

To register the workflow with LifeMonitor, we will send a POST request to the [`/users/current/workflows`](https://api.lifemonitor.eu/static/apidocs.html#post-/users/current/workflows)
API endpoint.  Restish lets us call it with the `user-workflows-post`
subcommand:

```
$ echo '{"version": "1.0"}' | restish lm user-workflows-post roc_link: "https://github.com/crs4/life_monitor/raw/master/examples/example-wf-crate.zip"

HTTP/1.0 201 Created
Access-Control-Allow-Origin: *
Content-Length: 124
Content-Type: application/json
Date: Wed, 07 Jul 2021 08:18:07 GMT
Server: Werkzeug/2.0.1 Python/3.7.9
Set-Cookie: session=.eJwlzkEOwkAIAMC_7NkD0GVh-xkDLESvrT0Z_66J84J5t3sdeT7a_jquvLX7c7W9KRk6utsIVgXdhECGF29gxkGrGBypK-E0ngpuuWirVXOMxATrA2KhbiRYsRKCLcsnigqbOBC6dq2-Ij2QlHsVgalMAYj2i1xnHv8Nts8XtT0vTA.YOVjPw.smgmVEBJFK2Q1tRqhxHlsbs8aMA; HttpOnly; Path=/
Vary: Cookie

{
  name: "galaxy-workflow-example-with-tests"
  uuid: "46a1812c-8743-4333-bd6c-e7954c559cb1"
  wf_version: "1.0"
}
```

:exclamation: Notice that we can provide property values (i.e., `roc_link` and `version`) for
the object to be POSTed both via stdin and via command line arguments.  In this
specific case, we have to provide this version value through stdin:

    echo '{"version": "1.0"}' |

This is to keep Restish from converting the value to a number (the version *must*
be a string). For more details about how to provide parameters through Restish [see
its documentation](https://rest.sh/#/input).

### Response

:bulb: LifeMonitor responded to the call with the UUID, version and name of the
workflow.  The UUID will be used for all operations on this workflow.

### More registration arguments

The API call [`POST
/users/current/workflows`](https://api.lifemonitor.eu/static/apidocs.html#post-/users/current/workflows)
accepts various additional arguments that may be useful for your particular use
case; they are listed below.  For the most up-to-date reference always refer to
[the API docs](https://api.lifemonitor.eu/static/apidocs.html#post-/users/current/workflows).


| Argument               | Explanation                                                                             |
| ---                    | ---                                                                                     |
| `roc_link` (mandatory) | Link to the Workflow RO-Crate. Link must be accessible to LM                            |
| `version` (mandatory)  | Version of the workflow                                                                 |
| `authorization`        | If the `roc_link` requires it, you can provide an authorization header                  |
| `uuid`                 | Optional UUID for the workflow. If not provided, LM will generate one                   |
| `name`                 | A name for the workflow. If not provided, the RO-Crate dataset name is used as default. |



## Querying

Now that you have registered the workflow and its test instance, you can query
LM for information.

Get a list of the workflows you registered with LM:

    $ restish lm user-workflows-get

Restish will print out a list with various details about your workflows,
including aggregate test status and information about the latest test build.  As
usual, refer to the [LM API
specs](https://api.lifemonitor.eu/static/apidocs.html#get-/users/current/workflows)
for the full specification of the response.

### Filtering and projecting results

Restish [supports
JMESPath](https://rest.sh/#/output?id=filtering-amp-projection) to filter and
project results as JSON (as usual, see the Restish documentation for full details).

:exclamation: The first thing to notice is that Restish does not print out the
whole response as JSON, but prints things in a way that are easier to read.  To
see the JSON structure that you will be filtering and projecting specify `-o
json`:

    $ restish lm -o json user-workflows-get
    {
      "body": {
        "items": [
          {
            "latest_version": "1",
            "name": "COVID-19: variation analysis on ARTIC PE data",
            "status": {
              "aggregate_test_status": "all_passing",
              "latest_build": {
                "build_id": "769307075",
                "instance": {
                  "managed": false,
    ...


Now, for instance, we can query just the workflow name, uuid and testing status for all our workflows:

    $ restish lm user-workflows-get -f 'body.items[*].{name: name, uuid: uuid, status: status.aggregate_test_status}' 
    [
      {
        "name": "galaxy-workflow-example-with-tests",
        "status": "all_passing",
        "uuid": "46a1812c-8743-4333-bd6c-e7954c559cb1"
      },
      {
        "name": "COVID-19: variation analysis on ARTIC PE data",
        "status": "all_passing",
        "uuid": "143cc7a0-8e3a-0139-2e05-005056ab5db4"
      }
    ]

In the following examples, remember to replace the workflow ID with the one you got upon registering it.

### Query information about your workflow

    $  restish lm workflows-get-latest-version-by-id 46a1812c-8743-4333-bd6c-e7954c559cb1
    {
      meta: {...}
      name: "galaxy-workflow-example-with-tests"
      uuid: "46a1812c-8743-4333-bd6c-e7954c559cb1"
      version: {
        is_latest: true
        ro_crate: {
          links: {
            download: "https://api.lifemonitor.eu/ro_crates/13/download"
            external: "https://github.com/crs4/life_monitor/raw/master/examples/example-wf-crate.zip"
          }
        }
        submitter: {
          id: 4
          username: "ilveroluca"
        }
        uuid: "8bc4c898-1880-4e34-8392-404619c2b5d5"
        version: "1.0"
      }
    }

### Query your workflow's test status

    $ restish lm workflows-get-status 46a1812c-8743-4333-bd6c-e7954c559cb1
    {
      aggregate_test_status: "all_passing"
      latest_builds: [
        {
          build_id: "642913559"
          instance: {
            managed: false
            name: "test1_1"
            resource: "repo/1002447"
            roc_instance: "#test1_1"
            service: {
              type: "travis"
              url: "https://api.travis-ci.org"
              uuid: "0a3c891f-8fc8-41ff-807a-36c4b9f60c31"
            }
            uuid: "0721e277-d54d-465e-b5a7-6509379adb02"
          }
          status: "passed"
          suite_uuid: "359a1a37-f71a-4140-b17e-0d30e0165e27"
          timestamp: "1580286172.0"
        }
      ]
    ...

### Query the test instances that are registered

    $ restish lm workflows-get-suites 46a1812c-8743-4333-bd6c-e7954c559cb1
    {
      items: [
        {
          definition: {
            test_engine: {
              type: "planemo"
              version: ">=0.70"
            }
          }
          instances: [
            {
              managed: false
              name: "test1_1"
              resource: "repo/1002447"
              roc_instance: "#test1_1"
              service: {
                type: "travis"
                url: "https://api.travis-ci.org"
                uuid: "0a3c891f-8fc8-41ff-807a-36c4b9f60c31"
              }
              uuid: "0721e277-d54d-465e-b5a7-6509379adb02"
            }
          ]
          roc_suite: "#test1"
          uuid: "359a1a37-f71a-4140-b17e-0d30e0165e27"
        }
      ]
    ...

## Going further

You can access all the API resources provided by LifeMonitor in this way.
Explore [the API specs](https://api.lifemonitor.eu/static/apidocs.html) to see
all the functionality that is available.
