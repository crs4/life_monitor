"""\
Start services:

    make startdev
    docker run -d --network life_monitor_default -p 3000:3000 --name wfhub fairdom/seek:workflow

LM now can connect to the Workflow Hub at http://wfhub:3000 (a real wf hub
would have a public address).

Create a user, enable workflows and upload a workflow via the wf hub GUI as
explained in the ro_crate_test.ipynb notebook. Run this on the LM container.
"""

from lifemonitor.wfhub import Client

client = Client("http://wfhub:3000")
workflows = client.get_workflows()
id_ = workflows[0]["id"]
workflow = client.get_workflow(id_)
path = client.download_workflow(workflow, "/tmp")
print(f"workflow {id_} downloaded to {path}")
