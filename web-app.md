# LifeMonitor Web App

The [LifeMonitor Web App](https://app.lifemonitor.eu) provides a graphical
interface to the service, allowing to get a quick overview of the status of
monitored workflows.

The web app's landing page displays the status of public workflows. At the
top, an overall summary bar shows the number of workflows for each category:

* **Passing:** workflows whose test suites are all successful
* **Some passing:** workflows for which only part of the test suites are passing
* **Failing:** workflows whose test suites are all unsuccessful
* **Unavailable:** workflows with no testing data available

<div class="mb-5" align="center">
<img alt="LM workflow status summary" src="images/lm_web_summary.png" width="800" />
</div>

The rest of the page is devoted to a table that reports the detailed status of
each workflow:

<div class="mb-4" align="center">
<img alt="LM workflow status details" src="images/lm_web_workflows.png" width="800" />
</div>

Each row contains, from left to right:

* The workflow's name, unique ID and external (registry) ID
* The workflow's visibility (public or private)
* The workflow's type (e.g., Galaxy, CWL)
* The workflow's version
* A pie chart representing the share of passing and failing test suites
* A bar chart showing the duration and outcome of each individual test build

A click on either the workflow's name/UUID or the pie chart leads to a similar
table, this time containing detailed information on each test _suite_ belonging
to the workflow:

<div class="mb-4" align="center">
<img alt="LM test suite status" src="images/lm_web_suites.png" width="800" />
</div>

Each row shows the following:

* The suite's name and unique ID
* The test engine used by the suite's test definition, if it has one
* A pie chart representing the share of passing and failing test instances
* A bar chart showing the duration and outcome of each build for the suite

Again, clicking on the suite's name/UUID or on the pie chart brings us to the
next level of detail, that of test instances, which is structured in a similar
way to the ones above. Finally, clicking on the instance's name leads to the
instance's main page on the CI service, while clicking on the build bars takes
to each individual build's page.


## Authenticated users

The previous section dealt with browsing through public workflows. To see your
private workflows, log in by clicking on "Sign in" at the top right of the
landing page. Assuming you've already [logged in to
LifeMonitor](getting_started#create-an-account-and-authenticate), you will
receive an authorization request from the Web application:

<div align="center">
  <img alt="LM web app authorization request" src="images/lm_web_auth.png" width="600" />
</div>

Click on "Allow" at the bottom; you will be taken back to the dashboard, but
this time you should also be able to see any workflow you've registered with
private visibility.
