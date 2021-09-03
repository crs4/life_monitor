# LifeMonitor Administration

This guide explains how to deploy and administer your own instance of
LifeMonitor.

The [GitHub repository](https://github.com/crs4/life_monitor) contains a
[Makefile](https://www.gnu.org/software/make/) that serves as an entry point
to the basic actions necessary to manage the [Docker
Compose](https://docs.docker.com/compose/) deployment.


## Default setup

This setup will instantiate:

* an instance of LifeMonitor;
* an instance of [Seek/WorkflowHub](https://about.workflowhub.eu/) which, among
  other things, you will use as an **identity provider**;
* an instance of [Jenkins](https://www.jenkins.io/).

**Assumptions**:

* you'll be running and accessing the setup on **localhost**;
* you will use the integrated WorkflowHub instance as the identity provider;
* **the WorkflowHub instance will be accessible with the host name "`seek`"**. You
  can do this by creating an entry in `/etc/hosts` or using a local DNS server,
  like `bind`

To start the deployment, go through the following steps:

0. `docker network create life_monitor`, to create the Docker network;
1. `make start`, to start the main LifeMonitor services;
2. `make start-aux-services`, to start the preconfigured instances of WorkflowHub and Jenkins;
    these auxiliary services are needed to run the LifeMonitor tests and to check your local deployment as explained below;
3. register the WorkflowHub instance with LifeMonitor with the following command (see
   the [WorkflowRegistrySetup](https://github.com/crs4/life_monitor/tree/master/examples/1_WorkflowRegistrySetup.ipynb) example
   for more details):

```
docker-compose exec lm /bin/bash -c "flask registry add seek seek ehukdECYQNmXxgJslBqNaJ2J4lPtoX_GADmLNztE8MI DuKar5qYdteOrB-eTN4F5qYSp-YrgvAJbz1yMyoVGrk https://seek:3000 --redirect-uris https://seek:3000"
```

Take note of the output of the command above. It will provide you with the
client credentials to setup your OAuth2 client to query the LifeMonitor API as a
workflow registry (see the [WorkflowRegistryAuthorize](https://github.com/crs4/life_monitor/tree/master/examples/2_WorkflowRegistryAuthorize.ipynb) example).

You should now have a deployment with the following services up and running:

* **LifeMonitor** @ [https://localhost:8443](https://localhost:8443)
* **WorkflowHub** @ [https://seek:3000](https://seek:3000)
* **Jenkins** @ [http://localhost:8080](http://localhost:8080)

To verify that the services are properly configured, point your browser to
[LifeMonitor](https://localhost:8443), click on `Log in` and then on `Sign in
using Seek`. You will be redirected to the WorkflowHub login page, which will
ask for a username and a password. You can use one of the [preloaded
users](https://github.com/crs4/life_monitor/tree/master/tests/config/registries/seek/notes.txt), e.g.:

 * Username: `user1`
 * Password: `workflowhub`

If all goes well, you should be redirected back to LifeMonitor, which will ask
you to _register_ your identity, i.e., associate the WorkflowHub identity with a
LifeMonitor identity. Type in a user name of your choice and click on
`Register`. You should be redirected to the user profile page. Here you can
generate an API key that can be used to interact with the [LifeMonitor
API](lm_api_specs): in the "API keys"
tab, click on `NEW` and copy the generated key. Then head over to the [API
explorer](https://localhost:8443/openapi.html), paste the copied string into
the API Key field in the authentication section and click on `SET`.

### Exploring the API

LifeMonitor exposes its functionalities through a [RESTful API](lm_api_specs).
If you followed the [default setup](#default-setup) instructions above, you
should now be able to interact with your local LifeMonitor instance via the
[API explorer](https://localhost:8443/openapi.html).

Select "List registries" and click on `TRY`. You should get a JSON response
listing all workflow registries known to LifeMonitor. In this case, the only
item should be a representation of your local WorkflowHub instance:

```json
{
  "items": [
    {
      "name": "seek",
      "type": "seek",
      "uri": "https://seek:3000",
      "uuid": "c07182a6-e2e6-4e0e-b3ed-c593aa900a3f"
    }
  ],
  "meta": {
    "api_version": "0.2.0-beta2",
    "base_url": "https://172.18.0.4:8000",
    "resource": "/registries"
  }
}
```

Copy the value of the "uuid" field, then select "List registry workflows" and
paste the copied UUID into the `registry_uuid` field. Click on `TRY`: you
should get an empty item list in the response. This is normal, since no
workflow has been submitted to LifeMonitor yet.

Now go to "Submit registry workflow". Again, use the copied UUID to populate
the `registry_uuid` field, then click on `EXAMPLE` in the "REQUEST BODY"
section right below. To fill in the request body, we need the workflow's WorkflowHub
ID and version (while "name" can be a name of your choice). Go to the
[workflows page](https://seek:3000/workflows) on your local WorkflowHub instance and
click on the "sort-and-change-case" workflow. This will open the workflow's
page, which lists the WorkflowHub ID and version as "SEEK ID". For instance:

```
https://seek:3000/workflows/21?version=1
```

Now we can fill in the request body in the LifeMonitor API explorer:

```json
{
  "identifier": "21",
  "name": "Sort and change case",
  "version": "1"
}
```

After running the example, you should get a response like the following:

```json
{
  "wf_uuid": "478b43f0-8650-0139-d67a-0242ac1b0005",
  "wf_version": "1"
}
```

This can in turn be used to try other API calls. For instance, go to "Get
workflow test status" and use the above UUID and version values to populate
the corresponding fields under "PATH PARAMETERS". Click on `TRY` and you
should get a response containing information on the workflow's testing
status. Also, if you repeat the above call to "List registry workflows", the
response should now include the newly submitted workflow.

Until now, you've interacted with the LifeMonitor API as a user / generic
client. The other main way to use the API is to access it as a _registry
client_. To do this from the API explorer, you need to change the
authentication method. In the Authentication section, at the top, click on
`CLEAR ALL API KEYS`. Now move to the "OAuth (RegistryClientCredentials)"
section, enable all scopes under "CLIENT CREDENTIALS FLOW" and fill in the
fields required to get an OAuth2 token. You can get the client id and secret
by running:

```
docker-compose exec lm /bin/bash -c "flask registry show seek"
```

Select "Request Body" in the drop-down menu, then click on `GET TOKEN`. You
should see an "Access Token Received" message appear under the text fields.
Now you can try operations reserved to registry clients, which are listed
under "Registry Client Operations" in the explorer (e.g., "Get the current
registry client").

The [examples](https://github.com/crs4/life_monitor/tree/master/examples)
folder contains several examples that show how to interact with the API in
Python.

An alternative rendering of the API is the Swagger UI provided by
[Connexion](https://connexion.readthedocs.io/en/latest/), which should be
accessible at [https://localhost:8443/ui](https://localhost:8443/ui).


## Deploy **LifeMonitor** with `docker-compose`

Basic management actions are implemented as [Makefile
rules](https://www.gnu.org/software/make/manual/html_node/Rule-Introduction.html#Rule-Introduction)
and can be listed by running `make help`:

```
$> make help
start                 Start LifeMonitor in a Production environment
start-dev             Start LifeMonitor in a Development environment
start-testing         Start LifeMonitor in a Testing environment
start-nginx           Start a nginx front-end proxy for the LifeMonitor back-end
start-aux-services    Start auxiliary services (i.e., Jenkins, Seek) useful for development and testing
run-tests             Run all tests in the Testing Environment
tests                 CI utility to setup, run tests and teardown a testing environment
stop-aux-services     Stop all auxiliary services (i.e., Jenkins, Seek)
stop-nginx            Stop the nginx front-end proxy for the LifeMonitor back-end
stop-testing          Stop all the services in the Testing Environment
stop-dev              Stop all services in the Develop Environment
stop                  Stop all the services in the Production Environment
stop-all              Stop all the services
down                  Teardown all the services
clean                 Clean up the working environment (i.e., running services, network, volumes, certs and temp files)
help                  Show help
```

### A note about volumes

Docker Compose uses Docker volumes for data storage. These will persist
between start and stop actions. Database schema will be automacally updated 
to the proper version as part of the system initialisation.

If you prefer to start with a clean database, use the regular Docker commands to delete
them. For instance:

```
docker volume rm life_monitor_lifemonitor_db
```

### Environments

| Environment     | Services                                                                                            |
| --------------- | --------------------------------------------------------------------------------------------------- |
| **production**  | LifeMonitor back-end, NGINX proxy, PostgreSQL DBMS                                                  |
| **development** | LifeMonitor back-end in dev mode, PostgreSQL DBMS                                                   |
| **testing**     | LifeMonitor back-end in testing mode, preconfigured auxiliary services (i.e., WorkflowHub, Jenkins) |

The development mode mounts the LifeMonitor directory within the container and
runs Flask in development mode.  Thus, local changes to the code are immediately
picked up.

### Services

| service                                     | port |
| ------------------------------------------- | ---- |
| LifeMonitor (prod), exposed via NGINX proxy | 8443 |
| LifeMonitor (dev)                           | 8000 |
| WorkflowHub                                 | 3000 |
| Jenkins                                     | 8080 |

### Docker build

The first step for setting up the environment is to build all required Docker
images. The main image containing the LifeMonitor back-end is built
from `docker/lifemonitor.Dockerfile`.

Note that `docker/lifemonitor.Dockerfile` depends on the presence of a `certs`
directory at the top level (i.e., the repository root) containing the SSL
certificates. You can provide your own certificates by renaming them to `lm.key`
and `lm.crt`. Any other (self-signed) certificate you might want to install on
the LifeMonitor container should be placed inside the same `certs` directory. If
this directory is not found, the Makefile will create it and populate it with
self-signed certificates.
> **WARNING**. If you have an empty `certs` directory the image will build but
> it will be broken due to missing certificates. Thus, be sure to have a `certs`
> folder populated with the `lm.key` and `lm.crt` files or use `make clean` to
> clean up and remove the existing `certs` directory.

### Auxiliary Services

LifeMonitor acts as a bridge between different systems. To simplify the setup of
a complete environment, we provide preconfigured instances of the two systems
which LifeMonitor is allowed to communicate with, i.e., the workflow registry
*WorkflowHub* and the testing platform *Jenkins*.

Their setup is mainly intended for testing but can be easily attached to the
*production* and *development* environment mainly for local testing and
development. You can use the `make start-aux-services` command to start them.

To use them on your local environment without any further modification, you have
to populate your `/etc/hosts` (or your local DNS server) in such a way that it
resolves the hostname `seek` to your local or loopback IP address.

### Settings

Go through `settings.conf` to customise the defaults of your LifeMonitor
instance. As with any [Flask](https://flask.palletsprojects.com/) application,
you might want to enable/disable the `DEBUG` mode or enable the `development`
Flask mode.

The most important settings are those related to the database connection: edit
the `POSTGRESQL_*` properties according to the configuration of your
PostgreSQL database.

### Using a server name other than `localhost`

To access the services in the docker-compose from another system, you'll have
to use a server name other than `localhost` (or an IP address). In this case,
set the `EXTERNAL_SERVER_URL` variable in `settings.conf` accordingly.
Additionally, You **must edit the API applications authorized by WorkflowHub**:

* Log into WorkflowHub as [`admin`](https://github.com/crs4/life_monitor/tree/master/tests/config/registries/seek/notes.txt);
* Click on the user menu on the top right; select *My profile*;
* Click on the *Actions* menu on the top right; select *API Applications*;
* Edit the `LifeMonitor` application by clicking on the *Edit* button on the
  left side of its row in the table;
* Add the correct URI to the **Redirect URI** box.  E.g.,

    https://122.33.4.72:8443/oauth2/authorized/seek


### Github login (optional)

Login via GitHub can be configured by editing the `GITHUB_CLIENT_ID` and
`GITHUB_CLIENT_SECRET` properties in `settings.conf`. To get these
credentials, you have to register your LifeMonitor instance on GitHub. On
GitHub, click on your profile picture on the top right, select "Settings" /
"Developer settings" / "OAuth Apps", then click on *Register a new
application*. The most relevant properties you need to provide are:

* **Homepage URL**: the `BASE_URL` of your LifeMonitor instance (e.g.,
  `https://lifemonitor.example.com`)
* the **Authorization callback URL**: the URL of the LifeMonitor callback to
  handle the authorization flow from Github. It must be set to
`<BASE_URL>/oauth2/authorized/github`.


## How to install on your local environment

LifeMonitor is a plain Flask app and all its internal dependencies are frozen
and collected on the `requirements.txt` file. Thus, you can easily install
LifeMonitor by typing:

```
pip install -r requirements.txt
```

The only non-Python dependency is **PostgreSQL** (back-end/client), which is
required by the `psycopg2` Python package.



## Upgrades


Existing Dockerized deployments can be easily upgraded to a more recent LifeMonitor version by going through the following steps:

1. stop `lm` service with the `docker-compose stop lm` command;
2. make a backup of LifeMonitor data to your local machine:

    ```bash
    # 2a) backup to a temp destination
    docker-compose exec db /bin/bash -c "PGPASSWORD=\${POSTGRESQL_PASSWORD} pg_dump -U \${POSTGRESQL_USERNAME} \${POSTGRESQL_DATABASE} > /tmp/lifemonitor_backup.sql"
    
    # 2b) copy backup to your machine
    docker cp life_monitor_db_1:/tmp/lifemonitor_backup.sql ${HOME}/lifemonitor_backup.sql
    ```
3. teardown all the services with the `make down` comamnd;
4. update your local copy of LifeMonitor sources (via `git clone` or `git pull`);
5. restart all the services with the `make start` (or `make start-dev` to start services in `dev` mode) command.


As a result, the up-to-date LifeMonitor instance should be started and the existing data migrated to the proper database schema. You can check the actual running database schema by typing:

```bash
docker-compose exec lm /bin/bash -c "flask db current"
```

> An output with `(head)` at the end, e.g., `bbe1397dc8a9 (head)`, indicates that your LifeMonitor instance is running with the most recent database schema.


To upgrade a LifeMonitor instance deployed without Docker (see section on ["How to install on your local environment"](#how-to-install-on-your-local-environment)), you have to:
1. stop LifeMonitor Flask app;
2. make a backup of the database used by LifeMonitor;
3. update your local copy of LifeMonitor sources (via `git clone` or `git pull`);
4. apply all the required migrations, by typing `flask db upgrade`;
5. restart the LifeMonitor Flask app.


## Authenticating

LifeMonitor supports OAuth2 for authentication and authorization and currently
supports using identities from WorkflowHub and GitHub.

>For these to work on a new deployment, the application must be appropriately
configured and registered with the respective identity provider. See the
[section on GitHub login configuration](#github-login-optional) and the
[WorkflowRegistrySetup](https://github.com/crs4/life_monitor/tree/master/examples/1_WorkflowRegistrySetup.ipynb)
example.

For testing and development, LifeMonitor provides a simple web-based
authentication interface:

  * [https://localhost:8443/register](https://localhost:8443/register): register a new user
  * [https://localhost:8443/login](https://localhost:8443/login): log in

### API access

LifeMonitor supports **API keys** and **OAuth2** for API authentication.

#### API keys

API keys should be
used only for development and testing. They can be created from the web UI
as explained above, or via CLI:

```
docker-compose exec lm /bin/bash -c 'flask api-key create <username>'
```

The API key will be printed as part of the command's output.

To query the LifeMonitor API with your API key, you have to add it to the request header. For instance, with `curl`:

```
curl --insecure -X GET \
  'https://localhost:8443/users/current' \
  -H 'ApiKey: <api key>'
```

>**NOTE: API calls when using self-signed certificates.** \
> If you are using `curl`, you need to add the `--insecure` flag to disable certificate validation (see the above example). If you are using [requests](https://requests.readthedocs.io/en/master/), you need to add `verify=False` to the calls. See
[this](https://stackoverflow.com/questions/30405867/how-to-get-python-requests-to-trust-a-self-signed-ssl-certificate)
for instance.

#### OAuth2

The OAuth2 protocol can be used with [_generic_ clients or _registry_
clients](lm_api_specs). Follow the [authenticating clients
guide](authenticate-your-client) to set up a generic client and the
[WorkflowRegistrySetup](https://github.com/crs4/life_monitor/tree/master/examples/1_WorkflowRegistrySetup.ipynb)
example to set up a registry client.

Workflow registries are allowed to use both the **Authorization Code** and
**Client Credentials** grant type to exchange authorization tokens. The OAuth2
token needs to be included in the `Authorization` header as a Bearer
Token. The
[WorkflowRegistryAuthorize](https://github.com/crs4/life_monitor/tree/master/examples/2_WorkflowRegistryAuthorize.ipynb)
example shows how to get a bearer token using the client id and secret you got
when registering the WorkflowHub instance with LifeMonitor.

```
curl --insecure -X GET \
  'https://localhost:8443/registries/current' \
  -H 'Authorization: Bearer <token>'
```


## Command line interface

LifeMonitor includes a command line interface (CLI), mainly intended for
administrative tasks. To display a general help, run:

    docker-compose exec lm flask --help

The above will list all available commands. To get help for a specific
command, run it with the `--help` flag. For instance:

    docker-compose exec lm flask registry --help


## Setup your own WorkflowHub instance

If you already have a WorkflowHub (Seek) instance you can easily register it
on LifeMonitor by following the procedure described
[here](https://github.com/crs4/life_monitor/tree/master/examples/1_WorkflowRegistrySetup.ipynb). Make sure the following
requirements are met.

### enabling HTTPS

HTTPS must be enabled on your WorkflowHub instance (See [these
notes](https://github.com/crs4/life_monitor/blob/master/docs/wfhub-setup-notes.md)) and its certificates should be valid on the
LifeMonitor instance you have to connect. You could use a certificate issued by
a known certificate authority (e.g., Let's Encrypt) or use the autogenerated
LifeMonitor certificate. The latter is automatically generated when you
start a deployment, but can also be regenerated by deleting the existing
`certs` folder and typing `make certs`. It is a multi-domain certificate and
you can customise the list of certificate domain names by editing the
`utils/gen-certs.sh` script.

### Reachability

LifeMonitor needs to directly connect to the registry for different
purposes. Therefore, the registry should be bound to a hostname resolvable and
reachable by LifeMonitor. For this reason, if you are using the docker-compose
deployment you should avoid `localhost` as hostname for the registry, unless you
reconfigure the deployment to use the `host` Docker network mode.

### Additional notes on WorkflowHub configuration

* In order to get correct URLs from the WorkflowHub API, you need to set the base URL. Go to Server admin > Settings and set "Site base URL" to `https://<BASE_URL>:3000` (e.g., `https://seek:3000` is the configuration of this field on the [WorkflowHub](#auxiliary-services) instance in the pre-configured LifeMonitor deployment).

* To enable workflows, go to Server admin > Enable/disable features and click on "Workflows enabled". You can set "CWL Viewer URL" to `https://view.commonwl.org/`.


## Starting a local development instance

We can accept code and documentation contributions as Pull Requests.  If you'd
like to contribute code, please try to make sure you also contribute tests (or
extend the existing tests) that exercise the new code, verify its correct
operation and that the changes did not break other parts of the code.

To contribute, you'll need to have a local development instance on which to
work and test.

Get yourself a local copy of the code.
```
git clone git@github.com:crs4/life_monitor.git
cd life_monitor
```

Edit `settings.conf`: uncomment the line
```
SERVER_NAME=localhost:8000
```

Start the service in development mode
```
make start-dev
```

You'll be able to access the service at `https://localhost:8000/`.  The service
will be running in development mode, so changes to the source code will be
immediately reflected in the running service.


### Running tests

Stop the running development instance
```
make stop-dev
```

Now run the tests:
```
make run-tests
```
You should see the Pytest output on the console.

Once your tests pass, feel free to push your changes to your fork and open a
Pull Request.
