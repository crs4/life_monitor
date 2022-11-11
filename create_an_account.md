# Creating an account and authenticating

To do anything but see public workflows, you must create an account and
authenticate with the LifeMonitor service.  Start by  clicking on "Sign in" at
the top right of the landing page.

## Use an external identity provider

LifeMonitor supports WorkflowHub and GitHub as *identity providers*, and
support for the [LS AAI](https://lifescience-ri.eu/ls-login/) is forthcoming.

Rather than creating a local account on the LifeMonitor we recommend that:

1. you use an external identity;
2. use the same identity on all the services used to manage your workflows
   (e.g., LifeMonitor, [WorkflowHub](https://about.workflowhub.eu/),
   [GitHub](https://github.com)).

Using the same identity across all services will allow them to interoperate more
effectively.

## Creating an account - external identity provider

Point your browser to the LifeMonitor web app: <https://app.lifemonitor.eu/>.

<img alt="LM login page" src="images/lm_login_page.png" width="600" />

To use an external identity provider (IdP), click on the relevant button; e.g.,

* "Sign in using GitHub" to use your GitHub account;
* "Sign in using WfHub" to use your WorkflowHub account.

Unless you're already authenticated with the IdP, you will be taken to their web
site where you'll be able to authenticate (i.e., with your GitHub or WorkflowHub
credentials).  You may be asked to authorize LifeMonitor to perform some
actions. You must "Allow" to proceed:

<div align="center">
  <img alt="LM web app authorization request" src="images/lm_web_auth.png" width="600" />
</div>

Once the process is completed, LifeMonitor will *automatically create the
account* associated with your selected identity.

## Creating an account - local identity

If you want to create a local LifeMonitor account, click on the "Sign
Up" link at the bottom of the form and follow the registration procedure.

You will be able to login and use all LifeMonitor features, but your identity
will be unknown to external services.

<img alt="LM Sign In form" src="images/lm_sign_in_form.png" width="400" />

## Signing in

To authenticate and sign in, click on "Sign in" at the top right of the landing
page and follow the instructions.

:bulb: Always use the same identity to sign into LifeMonitor or you will end
up with multiple unrelated LM accounts.
