# Support for best practices - LifeMonitor GitHub App

The workflow LifeMonitor supports the application of workflow sustainability
best practices.  Much of this revolves around following *community-accepted
conventions* for your specific workflow type and implementing *periodic workflow
testing*. Following conventions allows existing computational tools to understand
your workflow and its metadata. On the other hand, periodic workflow testing
ensures that problems that can arise over time due to software collapse are
detected and interested people notified: for workflow authors, it gives them the
opportunity to fix the workflow and keep it useful; for potential workflow
re-users, it reassures them that the workflow works and is maintained.

LifeMonitor supports the application of repository best practices through [its
GitHub App](#the-lifemonitor-github-app), while the LifeMonitor service [supports
periodic workflow testing](./lm_test_monitoring).

## Supported workflow managers

LifeMonitor is currently striving to support
[Galaxy](https://galaxyproject.org/) and
[Snakemake](https://snakemake.readthedocs.io/en/stable/) workflows.

[Contributions](https://github.com/crs4/life_monitor/pulls) to help us support
other workflow systems are more than welcome!

## The LifeMonitor GitHub App

The [LifeMonitor GitHub app](https://github.com/apps/lifemonitor) does the
following things.

* Examines the repositories on which it is installed and applies a series of
  *checks*.
* Suggests pull requests to make changes or additions to bring the workflow
  repository closer to conforming to best practices.
* Opens issues to let you know about problems detected by the checks:
  * you can converse with the LM bot through the issues, to provide
    information or issue commands.
* Registers new releases/versions of the workflow with both the [LifeMonitor
  service](https://app.lifemonitor.eu/) and the
  [WorkflowHub](https://workflowhub.eu/) workflow registry.

Naturally, all these actions can enabled or disabled in the [app configuration
file](#configuration-file).

Exactly which checks are applied depends on the type of workflow you have and
can change in time as the development of LM moves forward.

### Installation

1. Navigate to the [LifeMonitor GitHub app management
   page](https://github.com/apps/lifemonitor).
2. Click the "Install" button;
    ![LM App Install button](./images/lm_gh_app_install_button_with_arrow.png)
3. Pick the repository where you want to install the app.
    * Pick the account or organization that owns the repository;
    * Select one or more repositories using the form, the click "Install &
      authorize".
4. If it's the first time you install the app, the process will take you to the
   LifeMonitor web site to configure the GitHub integration settings.
    * To fully enable the GitHub app, make sure "Issue Checks" are enabled.
    * Set the default branches and tags that the app should consider as "new
      releases".
    * All the global settings can be overridden in the [repository-specific
      configuration file](#configuration-file).

### Configuration File

