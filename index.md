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
* Facilitate the periodic automated execution of workflow tests.
* Integrate with [WorkflowHub](https://about.workflowhub.eu/).
* Assist in test suite creation and workflow maintenance.

## Getting Started

1. Install the [LifeMonitor GitHub app](https://github.com/apps/lifemonitor) on
   your workflow's repository;
2. Profit!

The LifeMonitor app will analyze the repository and give further instructions
through Pull Requests and/or Issues.  See the
[page](lm_wft_best_practices_github_app) describing the LM GitHub app and LM's
support for workflow sustainability best practices for information on what it
does and how it can be configured.

Is the GitHub app is not an option?  You can still use LM’s test monitoring and
periodic test execution features. Follow [the instructions on configuring test
monitoring](./lm_test_monitoring) to register the workflow with the workflow
LifeMonitor.

If you still don't have tests for your workflow or you haven't created an
automated testing pipeline, see [our page on general workflow testing
tips](./reference_general_workflow_testing_tips).

## Road map

Here is our planned development road map.

#### End of 2020

* [x] Support for receiving workflow POSTs as Workflow RO-crate
* [x] Relatively stable interface and implementation for test outcome retrieval
* [x] Complete first draft of the [Workflow Testing RO-crate specification](workflow_testing_ro_crate)
* Support monitoring tests running on external testing services:
  * [x] TravisCI
  * [x] Jenkins

#### Spring 2021

* [x] Workflow Testing RO-crate template creation (integrated in
      [ro-crate-py](https://github.com/ResearchObject/ro-crate-py))
* [x] Alpha release on <https://lifemonitor.eu>

#### End of 2021

* [x] Command line client
* [x] Web interface
* Support monitoring tests running on external testing services:
  * [x] Github Actions
* [x] Workflow submission from the Web interface

#### Winter 2022

* [x] WorkflowHub integration
* [x] Email notifications

#### Spring 2022

* [x] GitHub app
* [x] Semi-automated workflow registration with GH app
* [x] Automated workflow update with GH app

#### Summer 2022

* [x] Programmable periodic test execution

#### Fall 2022

* [ ] Semi-automated configuration of GitHub Actions for workflow testing

#### Winter 2023

* [ ] LS-AAI support

#### Later

* [ ] Support workflow test creation
* [ ] Workflow maintenance plugins (e.g., Docker image linting)

## Acknowledgments

LifeMonitor is being developed as part of the [EOSC-Life project](https://www.eosc-life.eu/)

<div>
  <a title="Acknowledgments" href="https://www.eosc-life.eu">
    <img alt="Acknowledgments"
         width="300px"
         src="https://github.com/crs4/life_monitor/raw/master/docs/footer-logo.svg" style="vertical-align: middle" />
  </a>
</div>

---
<a name="hinsen2019">[1]</a> K. Hinsen, <em>Dealing with software collapse</em>.
Computing in Science & Engineering 21 (3), 104-108 (2019).
