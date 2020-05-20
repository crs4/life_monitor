# Life Monitor

Workflow testing service


## Developing

Basic actions are implemented as Makefile rules.

| Purpose | command |
|---------|---------|
| Building docker images | make |
| Launch the docker-compose | make start |
| Stop the docker-compose | make stop |
| Launch docker-compose in development mode | make startdev |
| Stop docker-compose in development mode | make stopdev |

The development mode mount the life monitor directory within the container and runs flask in development mode.  Thus, local changes to the code are immediately picked up.


## Connecting to the docker-compose

By default, the `lm` service listens on port 8080:

    $ curl http://localhost:8080/workflows
    []


## Exploring API / User interface

The web service has a built-in Swagger UI (thanks to
[connexion](https://connexion.readthedocs.io/en/latest/)).  When the
docker-compose is running, you can access the UI at `/ui`.


## Simple example with cURL


```
$ curl -H 'Content-Type: application/json' -d '{ "name": "test1" }' http://localhost:8080/workflows
"7338d1b9-215f-4b68-be50-d3b94a345343"

$ curl -H 'Content-Type: application/json' -d '{ "name": "test2" }' http://localhost:8080/workflows
"e0274c6b-47bc-4d7f-87c6-7a7a7a9b846d"

$ curl http://localhost:8080/workflows
[
  {
    "name": "test1",
    "workflow_id": "7338d1b9-215f-4b68-be50-d3b94a345343"
  },
  {
    "name": "test2",
    "workflow_id": "e0274c6b-47bc-4d7f-87c6-7a7a7a9b846d"
  }
]

$ curl http://localhost:8080/workflows/e0274c6b-47bc-4d7f-87c6-7a7a7a9b846d
{
  "name": "test2",
  "workflow_id": "e0274c6b-47bc-4d7f-87c6-7a7a7a9b846d"
}

$ curl -X DELETE http://localhost:8080/workflows/e0274c6b-47bc-4d7f-87c6-7a7a7a9b846d

$ curl -i http://localhost:8080/workflows/e0274c6b-47bc-4d7f-87c6-7a7a7a9b846d
HTTP/1.0 404 NOT FOUND
Content-Type: application/json
Content-Length: 0
Server: Werkzeug/1.0.1 Python/3.7.7
Date: Wed, 20 May 2020 16:28:36 GMT

$ curl -X DELETE http://localhost:8080/workflows/7338d1b9-215f-4b68-be50-d3b94a345343
HTTP/1.0 204 NO CONTENT
Content-Type: application/json
Server: Werkzeug/1.0.1 Python/3.7.7
Date: Wed, 20 May 2020 16:30:52 GMT

$ curl -i http://localhost:8080/workflows
HTTP/1.0 200 OK
Content-Type: application/json
Content-Length: 3
Server: Werkzeug/1.0.1 Python/3.7.7
Date: Wed, 20 May 2020 16:31:50 GMT

[]

```
