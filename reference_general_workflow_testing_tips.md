# General Workflow Testing Tips

Workflows are a type of complex software, so the general principles of software
testing apply to your workflows just like they apply to other software -- such
as the individual tools that compose your workflow.

## Test cases

To test software, you'll need to create some test cases. Each test case creates
a scenario by defining input data, workflow parameters, and the
expected output(s) of the execution of the workflow. The execution of the test
case compares the output of the workflow with the expected result: a match
results in a passing test; otherwise, the test fails.

One should try to create several test cases for the workflow, each one prodding
different areas of its input and parameter spaces, in the hopes of catching
different kinds of problems should they arise. The tests should be easy and
relatively quick to run, which normally entails that they require few computing
resources.  This makes it easier to run the tests and to do so frequently.
Small tests also make it easier to understand what's happening when things go
wrong.

In general, the tests need to run when the software/workflow or any "input
models" (e.g., reference genomes, annotation databases, etc.) change. In
addition, it's good to run the pipeline tests periodically (e.g., once or twice
per month) to catch problems due to changes or regressions in the workflow's
dependencies. These can trickle in subtly: for instance, a new version of a tool
or other dependency whose version is not specified, or changes to an outside
service used by the workflow (e.g., an annotation API). Also, especially if the
components of the pipeline are not
fully containerized, it's good to periodically execute tests that re-compile
and/or re-install the software and its dependencies.

## Test data

While you should always try to keep your test data as small as possible, if
your tests require a non-trivial amount of data, try to host them outside the
repository and download them as part of the test execution process. For
instance, you can try to use data from a publicly accessible source, or host a
file on your institutional infrastructure or any of the various free
cloud-based storage services.  You should also try to re-use the same data for
multiple test cases.

## Implementing tests

While there is no "right way" to implement your tests, you should be aware that
there are software tools to help you with the task.

First of all, check to see what's available for your specific workflow manager.
For instance, users of the [Galaxy workflow manager](https://galaxyproject.org/)
are encouraged to use the [Planemo
tool](https://planemo.readthedocs.io/en/latest/) for creating and running
workflow tests.  The [Snakemake workflow
manager](https://snakemake.readthedocs.io/en/stable/) provides functionality to
automatically [generate unit
tests](https://snakemake.readthedocs.io/en/stable/snakefiles/testing.html).

There are also more workflow-agnostic software frameworks to support test
writing. Examples are [pytest-workflow](https://pytest-workflow.readthedocs.io)
or the more general-purpose [pytest](https://docs.pytest.org).  A simple bash
script that executes your workflow and uses `diff` to verity its output can
also work just fine.

## Continuous integration services

Continuous integration (CI) services can automate and manage the execution of
your workflow tests.  Periodically, or when a new version of your workflow is
published, a CI service can automatically run your tests to make sure the
workflow is working as expected. LifeMonitor monitors the results produced
by such CI services and reports them as the "health status" of your workflow.

LifeMonitor is best integrated with the [GitHub
Actions](https://github.com/features/actions) system, which works very well
with software repositories hosted on
GitHub. [Jenkins](https://www.jenkins.io/) is also an option, in particular
for tests which must be run on a private computing infrastructure. [Travis
CI](https://www.travis-ci.com/) is supported as well. Many more options are
available but not currently supported by LifeMonitor. [Get in
touch](https://github.com/crs4/life_monitor/issues) if you would like to
contribute or request support for another system.
