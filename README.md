# Life Monitor

Workflow testing and monitoring service.

Life Monitor aims to facilitate the execution, monitoring and sharing of tests
for workflows over time, ensuring that deviations from correct operation are
detected and communicated to the workflow authors so that they might be
solved, thus extending the useful life of the workflow.

See the [wiki](https://github.com/crs4/life_monitor/wiki) for additional information.

Life Monitor is being developed as part of the [EOSC-Life project](https://www.eosc-life.eu/).


## Developing

Look over `settings.conf` and verify/customize the default settings.

Basic actions are implemented as Makefile rules.

| Purpose | command |
|---------|---------|
| Building docker images | make |
| Launch the docker-compose | make start |
| Stop the docker-compose | make stop |
| Launch docker-compose in development mode | make startdev |
| Stop docker-compose in development mode | make stopdev |

The development mode mount the life monitor directory within the container and
runs flask in development mode.  Thus, local changes to the code are immediately
picked up.


### Connecting to the docker-compose

After starting the docker-compose, by default the https proxy for the `lm`
service listens on port 8443:

    $ curl --insecure https://localhost:8443/workflows
    []


The `--insecure` (also `-k`) option will be required unless you're using your own signed
certificates.


## Exploring API / User interface

The web service has a built-in Swagger UI (thanks to
[connexion](https://connexion.readthedocs.io/en/latest/)).  When the
docker-compose is running, you can access the UI at `/ui`.  The full OpenAPI
specification is always in the source code repository under
[lifemonitor/api.yaml](specs/api.yaml) and a "beautified" html version is
available [here](https://crs4.github.io/life_monitor/).


## Connecting with WorkflowHub

You can run an instance of the WorkflowHub and LifeMonitor on the same host,
each in their own docker-compose.  See the `docker-compose-template.yml` file to
set the name of the docker network the WHub docker-compose created, then the LM
containers will be created attached to that same network and the services will
see each other.  You will also neet to set `WORKFLOW_REGISTRY_URL` appropriately
in `settings.conf`.


## Simple example with cURL

Before starting the development environment, you can configure a static
authentication token of your liking in `settings.conf`.  You'll be able to use
it to authenticate your requests.

These examples are 
```
$ curl -k -H 'Authorization: bearer mytoken' \
          -H 'Content-Type: application/json' \
          -d '{ "name": "nf-kmer-similarity", \
                "uuid": "8ad80dc7-dfb8-4fa5-b443-664689714bdb", \
                "version": "1", \
                "roc_link": "https://dev.workflowhub.eu/workflows/21/ro_crate?version=1" }' \
          https://localhost:8443/workflows
{
  "version": "1",
  "wf_uuid": "8ad80dc7-dfb8-4fa5-b443-664689714bdb"
}


$ curl -k https://localhost:8443/workflows
[
  {
    "isHealthy": true,
    "name": "test1",
    "roc_link": "\"http://172.30.10.90:3000\"/workflow/8ad80dc7-dfb8-4fa5-b443-664689714bdb?version=1",
    "uuid": "8ad80dc7-dfb8-4fa5-b443-664689714bdb",
    "version": "1"
  }
]

$ curl -k https://localhost:8443/workflows/8ad80dc7-dfb8-4fa5-b443-664689714bdb/1
{
  "isHealthy": true,
  "name": "test1",
  "roc_link": "\"http://172.30.10.90:3000\"/workflow/8ad80dc7-dfb8-4fa5-b443-664689714bdb?version=1",
  "uuid": "8ad80dc7-dfb8-4fa5-b443-664689714bdb",
  "version": "1"
}


$ curl -k -H 'Authorization: bearer mytoken' \
       -X DELETE https://localhost:8443/workflows/8ad80dc7-dfb8-4fa5-b443-664689714bdb/1

$ curl -k -i https://localhost:8443/workflows/8ad80dc7-dfb8-4fa5-b443-664689714bdb/1
HTTP/1.0 404 NOT FOUND
Content-Type: application/json
Content-Length: 0
Server: Werkzeug/1.0.1 Python/3.7.7
Date: Wed, 20 May 2020 16:28:36 GMT

$ curl -k https://localhost:8443/workflows
[]
 
```

