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

Note that `docker/lifemonitor.Dockerfile` depends on the presence of a `certs` directory at the top level (i.e., the repository root) containing the SSL certificates. If this directory is not found, the Makefile will create it and populate it with self-signed certificates (note that if you have an empty `certs` directory the image will build but it will be broken due to missing certificates).

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


## Authenticating

LifeMonitor supports OAuth2 for authentication and authorization and currently
supports using identities from WorkflowHub and GitHub (for both of these to work
on a new deployment, the application must be appropriately configured and
registered with the respective identity provider).

For testing and development, LifeMonitor provides a simple web-based
authentication interface:

  * https://localhost:8443/register --> register a new user on your instance
  * https://localhost:8443/login


To authenticate API access, you're best off creating an API key using the
provided CLI:

    flask api-key create <username>

The API key will be printed on the console.  See the
[CLI](#Command-line-interface) section for pointers on how to call it.


### Registering LifeMonitor as a client application on WorkflowHub

On the WorkflowHub web interface, click on the user name on the top right,
then go to "My Profile"; on the profile page, click "Actions" on the right,
then choose "API Applications"; now click on "New Application" on the right
and fill out the form. Choose a name, set Redirect URI to
https://localhost:8443/oauth2/auth/seek, activate Confidential and Scopes >
Read.

This can be done for any user (e.g., create a service user on the
WorkflowHub), all that matters to LifeMonitor is the OAuth params (Client ID,
Client Secret, etc.) provided after registration.


## Command line interface

To access the command line interface, you need to execute `flask ...` from the
base LifeMonitor repository directory.  Rather than installing the dependencies
on your system, you might prefer to use the pre-built docker images, either by:

a. starting a new container:

     docker run --rm -it crs4/lifemonitor flask --help

b. if the docker compose is up, you can run commands inside that container:

    docker-compose exec lm flask --help

As you can see from the help message, the CLI provides various commands.  The
most relevant ones for non-developers might be the following.

| command       |               |
|---------------|---------------|
| flask api-key | api-key management |
| flask db init | init the schema in a new database |


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

