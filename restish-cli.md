
# Life Monitor CLI

You can use Life Monitor from the command line with the
[restish](https://rest.sh/#/guide?id=guide) client for openAPIs.  Follow this
documentation to walk you through the steps to get you going.

## Install restish

Refer to the [restish documentation](https://rest.sh/#/guide?id=installation)
for up-to-date and complete instructions.  For convenience, we summarize the installation steps here.  You have three
options:

Grab a [binary release](https://github.com/danielgtaylor/restish/releases) for
your platform:
```
$ wget https://github.com/danielgtaylor/restish/releases/download/v0.7.0/restish-0.7.0-linux-x86_64.tar.gz
$ tar xzf restish-0.7.0-linux-x86_64.tar.gz
$ ./restish --version
restish version 0.7.0
```

Use `Go get`:
```
$ go get -u github.com/danielgtaylor/restish
```

Use Homebrew:
```
# Add the tap
$ brew tap danielgtaylor/restish

# Install the executable
$ brew install restish
```

## Configure Restish to work with the Life Monitor API

Make sure you have credentials to access the Life Monitor API (see the [getting
started page](getting_started) otherwise).  Access the [Life Monitor](https://api.lifemonitor.eu/) page, log in and get an API key.  You can then configure `restish` to use it to access the API:
```
$ restish api configure lm https://api.lifemonitor.eu
? Select option Edit profile default
? Select option for profile `default` Add header
? Header name ApiKey
? Header value (optional) <YOUR API KEY HERE>
? Select option for profile `default` Finished with profile
? Select option Save and exit
```

Unfortunately, because of an [issue with restish](
https://github.com/danielgtaylor/restish/issues/44) it will generate an
incompatible configuration.  To fix it follow these instructions.

1. Use your favourite editor to open the restish configuration file
   `$HOME/.restish/apis.json`
2. Find the Life Monitor configuration remove the following structure from it:
```
  "auth": { 
    "name": "oauth-authorization-code", 
    "params": { 
      "authorize_url": "oauth2/authorize", 
      "client_id": "", 
      "token_url": "oauth2/token" 
    }
```

Now you should be ready to go.  Test things out:  try to query your user
profile:
```
$ restish lm show-current-user-profile
HTTP/1.1 200 OK
Access-Control-Allow-Origin: *
Cache-Control: private
Content-Length: 664
Content-Type: application/json
Date: Mon, 03 May 2021 16:19:52 GMT
Server: nginx
Set-Cookie: session=.eJwlzjkOwjAQQNG7uKbwLLZncpnInkXQJqRC3J1ItP8371P2POJ8lu19XPEo-8vLVlK4YjVYSObQAHhRVeE-OoFOIE4EbLkUxYDvlJ1mj5i-6siaU6J3uj9FdYsp1mkosTAaWfJsyhq6BNQJRRs0dFcO5QoB5YZcZxx_DZfvD0-SLiM.YJAiqA.UZu2x0Zrc7p6LQrgQt-OwTsL8ic; HttpOnly; Path=/
a4f14707e508ff4121052c83aea9e62e=a4c568703bcc20346735ea36d21623e8; path=/; HttpOnly; Secure
Vary: Cookie
X-Frame-Options: SAMEORIGIN

{
  id: 43838
  identities: {
    github: {
      email: ""
      name: "My name"
      picture: "https://avatars.githubusercontent.com/u/1029365?v=4"
      profile: "https://github.com/myname"
      provider: {
        name: "github"
        type: "oauth2_identity_provider"
        uri: "https://api.github.com/"
        userinfo_endpoint: "https://api.github.com/user"
      }
      sub: "5029316"
      username: "myname"
    }
  }
  meta: {
    api_version: "0.2.0-beta2"
    base_url: "https://api.lifemonitor.eu"
    resource: "/users/current"
  }
  username: "myname"
}
```

## What can you do?

The `restish` client will give you access to all API calls.

To see all the available calls:
```
$ restish lm
*Workflow sustainability service*

Life Monitor aims to facilitate the sharing, execution and monitoring of
workflow tests over time, ensuring that deviations from the workflow's
correct operation are detected and communicated to the workflow authors so
that they might be solved, thus extending the useful life of the workflow.

Life Monitor is being developed as part of the [EOSC-Life project](https://www.eosc-life.eu/).

Usage:
  restish lm [flags]
  restish lm [command]

Available Commands:
  get-registry-users                 List users
  instances-builds-get-by-id         Get a test instance build
  instances-builds-get-logs          Get test instance build logs
  instances-delete-by-id             Delete a test instance
  instances-get-builds               Get the latest test instance builds
  instances-get-by-id                Get a test instance
  registry-user-workflows-get        List workflows for a user
  registry-user-workflows-post       Submit workflow for a user
....
```


To see what the commands do, remember that you can refer to the API specs at <https://api.lifemonitor.eu/static/apidocs.html>.

