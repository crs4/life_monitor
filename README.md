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
