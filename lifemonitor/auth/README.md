
## Enabling authentication with GitHub

To allow your instance of LifeMonitor to use GitHub as an identity provider,
you'll have to register it with your GitHub account.

On the GitHub page, navigate to

    Github > Settings > Developer Settings > OAuth Apps

On this page, "Register a new OAuth application".  Assuming `BASE_URL` is the
address where you're deploying LifeMonitor,


    Homepage URL: BASE_URL
    Authorization callback URL: BASE_URL/oauth2/auth/github

Should this documentation become obsolete, you can always verify the correct
value of the callback URL from the LifeMonitor openapi specification.

Once registered, copy the client ID and client secret to the `settings.conf`
file in your Life Monitor deployment and restart the application.
