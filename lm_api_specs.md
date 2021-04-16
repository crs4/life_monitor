# Life Monitor API Specs

**Life Monitor (LM)** exposes its functionalities through a RESTful API defined with
[OpenAPI](https://swagger.io/specification).

### Actors

The LM API is designed with _two types_ of **actors** in mind:

1. **Users**
2. **Registries**

Both can manage their own workflows and associated workflow tests through the LM
API. In addition, Registries can _act on their users' behalf_, and thus, they
can manage workflows and workflow tests that belong to their users. For
instance, you may register a workflow on the [Workflow Hub
registry](https://workflowhub.eu/) and it may in turn register on your behalf
the workflow's tests with the Life Monitor.

### Clients

Thanks to the RESTful implementation and the adoption of OAuth 2.0 as
authorisation protocol, the LM API provides support for a variety of different
clients (e.g., scripting tools, web apps, etc.).

Clients allow users and registries to interact with the LifeMonitor API.  With
respect to the actors they support, we can distinguish between:

- **Generic Clients**: can act on behalf of a user to register user's workflows
  and associated workflow tests;

- **Registry Clients**: allow a registry to submit its own workflows and
  associated workflow tests. In addition, registries can act on their users’
behalf and submit their users' workflows and associated workflow tests.

<img alt="Life Monitor client types" src="images/lm_clients.png" width="900" />

The authorisation mechanisms available for clients are:

* **API key**, can be used to implement generic clients;
* **OAuth2 Client Credentials**, only available for trusted workflow registries
  (see *RegistryClientCredentials*);
* **OAuth2 Authorization Code**, available for both generic clients (see
  *AuthorizationCodeFlow*) and registry clients (see *RegistryCodeFlow*).

Clients can query API endpoints according to the authorisation mechanism they
adopt.  There are in fact resources which are _"contextual"_ to the actor which
the client is acting on behalf of and the type of "impersonated" actor is
determined by the authorisation grant in use. Examples of contextual resources
are:

- `/users/current/*`, which assume an authenticated _user_ and thus can be
  queried only by clients authorised through an _API key_, an OAuth2
_AuthorizationCodeFlow_ or _RegistryCodeFlow_;

- `/registries/current/*`, which assume an authenticated _registry_ and thus can
  be queried only by clients authorised through an OAuth2
_RegistryClientCredentials_ or _RegistryCodeFlow_.

### Useful resources

- [API documentation and examples](https://api-lifemonitor-dev.rahtiapp.fi/static/apidocs.html).
- [YAML API specifications](https://github.com/crs4/life_monitor/tree/master/specs).
