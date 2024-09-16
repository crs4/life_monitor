# Authenticating clients with the LifeMonitor API

This documentation concerns [Generic Clients](lm_api_specs#clients) (*not*
Registry Clients).

## API key

Once you have [logged in to LifeMonitor](https://api.lifemonitor.eu) you can
create an API key for your client.  Select the **API Keys** tab, then click on
the `NEW` button.

<img alt="LM Click to create new API key" src="images/lm_click_new_api_key.png" width="600" />

The new API key appears in the list and is immediately ready to use.  Copy it
and configure your client to use it.  The API calls compatible with API Key
authentication are specified in the [API
specs](https://api.lifemonitor.eu/openapi.html): look at the top right
of each call's section for a list of authentication methods compatible with
that call (if there's nothing there, then the call does not require
authentication).

## OAuth2

LifeMonitor supports [OAuth2 Authorization
Code](https://www.oauth.com/oauth2-servers/server-side-apps/authorization-code)
authentication.  All API calls compatible with this authentication scheme are
visible in the [API specs](https://api.lifemonitor.eu/static/apidocs.html) with
the authentication scheme *OAuth (AuthorizationCodeFlow)*.

To use OAuth2 with LifeMonitor, you have to register your client first.

### Registering your OAuth2 client with LifeMonitor

Log in at <https://api.lifemonitor.eu>, then select the **OAuth Apps** tab.

<img alt="LM OAuth Apps list" src="images/lm_oauth_apps.png" width="500" />

Click on the `NEW` button on the right.  The OAuth2 Application Client module
opens.

<img alt="LM OAuth Application Client"
src="images/lm_oauth2_application_client.png" width="500" />

The configuration of this module is specific to the client application
you're using.  For an example you can look at the instructions on how to
set up the [restish command line client](restish-cli).