# Workflow Testing RO-Crate

Please note this is a draft, subject to change. You can leave any comments [here](https://github.com/crs4/life_monitor/issues/51).

Workflow Testing RO-Crate is a specialization of [Workflow RO-Crate](https://about.workflowhub.eu/Workflow-RO-Crate/) that supports additional metadata related to the testing of computational workflows. [LifeMonitor](index) uses this as an exchange format that allows RO-Crate authors to describe test suites associated with workflows.

## Introduction

The LifeMonitor service aims to provide two main functionalities:

* Monitor workflow tests being executed on one or more Continuous Integration (CI) services. In this case the test metadata specifies a series of test **instances**, corresponding to execution jobs of the test suite on the testing service(s).

* Execute test suites according to a **definition** included in the metadata. Tests are defined according to specific test **engines**, such as [Planemo](https://planemo.readthedocs.io/en/latest/test_format.html).

## Concepts

This section uses terminology from the [RO-Crate 1.1 specification](https://w3id.org/ro/crate/1.1), which is the basis for the Workflow RO-Crate spec.

The **context** used by Workflow Testing RO-Crates is an extension of the [RO-Crate 1.1 context](https://www.researchobject.org/ro-crate/1.1/context.jsonld) that includes test-specific classes and properties defined in the [test RO-Terms vocabulary](https://github.com/ResearchObject/ro-terms/blob/master/test/vocabulary.csv):

```json
[
    "https://w3id.org/ro/crate/1.1/context",
    {
        "TestSuite": "https://w3id.org/ro/terms/test#TestSuite",
        "TestInstance": "https://w3id.org/ro/terms/test#TestInstance",
        "TestService": "https://w3id.org/ro/terms/test#TestService",
        "TestDefinition": "https://w3id.org/ro/terms/test#TestDefinition",
        "PlanemoEngine": "https://w3id.org/ro/terms/test#PlanemoEngine",
        "JenkinsService": "https://w3id.org/ro/terms/test#JenkinsService",
        "TravisService": "https://w3id.org/ro/terms/test#TravisService",
        "GithubService": "https://w3id.org/ro/terms/test#GithubService",
        "instance": "https://w3id.org/ro/terms/test#instance",
        "runsOn": "https://w3id.org/ro/terms/test#runsOn",
        "resource": "https://w3id.org/ro/terms/test#resource",
        "definition": "https://w3id.org/ro/terms/test#definition",
        "engineVersion": "https://w3id.org/ro/terms/test#engineVersion"
    }
]
```

The most recent version of the context is available from [https://github.com/ResearchObject/ro-terms/blob/master/test](https://github.com/ResearchObject/ro-terms/blob/master/test).

A Workflow Testing RO-Crate MUST be a valid [Workflow RO-Crate](https://about.workflowhub.eu/Workflow-RO-Crate/) (e.g., it has to contain a *Main Workflow*). In addition, it COULD refer to one or more test suites from the root data entity via the `mentions` property:

```json
{
    "@id": "./",
    "@type": "Dataset",
    "mentions": [
        {
            "@id": "#test1"
        },
        {
            "@id": "#test2"
        }
    ],
    ...
}
```

### Test suite

A _test suite_ describes a set of tests for a computational workflow. It is represented by a context entity of type `"TestSuite"`. A test suite MUST refer either to one or more [test instances](#test-instance) (via the `instance` property) or to a [test definition](#test-definition) (via the `definition` property) or both. Additionally, a test suite SHOULD refer to the tested workflow via `mainEntity`.

```json
{
    "@id": "#test1",
    "@type": "TestSuite",
    "mainEntity": {"@id": "sort-and-change-case.ga"},
    "instance": [
        {"@id": "#test1_1"}
    ],
    "definition": {"@id": "test/test1/sort-and-change-case-test.yml"}
}
```

### Test instance

A _test instance_ is a specific job that executes a [test suite](#test-suite) on a [test service](#test-service). It is represented by a context entity of type `"TestInstance"`. A test instance MUST refer to: a test service via the `runsOn` property; the base URL of the specific test service deployment where it runs via the `url` property; the relative URL of the test project via the `resource` property:

```json
{
    "@id": "#test1_1",
    "@type": "TestInstance",
    "runsOn": {"@id": "https://w3id.org/ro/terms/test#JenkinsService"},
    "url": "http://example.org/jenkins",
    "resource": "job/tests/"
}
```
 
### Test service

A _test service_ is a software service where tests can be run. It is represented by a context entity of type `"TestService"`:

```json
{
    "@id": "https://w3id.org/ro/terms/test#JenkinsService",
    "@type": "TestService",
    "name": "Jenkins",
    "url": {"@id": "https://www.jenkins.io"}
}
```

### Test definition

A _test definition_ is a set of metadata that describes how to run a [test suite](#test-suite). It is represented by a data entity of type `["File", "TestDefinition"]`. A test definition MUST refer to the [test engine](#test-engine) it is written for via `conformsTo` and to the engine's version via `engineVersion`:

```json
{
    "@id": "test/test1/my-test.yml",
    "@type": [
        "File",
        "TestDefinition"
    ],
    "conformsTo": {"@id": "https://w3id.org/ro/terms/test#PlanemoEngine"},
    "engineVersion": ">=0.70"
},
```

### Test engine

A _test engine_ is a software application that runs workflow tests according to a definition. It is represented by a context entity of type `"SoftwareApplication"`:

```json
{
    "@id": "https://w3id.org/ro/terms/test#PlanemoEngine",
    "@type": "SoftwareApplication",
    "name": "Planemo",
    "url": {"@id": "https://github.com/galaxyproject/planemo"}
}
```


## Example
An example of Workflow Testing RO-Crate metadata.

```json
{
    "@context": [
        "https://w3id.org/ro/crate/1.1/context",
        {
            "TestSuite": "https://w3id.org/ro/terms/test#TestSuite",
            "TestInstance": "https://w3id.org/ro/terms/test#TestInstance",
            "TestService": "https://w3id.org/ro/terms/test#TestService",
            "TestDefinition": "https://w3id.org/ro/terms/test#TestDefinition",
            "PlanemoEngine": "https://w3id.org/ro/terms/test#PlanemoEngine",
            "JenkinsService": "https://w3id.org/ro/terms/test#JenkinsService",
            "TravisService": "https://w3id.org/ro/terms/test#TravisService",
            "GithubService": "https://w3id.org/ro/terms/test#GithubService",
            "instance": "https://w3id.org/ro/terms/test#instance",
            "runsOn": "https://w3id.org/ro/terms/test#runsOn",
            "resource": "https://w3id.org/ro/terms/test#resource",
            "definition": "https://w3id.org/ro/terms/test#definition",
            "engineVersion": "https://w3id.org/ro/terms/test#engineVersion"
        }
    ],
    "@graph": [
        {
            "@id": "ro-crate-metadata.json",
            "@type": "CreativeWork",
            "about": {
                "@id": "./"
            },
            "conformsTo": {
                "@id": "https://w3id.org/ro/crate/1.1"
            }
        },
        {
            "@id": "./",
            "@type": "Dataset",
            "name": "sort-and-change-case",
            "description": "sort lines and change text to upper case",
            "license": "Apache-2.0",
            "mainEntity": {
                "@id": "sort-and-change-case.ga"
            },
            "hasPart": [
                {
                    "@id": "sort-and-change-case.ga"
                },
                {
                    "@id": "LICENSE"
                },
                {
                    "@id": "README.md"
                },
                {
                    "@id": "test/test1/sort-and-change-case-test.yml"
                }
            ],
            "mentions": [
                {
                    "@id": "#test1"
                }
            ]
        },
        {
            "@id": "sort-and-change-case.ga",
            "@type": [
                "File",
                "SoftwareSourceCode",
                "ComputationalWorkflow"
            ],
            "programmingLanguage": {
                "@id": "#galaxy"
            },
            "name": "sort-and-change-case"
        },
        {
            "@id": "LICENSE",
            "@type": "File"
        },
        {
            "@id": "README.md",
            "@type": "File"
        },
        {
            "@id": "#galaxy",
            "@type": "ComputerLanguage",
            "name": "Galaxy",
            "identifier": {
                "@id": "https://galaxyproject.org/"
            },
            "url": {
                "@id": "https://galaxyproject.org/"
            }
        },
        {
            "@id": "#test1",
            "name": "test1",
            "@type": "TestSuite",
            "mainEntity": {
                "@id": "sort-and-change-case.ga"
            },
            "instance": [
                {"@id": "#test1_1"}
            ],
            "definition": {"@id": "test/test1/sort-and-change-case-test.yml"}
        },
        {
            "@id": "#test1_1",
            "name": "test1_1",
            "@type": "TestInstance",
            "runsOn": {"@id": "https://w3id.org/ro/terms/test#JenkinsService"},
            "url": "http://example.org/jenkins",
            "resource": "job/tests/"
        },
        {
            "@id": "test/test1/sort-and-change-case-test.yml",
            "@type": [
                "File",
                "TestDefinition"
            ],
            "conformsTo": {"@id": "https://w3id.org/ro/terms/test#PlanemoEngine"},
            "engineVersion": ">=0.70"
        },
        {
            "@id": "https://w3id.org/ro/terms/test#JenkinsService",
            "@type": "TestService",
            "name": "Jenkins",
            "url": {"@id": "https://www.jenkins.io"}
        },
        {
            "@id": "https://w3id.org/ro/terms/test#PlanemoEngine",
            "@type": "SoftwareApplication",
            "name": "Planemo",
            "url": {"@id": "https://github.com/galaxyproject/planemo"}
        }
    ]
}
```
