# Life Monitor

Workflow testing service


## Developing

Basic actions are implemented as Makefile rules.


| Building docker images | make |
| Launch the docker-compose | make start |
| Stop the docker-compose | make stop |


## Connecting to the docker-compose

By default, the `lm` service listens on port 8080:

    $ curl http://localhost:8080/workflows
    []


## Exploring API / User interface

The web service has a built-in Swagger UI (thanks to
[connexion](https://connexion.readthedocs.io/en/latest/)).  When the
docker-compose is running, you can access the UI at `/ui`.

