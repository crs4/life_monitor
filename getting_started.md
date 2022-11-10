# Getting Started

There are several ways you can interact with LifeMonitor:

* through the [Web Application](https://app.lifemonitor.eu/);
* by using a [command line client](restish-cli);
* programmatically via its [REST API](lm_api_specs);

Under the hood, all of the above access the service via the API. Most API
calls require authentication, so the first thing to do is create an account.

## Start Life Monitoring

How to interact with LifeMonitor depends on your tech level and what you want
to achieve. The [web GUI](web-app) is the easiest way to
access the service and get an immediate visual feedback on workflow status.
For more advanced, feature-complete and programmatic interaction, you can use
the [REST API](lm_api_specs) -- e.g., with your own custom client or with a
general openAPI [command line client](restish-cli).

You will need to decide how to [authenticate your
client](authenticate-your-client).  Depending on your
client of choice, you may want to create an API key or use full OAuth2
authentication.

### API examples

The API specifications contain examples you can try out using your API key.
Head over to <https://api.lifemonitor.eu/static/apidocs.html>.
