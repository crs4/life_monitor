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


## Getting Started
You can easily set up your own ready-to-use LifeMonitor instance using the
docker-compose deployment we distribute with this repository. A `Makefile`
provides you with the basic actions necessary to manage the deployment. 

To start the deployment, go through the following steps:

0. `docker network create life_monitor` to create the Docker network;
1. `make start`, to start the main LifeMonitor services;
2. `make start-aux-services`, to start a preconfigured set of auxiliary services
   that are needed to test the LifeMonitor -- i.e., an instance of
   [**Seek/WorkflowHub**](https://workflowhub.eu/) and an instance of
   [**Jenkins**](https://www.jenkins.io/);
3. register the Seek instance on LifeMonitor with the following command (see
   [WorkflowRegistrySetup](examples/1_WorkflowRegistrySetup.ipynb)
   for more details):

```bash
docker-compose exec lm /bin/bash -c "flask registry add seek seek ehukdECYQNmXxgJslBqNaJ2J4lPtoX_GADmLNztE8MI DuKar5qYdteOrB-eTN4F5qYSp-YrgvAJbz1yMyoVGrk https://seek:3000 --redirect-uris https://seek:3000"
```
Take note of the output of the command above. It will provide you with the
client credentials to setup your OAuth2 client to query the LifeMonitor API as a
workflow registry (see the [examples](examples)).


**NOTE.** If you're authenticating with the instance of Seek/WorkflowHub running
in the docker-compose (as we suggested in the instructions above), you need to
make sure the client from which you're connecting can resolve its host name.
The host name of the workflow registry is `seek` and it is properly resolved by
the other services within the docker-compose. But **if your client connects to
the LifeMonitor API from the outside of the Docker container network**, set a
proper entry on your local `/etc/hosts` (or local DNS server, like `bind`) in
order to resolve the host name `seek` to your local IP address. Alternatively,
you can customise the docker-compose to directly use the *host* network and use
`localhost` as hostname in the registration command above.

You should now have a deployment with the following services up and running:

* **LifeMonitor** @ https://localhost:8443
* **Seek** @ https://seek:3000
* **Jenkins** @ http://localhost:8080

To verify that the services are properly configured, go to the LifeMonitor login
page at https://localhost:8443/login/ and log in
by clicking "[Login with Seek](https://localhost:8443/oauth2/login/seek)" (you
can use one of the preloaded users, e.g.: **user1**, *password*: **workflowhub**
 -- see these
[notes](tests/config/registries/seek/notes.txt)).
If all goes well, you should be logged into LifeMonitor and see a minimal user
profile page.


## Exploring the API

The full OpenAPI specification is always in the source code repository under
[specs/api.yaml](specs/api.yaml)
and a "beautified" html version is available
[here](https://crs4.github.io/life_monitor/lm-openapi-rapidoc.html).

The LifeMonitor web service has a built-in Swagger UI (thanks to
[Connexion](https://connexion.readthedocs.io/en/latest/)). You can access the UI
at `/ui` (e.g., https://localhost:8443/ui if you
are using the *production* docker-compose deployment or
https://localhost:8000/ui if your are using the
*development* deployment).  


Look in the [examples](examples) folder for some examples of Python clients interacting with the
LifeMonitor API.


## Deploy **LifeMonitor** with `docker-compose`

Basic management actions are implemented as `Makefile` *rules* and can be listed by `make help`:

```bash
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
stop-testing          Teardown all the services in the Testing Environment
stop-dev              Teardown all services in the Develop Environment
stop                  Teardown all the services in the Production Environment
stop-all              Teardown all the services
```

#### A note about volumes

The docker-compose uses docker volumes for data storage.  These will persist
between start and stop actions.  Use the regular Docker commands to delete
them. For instance:

```bash
docker volume rm life_monitor_lifemonitor_db
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


#### Docker build <a name="image-build"></a>
As first setup of every environment initialisation, all the required Docker
images will be build. The main image containing the LifeMonitor backend is built
from `docker/lifemonitor.Dockerfile`. 

Note that `docker/lifemonitor.Dockerfile` depends on the presence of a `certs`
directory at the top level (i.e., the repository root) containing the SSL
certificates. You can provide your own certificates by renaming them to `lm.key`
and `lm.crt`. Any other (self signed) certificate you might want to install on
the LifeMonitor container should be placed inside the same `certs` directory. If
this directory is not found, the Makefile will create it and populate it with
self-signed certificates 
> **WARNING**. If you have an empty `certs` directory the image will build but
> it will be broken due to missing certificates. Thus, be sure to have a `certs`
> folder populated with the `lm.key` and `lm.crt` files or use `make clean` to
> clean up and remove the existing `certs` directory.

#### Auxiliary Services <a name="aux-services"></a>
LifeMonitor acts as a bridge between different systems. To simplify the setup of
a complete environment, we provide preconfigured instances of the two systems
which LifeMonitor is allowed to communicate with, i.e., the workflow registry
*Seek* and the testing platform *Jenkins*.

Their setup is mainly intended for testing but can be easily attached to the
*production* and *development* environment mainly for local testing and
development. The command `make start-aux-services` allows to start 

To use them on your local environment without any further modification, you have
to populate your `/etc/hosts` (or your local DNS server) in such a way that it
resolve the hostname `seek` to your local or loopback IP address.


### Settings <a name="settings"></a>
Go through the `settings.conf` to customise the defaults of your LifeMonitor
instance. As with any Flask application, you might want to enable/disable the
`DEBUG` mode or enable the development Flask mode.

The main important settings are related with the database connection: you have
to edit the `POSTGRESQL_*` properties accordingly to the configuration of your
Postgres database.

#### Github login (optional) <a name="github"></a>
The current implementation already support user login through **Github**, but it
will be actively used in further versions of the system. Anyway, it can be
configured by the editing the two properties `GITHUB_CLIENT_ID` and
`GITHUB_CLIENT_SECRET` that you obtain as result of the registration of your
LifeMonitor instance on Github. Go through *Settings/Developer settings/OAuth
App* and click on *New OAuth App* to start the registration. The main relevant
properties you need to provide are: 
* **Homepage URL**: the `BASE_URL` of your LifeMonitor instance (e.g.,
  `https://localhost:8443` or `https://localhost:8000`)
* the **Authorization callback URL**: the URL of the LifeMonitor callback to
  handle the authorisation flow from Github. It must be set to
`<BASE_URL>/oauth2/authorized/github`.




## How to install on your local environment
LifeMonitor is a plain Flask app and all its internal dependencies are frozen
and collected on the `requirements.txt` file. Thus, you can easily install
LifeMonitor by typing:

```bash 
pip3 install -r requirements.txt
```

The only external requirement is **PostgreSQL** (backend/client). You have to
install it on your own to be able to successfully install the `psycopg2==2.8.5`
Python requirement.

<br/>

## Authenticating <a name="authenticating"></a>

LifeMonitor supports OAuth2 for authentication and authorization and currently
supports using identities from WorkflowHub and GitHub. 

>For both of these to work
on a new deployment, the application must be appropriately configured and
registered with the respective identity provider (see [here](#github) for the Github configuration and [WorkflowRegistrySetup](https://github.com/crs4/life_monitor/blob/first-release-docs/examples/1_WorkflowRegistrySetup.ipynb) to configure your instance of WorkflowHub/Seek workflow registry).

For testing and development, LifeMonitor provides a simple web-based
authentication interface:

  * [https://localhost:8443/register]() --> register a new user on your instance
  * [https://localhost:8443/login]()


### Authenticating API <a name="authenticating-api"></a>

LifeMonitor supports **API key** and **OAuth2** for authorizing API access.

#### API key

API keys allows to authenticate users when performing API calls and should be
used only for development and testing. At the moment, API keys can be created
only via CLI (see the [CLI](#cli) section for pointers on how to call it). 

The API key will be printed on the console by typing:

    flask api-key create <username>

Or, if you are using the docker-compose deployment: 

```
docker-compose exec lm /bin/bash -c 'flask api-key create <username>'
```    

To query the LifeMonitor API with your API key, you have to pass it in the request header as follows:

```
curl --insecure -X GET \
  'https://localhost:8443/users/current' \
  -H 'ApiKey: KmIIggU9lTcI70fuzZEMHmAFyPHcg82r0qyCVvoKswr2K4XdN8FnVQ' 
```


>**NOTE: API calls when using self-signed certificates.** \
> If are using `curl`, you need to add the `--insecure` flag to disable the certificate validation (see the above example). If you are using [requests](https://requests.readthedocs.io/en/master/), you need to add `verify=False` to the calls. See
[this](https://stackoverflow.com/questions/30405867/how-to-get-python-requests-to-trust-a-self-signed-ssl-certificate)
for instance.


#### OAuth2
The current implementation allows to use the OAuth2 protocol only with workflow
registries. See
[WorkflowRegistrySetup](https://github.com/crs4/life_monitor/blob/first-release-docs/examples/1_WorkflowRegistrySetup.ipynb)
to set up your registry as OAuth2 LifeMonitor client.

Workflow registries are allowed to use both the **Authorization Code** and
**Client Credentials** grant type to exchange authorization tokens. Once you a
valid OAuth2 token, put it into the `Authorization` header as follows:

```
curl --insecure -X GET \
  'https://localhost:8443/registries/current' \
  -H 'Authorization: Bearer IT6g8H38GqIYcg7bnZuh8V0i1oGMGMjLIj9wMmQNOQ'
```

<br>

## Command line interface <a name="cli"></a>

To access the command line interface, you need to pass the `CMD` to flask -
i.e.,  `flask <CMD>` - from the base LifeMonitor repository directory.

If you are using the `docker-compose` deployment, when it is up, you can run
commands inside the LifeMonitor backend container (named `lm`):

    docker-compose exec lm flask --help

As you can see from the help message, the CLI provides various commands mainly
intended for administrative tasks:

| command        | purpose             |
|----------------|---------------------|
| flask api-key  | api-key management  |
| flask db       | db management       |
| flask registry | registry management |

<br>

## Setup your own WorkflowHub instance <a name="setup-custom-seek-instance"></a>

If you already have a WorkflowHub (Seek) instance you can easily register it on
LifeMonitor by following the procedure describe
[here](https://github.com/crs4/life_monitor/blob/first-release-docs/examples/1_WorkflowRegistrySetup.ipynb).

Notice that to successfully setup your own WorkflowHub instance to work with
LifeMonitor you must make sure the following requirements are met.

###### HTTPs enabled
HTTPS must be enabled on your WorkflowHub instance
([here](https://github.com/crs4/life_monitor/blob/first-release-docs/docs/wfhub-setup-notes.md)
some note on how to enable HTTPs) and its certificates should be valid by the
LifeMonitor instance you have to connect. You could use certificates issued by a
know certificate authority (e.g., Let's Encrypt) or use the autogenerated
LifeMonitor certificate. It is automatically generated when you start a
deployment, but can also be regenerated by deleting the existing `certs` folder
and typing `make certs`. It is a multi-domain certificate and you can customise
the list of certificate domain names by editing the `utils/gen-certs.sh` script.

###### Reachability
LifeMonitor needs to direct directly connect to the registry for different
purposes. Therefore, the registry should be bound to a hostname resolvable and
reachable by LifeMonitor. For this reason, if you are using the docker-compose
deployment you should avoid `localhost` as hostname for the registry, unless you
reconfigure the deployment to use the `host` Docker network mode.

###### Additional notes on WorkflowHub configuration

* In order to get correct URLs from the WorkflowHub API, you need to set the base URL. Go to Server admin > Settings and set "Site base URL" to `https://<BASE_URL>:3000` (e.g., `https://seek:3000` is the configuration of this field on the [Seek](#aux-services) instance f the pre-configured LifeMonitor deployment ).

* To enable workflows, go to Server admin > Enable/disable features and click on "Workflows enabled". You can set "CWL Viewer URL" to `https://view.commonwl.org/`.
