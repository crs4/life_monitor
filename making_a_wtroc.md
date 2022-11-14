# Making a Workflow Testing RO-Crate

In order to have your workflow monitored by LifeMonitor, you need to package
it as a [Workflow Testing RO-Crate](workflow_testing_ro_crate) (WTROC). If you
have a Galaxy, Snakemake or Nextflow workflow that follows community best
practices, the easiest way to generate a WTROC for it is to use
[repo2rocrate](https://github.com/crs4/repo2rocrate). Example:

```bash
git clone https://github.com/nf-core/rnaseq
repo2rocrate -r rnaseq/ -o rnaseq.crate.zip
```

See repo2rocrate's documentation at the above link for more information.


## Using ro-crate-py

If your workflow type is not supported by repo2rocrate, or you can't conform
to community best practices for some reason, you can generate a WTROC with
[ro-crate-py](https://github.com/ResearchObject/ro-crate-py). Set up a Python
virtual environment and install ro-crate-py:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install rocrate
```

Now move into the directory that contains your workflow and associated
assets. This can be, for instance, a copy of a repository in a version control
provider such as [GitHub](https://github.com/). As an example, we're going to
use the [FAIR CRCC - send data](https://github.com/crs4/fair-crcc-send-data)
workflow.

```bash
git clone https://github.com/crs4/fair-crcc-send-data
cd fair-crcc-send-data/
```

Initialize the crate, ignoring the `.git` and `.github` directories:

```bash
rocrate init --exclude .git,.github
```

The above command creates an `ro-crate-metadata.json` file at the top level
that simply lists all files as `"File"` and directories as `"Dataset"`. This
includes the main workflow file:

```json
{
    "@id": "workflow/Snakefile",
    "@type": "File"
}
```

To register it as a computational workflow, run the following command:

```bash
rocrate add workflow -l snakemake workflow/Snakefile
```

If you check the JSON file now, you'll see that the entry for
`workflow/Snakefile` is more articulate: for instance, it has a more specific
`@type` and it links to an entity representing the Snakemake language. Other
changes have also been made to the crate so that it conforms to the [Workflow
RO-Crate spec](https://about.workflowhub.eu/Workflow-RO-Crate/). If your
workflow is written in a different language, specify it using the `-l` option
as shown above. To get a list of supported options, run:

```bash
rocrate add workflow --help
```

Now we need to point the crate to a test instance for the
workflow. LifeMonitor supports monitoring test executions that run on [Travis
CI](https://travis-ci.org/), [Jenkins](https://www.jenkins.io/) and [GitHub
Actions](https://docs.github.com/en/actions). In this case, the (scientific)
workflow is tested by a GitHub Actions workflow defined by
[.github/workflows/main.yml](https://github.com/crs4/fair-crcc-send-data/blob/main/.github/workflows/main.yml).

First, create a test suite:

```bash
rocrate add test-suite -i suite_1
```

Then, add a test instance that points to the CI workflow:

```bash
rocrate add test-instance suite_1 https://api.github.com -s github \
  -r repos/crs4/fair-crcc-send-data/actions/workflows/main.yml \
  -i first_test
```

Where `https://api.github.com` is the service URL, while the argument of the
`-r` option is a reference to the CI workflow in the form:

```bash
repos/<OWNER>/<REPO NAME>/actions/workflows/<YAML FILE NAME>
```

That's it! If you want, you can check `ro-crate-metadata.json` again to see
how it changed in response to the above commands. All that's left to do is to
zip the crate in the format accepted by WorkflowHub:

```bash
rocrate write-zip /tmp/fair-crcc-send-data.crate.zip
```
