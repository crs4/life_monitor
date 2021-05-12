# Getting Started

Follow this guide if you want to use LifeMonitor to monitor your workflows.

At the moment, LifeMonitor can be used through its [REST API](lm_api_specs)
or a [command line client](restish-cli).

To interact with the API, the first thing to do is to authenticate with
LifeMonitor.


## Create an account and authenticate

Point your browser to the LifeMonitor API endpoint <https://api.lifemonitor.eu/>.

:bulb: If you just want to play around or get familiar with the API, use the dev
instance of LifeMonitor (replace <https://api.lifemonitor.eu> with
<https://api.dev.lifemonitor.eu> throughout these instructions and examples).

:warning: Please note that the dev instance is meant for testing / development and it
could be wiped out at any time with no warning.

<img alt="LM login page" src="images/lm_login_page.png" width="600" />

Click on the "**Log in**" button.

You can log in directly with an existing account from one of the supported
external identity providers, like GitHub or the Workflow Hub (use the
appropriate buttons for this).

Alternatively you can click on "Sign Up" and follow the registration procedure
to create an LM-specific account.

<img alt="LM Sign In form" src="images/lm_sign_in_form.png" width="400" />

## Start Life Monitoring

Until [WorkflowHub](https://workflowhub.eu/) integration and the LifeMonitor
web interface are ready, the only way to use the LifeMonitor service is through
its [REST API](lm_api_specs) -- e.g., with your own custom client or with a
general openAPI [command line client](restish-cli).

You will need to decide how to [authenticate your
client](authenticate-your-client).  Depending on your
client of choice, you may want to create an API key or use full OAuth2
authentication.

### API examples

Remember that the API specifications contain examples and you can use your API key to try them out.  Head over to <https://api.lifemonitor.eu/static/apidocs.html>.
