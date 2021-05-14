# Welcome to LifeMonitor

LifeMonitor is a **testing and monitoring service** for scientific workflows.

The "collapse" over time of the software and services on which computational
workflows depend for correct operation is destructive to their reusability,
and to the reproducibility of work for which they were used; in this case,
"collapse" can be a change in API that is not backwards compatible, a regression
in a tool whose version was not pinned, a change in URL of an external resource,
etc.

LifeMonitor aims to facilitate the creation, sharing, periodic execution and
monitoring of workflow tests, ensuring that software collapse is detected and
communicated to the authors, in the hope it will be solved thus extending the
useful life of the workflows.

The project's main goals are to:

* Serve as a central aggregation point for workflow test statuses and outputs
  from various testing bots (e.g., [Travis CI](https://travis-ci.org/),
  [GitHub Actions](https://docs.github.com/en/actions), your own
  [Jenkins](https://www.jenkins.io/) instance, etc.).
* Allow to execute workflow tests on a built-in Jenkins-based service.
* Facilitate periodic automated execution of tests for
  [Galaxy](https://usegalaxy.org/), [Nextflow](https://www.nextflow.io/) and
  [CWL](https://www.commonwl.org/) workflows.
* Integrate with [WorkflowHub](https://about.workflowhub.eu/).
* Provide access through multiple user interfaces: Web GUI, CLI client, REST API.


## Documentation

* [Getting started](getting_started)
* [REST API](lm_api_specs)
* [Using the API via CLI](restish-cli)
* [Administration Guide](lm_admin_guide)
* [Workflow Testing RO-crate specification](workflow_testing_ro_crate)


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
  - [ ] Alpha release on <https://lifemonitor.eu>

#### Mid 2021
  - [ ] WorkflowHub integration?
  - [ ] Command line client
  - [ ] Web interface
  - Support monitoring tests running on external testing services:
      - [ ] Github Actions

#### Later
  - [ ] Internal testing service managed by LifeMonitor
  - [ ] Programmable periodic test execution
  - [ ] Support workflow test creation


## Acknowledgments

LifeMonitor is being developed as part of the [EOSC-Life project](https://www.eosc-life.eu/)

<img alt="EOSC-Life Logo" src="https://github.com/crs4/life_monitor/raw/master/docs/logo_EOSC-Life.png" width="100" />
<img alt="CRS4 Logo" src="https://github.com/crs4/life_monitor/raw/master/docs/logo_crs4-transparent.png" width="100" />
<img alt="BBMRI-ERIC Logo" src="https://github.com/crs4/life_monitor/raw/master/docs/logo_bbmri-eric.png" width="100" />
