# Welcome to LifeMonitor

LifeMonitor is a service to support the **sustainability** and **reusability**
of published computational workflows.

The collapse [[1](#hinsen2019)] over time of the software and services on
which computational workflows depend is destructive to their reusability, and
to the **reproducibility** of work for which they were used; this phenomenon
can be caused by an API change that is not backwards compatible, a regression
in a tool whose version was not pinned, a change in URL of an external
resource, etc. Frequent **testing** is crucial to the preservation of workflow
health, allowing to expose problems when they arise and providing a
machine-actionable way to verify changes to the workflow
structure. LifeMonitor aims to facilitate the maintenance of computational
workflows, supporting their reusability over time, with a strong focus on
testing and test monitoring.

The project's main goals are to:

* Serve as a central aggregation point for workflow test statuses and outputs
  from various testing services (e.g., [Travis CI](https://travis-ci.org/),
  [GitHub Actions](https://docs.github.com/en/actions),
  [Jenkins](https://www.jenkins.io/), etc.).
* Facilitate the periodic automated execution of workflow tests.
* Integrate with [WorkflowHub](https://about.workflowhub.eu/).
* Assist in test suite creation and workflow maintenance.


<!-- ## Documentation

* [Getting started](getting_started)
* [REST API](lm_api_specs)
* [Using the API via CLI](restish-cli)
* [Administration Guide](lm_admin_guide)
* [Workflow Testing RO-crate specification](workflow_testing_ro_crate) -->


## Road map

LifeMonitor is still in early development.  Here is our planned development road map.

#### End of 2020
- [x] Support for receiving workflow POSTs as Workflow RO-crate
- [x] Relatively stable interface and implementation for test outcome retrieval
- [x] Complete first draft of the [Workflow Testing RO-crate specification](workflow_testing_ro_crate)
- Support monitoring tests running on external testing services:
    - [x] TravisCI
    - [x] Jenkins

#### Spring 2021
  - [x] Workflow Testing RO-crate template creation (integrated in
        [ro-crate-py](https://github.com/ResearchObject/ro-crate-py))
  - [x] Alpha release on <https://lifemonitor.eu>

#### Mid 2021
  - [ ] WorkflowHub integration?
  - [ ] Command line client
  - [ ] Web interface
  - Support monitoring tests running on external testing services:
      - [ ] Github Actions

#### Later
  - [ ] Programmable periodic test execution
  - [ ] Support workflow test creation
  - [ ] Workflow maintenance plugins (e.g., Docker image linting)
  - [ ] Automatic configuration of GitHub Actions for workflow testing


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
<a name="hinsen2019">[1]</a> K. Hinsen, <em>Dealing with software collapse</em>. Computing in Science & Engineering 21 (3), 104-108 (2019).
