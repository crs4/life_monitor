# Copyright (c) 2020-2024 CRS4
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""\
WorkflowHub client usage example.

You can point this script to an externally available workflow hub instance.

You can also spin up a local WorkflowHub on the same network as the LM:

    make startdev
    docker run -d --network life_monitor_default -p 3000:3000 \
      --name wfhub fairdom/seek:workflow

The lm service can now connect to the WorkflowHub at http://wfhub:3000.
Create a user, enable workflows and upload a workflow via the wf hub GUI as
explained in the ro_crate_test.ipynb notebook under interaction_experiments.
While registering the workflow, In the "New Workflow" page, enable public view
and download.

To generate a token, click on your user on the top right, select "My profile"
and go to "Actions" -> "API Tokens".
"""

import argparse
import sys

from lifemonitor.wfhub import Client


def main(args):
    with Client(args.wfhub_url, token=args.token) as client:
        workflows = client.get_workflows()
        print("SUMMARY:")
        for w in workflows:
            print(f"{w['id']}\t{w['attributes']['title']}")
        if args.id:
            id_ = str(args.id)
        else:
            id_ = workflows[0]["id"]
        workflow = client.get_workflow(id_)
        path = client.download_workflow(workflow, "/tmp")
    print(f"workflow {id_} downloaded to {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wfhub_url", metavar="HUB_URL")
    parser.add_argument("--token", metavar="STR", help="auth token")
    parser.add_argument("--id", type=int, metavar="INT",
                        help="get the workflow with this specific ID")
    main(parser.parse_args(sys.argv[1:]))
