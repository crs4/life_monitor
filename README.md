[![Build Status](https://travis-ci.org/crs4/life_monitor.svg?branch=master)](https://travis-ci.org/crs4/life_monitor)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/crs4/life_monitor) 
![GitHub](https://img.shields.io/github/license/crs4/life_monitor)


<div align="center" style="text-align: center; margin-top: 50px;">
<img src="/docs/life_monitor_logo.png" alt="LM logo" width="250px" 
     style="margin-top: 50px;" align="center" />
</div>

<br/>
<br/>

*Workflow testing and monitoring service.*

Life Monitor aims to facilitate the execution, monitoring and sharing of tests
for workflows over time, ensuring that deviations from correct operation are
detected and communicated to the workflow authors so that they might be
solved, thus extending the useful life of the workflow.

Life Monitor is being developed as part of the [EOSC-Life project](https://www.eosc-life.eu/).


## Wiki

See the [wiki](https://github.com/crs4/life_monitor/wiki) for a more complete description and additional information.

[https://github.com/crs4/life_monitor/wiki]()

## Getting Started
A ready-to-use LifeMonitor instance can be easily set up using the docker-compose deployment we distribute with this repository. A `Makefile` provides you the basic actions you might need to manage the deployment. 

To start the deployment, go through the following steps:

1. `make start`, to start the main LifeMonitor services;
2. `make start-aux-services`, to start a preconfigured  set of auxiliary services  i.e., a **Seek/WorkflowHub** instance and a **Jenkins** instance) you need to test the current implementation of the system;
3. register the Seek instance on LifeMonitor for more details) with the following command (see [WorkflowRegistrySetup](https://github.com/crs4/life_monitor/blob/first-release-docs/examples/1_WorkflowRegistrySetup.ipynb)):

```bash
docker-compose exec lm /bin/bash -c "flask registry add seek seek ehukdECYQNmXxgJslBqNaJ2J4lPtoX_GADmLNztE8MI DuKar5qYdteOrB-eTN4F5qYSp-YrgvAJbz1yMyoVGrk https://seek:3000 --redirect-uris https://seek:3000"
```
Take note of the output of the command above which provide you the client credentials to setup your OAuth2 client to query the LifeMonitor API as workflow registry (see examples [LINK] ).


> **NOTE.** The hostname of the workflow registry is `seek`. It is properly resolved by the other services of the deployment. But if your client connects to the LifeMonitor API from the outside of the Docker container network, you'll get a connection error. To solve this issue, set a proper entry on your local `/etc/hosts` (or local DNS server, like `bind`) in order to resolve the hostname `seek` to your local IP address. Alternatively, you can customise the docker-compose to directly use the *host* network and use `localhost` as hostname in registration command above.

You should now have a deployment with the following services up and running:

* **LifeMonitor** @ [https://locahost:8443](https://localhost:8443)
* **Seek** @ [https://seek:3000](https://seek:3000)
* **Jenkins** @ [http://localhost:8080](https://localhost:3000)

To check if the services are properly configured go to the LifeMonitor login page [https://localhost:8443/login/](https://localhost:8000/login/) and to log in by clicking "[Login with Seek](https://localhost:8000/oauth2/login/seek)" (you can use one of the preloaded users, e.g.: **user1**, *password*: **workflowhub** [see [notes](https://github.com/crs4/life_monitor/blob/master/tests/config/registries/seek/notes.txt)]). If all goes well, you should be logged in LifeMonitor and see a minimal user profile page.


## Exploring API / User interface

The web service has a built-in Swagger UI (thanks to
[connexion](https://connexion.readthedocs.io/en/latest/)).  
When the docker-compose is running, you can access the UI at `/ui` (e.g., [https://localhost:8443/ui](https://localhost:8443/ui) if you are using the *production* docker-compose deployment or [https://localhost:8000/ui](https://localhost:8000/ui) if your are using the *development* deployment).  
The full OpenAPI specification is always in the source code repository under [specs/api.yaml](https://github.com/crs4/life_monitor/blob/master/specs/api.yaml) and a "beautified" html version is
available [here](https://crs4.github.io/life_monitor/lm-openapi-rapidoc.html).


## Deploy **LifeMonitor** with `docker-compose`
Basic management actions are implemented as `Makefile` *rules* and can be listed by `make help`:

```bash
$> make help
start                 Start LifeMonitor in a Production environment
start-dev             Start LifeMonitor in a Development environment
start-testing         Start LifeMonitor in a Testing environment
start-nginx           Start a nginx front-end proxy 
                      for the LifeMonitor back-end
start-aux-services    Start auxiliary services (i.e., Jenkins, Seek) useful for development and testing
run-tests             Run all tests in the Testing Environment
tests                 CI utility to setup, run tests and teardown a testing environment
stop-aux-services     Stop all auxiliary services (i.e., Jenkins, Seek)
stop-nginx            Stop the nginx front-end proxy for the LifeMonitor back-end
stop-testing          Teardown all the services in the Testing Environment
stop-dev              Teardown all services in the Develop Environment
stop                  Teardown all the services in the Production Environment
stop-all              Teardown all the services
```

#### Environments

| Environment | Services |
|---------|---------|
| **production** | LifeMonitor BackEnd, NGINX proxy, PostgreSQL DBMS |
| **development** | LifeMonitor BackEnd in dev mode, PostgreSQL DBMS
| **testing** | LifeMonitor Backend in testing mode, preconfigured auxiliary services (i.e., Seek, Jenkins) |

##### Development environment
The development mode mount the life monitor directory within the container and
runs flask in development mode.  Thus, local changes to the code are immediately
picked up.

##### Services
| service | port |
|---------|---------|
| LifeMonitor (prod), exposed via NGINX proxy| 8443|
| LifeMonitor (dev)                          | 8000|
| Seek                                       | 3000|
| Jenkins                                    | 8080|


#### Docker build
As first setup of every environment initialisation, all the required Docker images will be build. The main image containing the LifeMonitor backend is built from `docker/lifemonitor.Dockerfile`. 

Note that `docker/lifemonitor.Dockerfile` depends on the presence of a `certs` directory at the top level (i.e., the repository root) containing the SSL certificates. You can provide your own certificates by renaming them to `lm.key` and `lm.crt`. Any other (self signed) certificate you might want to install on the LifeMonitor container should be placed inside the same `certs` directory. If this directory is not found, the Makefile will create it and populate it with self-signed certificates 
> **WARNING**. If you have an empty `certs` directory the image will build but it will be broken due to missing certificates. Thus, be sure to have a `certs` folder populated with the `lm.key` and `lm.crt` files or use `make clean` to clean up and remove the existing `certs` directory.

#### Auxiliary Services
LifeMonitor acts as a bridge between different systems. To simplify the setup of a complete environment, we provide preconfigured instances of the two systems which LifeMonitor is allowed to communicate with, i.e., the workflow registry *Seek* and the testing platform *Jenkins*.

Their setup is mainly intended for testing but can be easily attached to the *production* and *development* environment mainly for local testing and development. The command `make start-aux-services` allows to start 

To use them on your local environment without any further modification, you have to populate your `/etc/hosts` (or your local DNS server) in such a way that it resolve the hostname `seek` to your local or loopback IP address.


### Settings <a name="settings"></a>
Go through the `settings.conf` to customise the defaults of your LifeMonitor instance. As with any Flask application, you might want to enable/disable the `DEBUG` mode or enable the development Flask mode.

The main important settings are related with the database connection: you have to edit the `POSTGRESQL_*` properties accordingly to the configuration of your Postgres database.

#### Github login (optional)
The current implementation already support user login through **Github**, but it will be actively used in further versions of the system. Anyway, it can be configured by the editing the two properties `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` that you obtain as result of the registration of your LifeMonitor instance on Github. Go through *Settings/Developer settings/OAuth App* and click on *New OAuth App* to start the registration. The main relevant properties you need to provide are: 
* **Homepage URL**: the `BASE_URL` of your LifeMonitor instance (e.g., `https://localhost:8443` or `https://localhost:8000`)
* the **Authorization callback URL**: the URL of the LifeMonitor callback to handle the authorisation flow from Github. It must be set to `<BASE_URL>/oauth2/authorized/github`.




## How to install on your local environment
LifeMonitor is a plain Flask app and all its internal dependencies are freezed and collected on the `requirements.txt` file. Thus, you can easily install LifeMonitor by typing:

```bash 
pip3 install -r requirements.txt
```

The only external requirement is **PostgreSQL** (backend/client). You have to install it on your own to be able to successfully install the `psycopg2==2.8.5` Python requirement.


-----------------------------------------------

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



## Connecting with WorkflowHub

You can run an instance of the WorkflowHub and LifeMonitor on the same host,
each in their own docker-compose.  See the `docker-compose-template.yml` file to
set the name of the docker network the WHub docker-compose created, then the LM
containers will be created attached to that same network and the services will
see each other.  You will also neet to set `WORKFLOW_REGISTRY_URL` appropriately
in `settings.conf`.


## Setting up WorkflowHub and LifeMonitor with OAuth2 login

Bring up WorkflowHub and LifeMonitor with OAuth2 enabled on a single physical
host. Note that this is an example walkthrough for documentation purposes. For
a production deployment you might want to change something, e.g., avoid using
self-signed certificates.

### Bringing up WorkflowHub with HTTPS configuration

In this example we're going to use the same self-signed certificates generated
by our Makefile, which we're going to mount on `/nginx/certs` on the
WorkflowHub Docker container.

Apply the following modifications to the WorkflowHub `nginx.conf` file:


```diff
@@ -63,7 +63,10 @@ http {
         # gzip_http_version 1.1;
 
         server {
-               listen 3000;
+               listen 3000 ssl default_server;
+               ssl_certificate /nginx/certs/lm.crt;
+               ssl_certificate_key /nginx/certs/lm.key;
                root /seek/public;
                client_max_body_size 2G;
                location / {
@@ -72,6 +75,7 @@ http {
                     proxy_set_header   X-Real-IP $remote_addr;
                     proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
                     proxy_set_header   X-Forwarded-Host $server_name;
+                    proxy_set_header   X-Forwarded-Proto $scheme;
                }
                 location ^~ /(assets)/  {
                                gzip_static on;
```

You can change `docker/nginx.conf` on the WorkflowHub git repo (currently on
the "workflow" branch of https://github.com/seek4science/seek) and rebuild the
image locally, or overwrite the `/etc/nginx` dir on the WorkflowHub container
with a bind mount. For instance, suppose you have copied the contents of
`/etc/nginx` from the WorkflowHub container to `/tmp/etc_nginx`. Also suppose
our certificates are on `/tmp/certs`. Finally, we're going to map `lm.org` (the
hostname in the self-signed certificates) to the physical host's (internal) IP
address (you can get it with `ifconfig` on Linux): suppose this is
`192.168.1.167`. We're going to run WorkflowHub on a single Docker container,
and put it on a network called `seek_default`.

```
docker network create seek_default
docker run -d --network seek_default -p 3000:3000 \
  -v /tmp/etc_nginx:/etc/nginx:ro -v /tmp/certs:/nginx/certs:ro \
  --add-host lm.org:192.168.1.167 --name wfhub fairdom/seek:workflow
```

Also add a `192.168.1.167 lm.org` entry to the physical host's `/etc/hosts`.

### Register on WorkflowHub

Since WorkflowHub is starting for the first time, we need to register a first
admin user. Go to https://lm.org:3000 and fill out the forms.

### Registering LifeMonitor as a client application on WorkflowHub

On the WorkflowHub web interface, click on the user name on the top right,
then go to "My Profile"; on the profile page, click "Actions" on the right,
then choose "API Applications"; now click on "New Application" on the right
and fill out the form. Choose a name, set Redirect URI to
https://lm.org:8443/oauth2/auth/seek, activate Confidential and Scopes >
Read, then submit the form.

This can be done for any user (e.g., a service user could have been created on
the WorkflowHub just for this), all that matters to LifeMonitor is the OAuth
params provided after registration. Specifically, copy the following to
`settings.conf` in the LifeMonitor repo: "Application UID" to `SEEK_CLIENT_ID`
and "Secret" to `SEEK_CLIENT_SECRET`. Set the other WorkflowHub params to:

```
SEEK_API_BASE_URL="https://lm.org:3000"
SEEK_AUTHORIZE_URL="https://lm.org:3000/oauth/authorize"
SEEK_ACCESS_TOKEN_URL="https://lm.org:3000/oauth/token"
```

### Configure LifeMonitor's docker-compose file and start the service

In the LifeMonitor `docker-compose-template.yml`, in the `lm` service section,
map the lm.org host to the above IP:

```yaml
  lm:
    [...]
    extra_hosts:
      - "lm.org:192.168.1.167"
```

Set the network name to `seek_default`:

```yaml
networks:
  life_monitor:
    name: seek_default
    external: true
```

Start the service with `make startdev`.


### Authorizing LifeMonitor as a client application and logging in

Now go back to the WorkflowHub web UI and click on "Authorize" on the right of
the callback url for LifeMonitor. Confirm authorization on the next page. You
should get an OAuth error. This is currently a [known
bug](https://github.com/crs4/life_monitor/issues/30), so ignore it. Go to
https://lm.org:8443, click on "Log in" and choose to log in with Seek. You
should be redirected to a WorkflowHub page that asks you to authorize
LifeMonitor to use your account. Click on "Authorize" and you should land on a
LifeMonitor page that confirms you are logged in and displays your login
details.

### Additional notes on WorkflowHub configuration

In order to get correct URLs from the WorkflowHub API, you need to set the base URL. Go to Server admin > Settings and set "Site base URL" to https://lm.org:3000.

To enable workflows, go to Server admin > Enable/disable features and click on "Workflows enabled". You can set "CWL Viewer URL" to `https://view.commonwl.org/`.

### WorkflowHub API calls with requests when using self-signed certificates

If you are using [requests](https://requests.readthedocs.io/en/master/), note
that to interact with the WorkflowHub configured with a self-signed
certificate you need to add `verify=False` to the calls. See
[this](https://stackoverflow.com/questions/30405867/how-to-get-python-requests-to-trust-a-self-signed-ssl-certificate)
for instance.
