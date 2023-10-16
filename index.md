# Welcome to <span style="font-style: italic; font-family: Baskerville,Baskerville Old Face,Hoefler Text,Garamond,Times New Roman,serif;">Life</span><span class="small" style="font-size: 75%; margin: 0 -1px 0 1px;">-</span><span style="font-weight: bold; font-family: Gill Sans,Gill Sans MT,Calibri,sans-serif;">Monitor</span>

LifeMonitor is a service to support the **sustainability** and **reusability**
of published computational workflows.

The collapse [[1](#hinsen2019)] over time of the software and services on
which computational workflows depend is destructive to their reusability, and
to the reproducibility of work for which they were used; this phenomenon
can be caused by an API change that is not backwards compatible, a regression
in a tool whose version was not pinned, a change in URL of an external
resource, etc. Frequent **testing** is crucial to the preservation of workflow
health, allowing to expose problems when they arise and providing a
machine-actionable way to verify changes to the workflow
structure. LifeMonitor aims to facilitate the maintenance of computational
workflows, supporting their **reusability** over time, with a strong focus on
testing and test monitoring.

The project's main goals are to:

* Serve as a central aggregation point for workflow test statuses and outputs
  from various testing services (e.g., [GitHub
  Actions](https://docs.github.com/en/actions),
  [Jenkins](https://www.jenkins.io/), [Travis CI](https://travis-ci.org/),
  etc.).
* Facilitate the application of workflow best practices, including periodic
  automated execution of workflow tests.
* Integrate with [WorkflowHub](https://about.workflowhub.eu/).
* Assist in test suite creation and workflow maintenance.

## Quick Start

:bulb: If you just want to play around or get familiar with the API, use the
[dev instance of LifeMonitor](https://app.dev.lifemonitor.eu) (note that the dev
instance could be wiped out at any time with no warning).

1. Install the [LifeMonitor GitHub app](https://github.com/apps/lifemonitor) on
   your workflow's repository;
2. Follow the installation process to enable issue checks;
3. Follow the instructions provided by the bot through pull requests and/or
   issues opened on your workflow repository to configure [test
   monitoring](./lm_test_monitoring) and improve the application of workflow
   sustainability best practices;
4. Profit!

Once installed, the LifeMonitor app can be configured to:

* support the configuration of [test monitoring](./lm_test_monitoring) by the
  LifeMonitor service;
* notify [WorkflowHub](https://about.workflowhub.eu/) and
  [LifeMonitor](https://app.lifemonitor.eu/) about new workflow releases;
* analyze the workflow through a series of checks to signal possible
  improvements pertaining to maintenance best practices.

See the
[page describing the LifeMonitor GitHub app](lm_wft_best_practices_github_app)
for more detailed information on what it does and how it can be configured.

If you don't want to install the GitHub app, you can still use LifeMonitor’s
test monitoring and periodic test execution features. Follow [the instructions
on configuring test monitoring](./lm_test_monitoring).

If you still don't have tests for your workflow or you haven't created an
automated testing pipeline, see [our page on general workflow testing
tips](./reference_general_workflow_testing_tips).


## Acknowledgments

LifeMonitor was started as part of the [EOSC-Life
project](https://www.eosc-life.eu/) and is developed by
[CRS4](https://www.crs4.it/) with contributions from the wider
[WorkflowHub Club](https://about.workflowhub.eu/project/community/#workflowhub-club).
<div>
  <a title="Acknowledgments" href="https://www.eosc-life.eu">
    <img alt="Acknowledgments"
         width="300px"
         src="https://github.com/crs4/life_monitor/raw/master/docs/footer-logo.svg" style="vertical-align: middle" />
  </a>
</div>

Hosting for LifeMonitor is provided by [CSC](https://www.csc.fi/en/).
<div>
  <a title="Hosting-CSC" href="https://www.csc.fi/en">
    <img alt="Hosting by CSC"
         width="200px"
         src="images/csc.png" style="vertical-align: middle" />
  </a>
</div>

---
<a name="hinsen2019">[1]</a> K. Hinsen, <em>Dealing with software collapse</em>.
Computing in Science & Engineering 21 (3), 104-108 (2019).
