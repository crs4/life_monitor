# Copyright (c) 2020-2021 CRS4
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitatioån the rights
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

import inspect
import logging
import os
import shutil
import sys

import click
from cli.client.utils import is_url
from lifemonitor.api.models.issues import (WorkflowRepositoryIssue,
                                           find_issues, load_issue)
from lifemonitor.api.models.repositories.github import GithubWorkflowRepository
from lifemonitor.api.models.repositories.local import LocalWorkflowRepository
from lifemonitor.utils import to_snake_case
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

logger = logging.getLogger(__name__)

issues_list = find_issues()

console = Console()
error_console = Console(stderr=True, style="bold red")

repository_arg = click.argument('repository', type=str, default=".")
changes_path_arg = click.option('--changes-path', type=click.Path(file_okay=False), default=None)


def _get_repository(repository: str, local_path: str = None):
    assert repository, repository
    if is_url(repository):
        remote_repo_url = repository
        if remote_repo_url.endswith('.git'):
            return GithubWorkflowRepository.from_url(remote_repo_url, auto_cleanup=False, local_path=local_path)
    else:
        return LocalWorkflowRepository(repository)
    return ValueError("Repository type not supported")


@click.group(name="issues", help="Tools to develop and check issue types")
@click.pass_obj
def issues_group(ctx):
    pass


@issues_group.command(help="List all available issue types")
@click.pass_obj
def list(config):
    # Configure Table
    table = Table(title="Available Issue Types", style="bold", expand=True)
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("ID", style="white")
    table.add_column("Name", style="bold white")
    table.add_column("Description", style="white")
    table.add_column("DependsOn", justify="left", style="dark_orange")
    table.add_column("Tags", justify="left", style="cyan")

    for idx in range(1, len(issues_list) + 1):
        i = issues_list[idx - 1]
        table.add_row(str(idx), i.get_identifier(), i.name,
                      Syntax(i.description, "html"), ", ".join([_.__name__ for _ in i.depends_on]), ", ".join(i.labels))
    console.print(table)


@issues_group.command(help="Describe an issue type")
@click.argument('issue_number', type=int, default=0)
@click.pass_obj
def get(config, issue_number):
    if issue_number not in range(1, len(issues_list) + 1):
        error_console.print("\nERROR: invalid issue number\n")
        sys.exit(99)
    i = issues_list[issue_number - 1]
    # Configure Table
    table = Table(title=f"Issue Type: [bold]{i.name}[/bold]", style="bold", expand=True)
    table.add_column("#", justify="right", style="bright_white bold", no_wrap=True)
    table.add_column("ID", style="white")
    table.add_column("Name", style="white bold")
    table.add_column("Description", style="white", overflow="fold")
    table.add_column("DependsOn", justify="center", style="dark_orange")
    table.add_column("Tags", justify="center", style="cyan")
    table.add_row(str(issue_number), i.get_identifier(), i.name,
                  Syntax(i.description, "html"), ", ".join([_.__name__ for _ in i.depends_on]), ", ".join(i.labels))
    console.print(table)
    p = Panel.fit(Syntax(inspect.getsource(i), "python", line_numbers=True), title=f"Source Code: [bold]{i.__module__}.{i.__name__}[/bold]")
    console.print(p)


def _check_changes_path(changes_path):
    logger.debug("Changes path: %r", changes_path)
    if not os.path.exists(changes_path):
        os.makedirs(changes_path, exist_ok=True)
    else:
        answer = Prompt.ask(f"The folder '{changes_path}' already exists. "
                            "Would like to delete it?", choices=["y", "n"], default="y")
        logger.debug("Answer: %r", answer)
        if answer == 'y':
            shutil.rmtree(changes_path)
        else:
            sys.exit(0)


@issues_group.command(help="Check for issues on a Workflow RO-Crate repository")
@repository_arg
@changes_path_arg
@click.pass_obj
def check(config, repository, changes_path=None):
    try:
        _check_changes_path(changes_path=changes_path)
        repo = _get_repository(repository, local_path=changes_path)
        result = repo.check(repository)
        # Configure Table
        table = Table(title=f"Check Issue Report of Repo [bold]{repository}[/bold]",
                      style="bold", expand=True)
        table.add_column("Issue ID", justify="left", style="white")
        table.add_column("Issue Name", justify="left", style="white bold")
        table.add_column("Status", style="white", overflow="fold", justify="center")
        table.add_column("Proposed Changes", justify="center", style="dark_orange")
        table.add_column("Tags", style="cyan", overflow="fold", justify="center")
        checked = [_.name for _ in result.checked]
        issues = [_.name for _ in result.issues]
        for issue in issues_list:
            x = None
            if issue.name not in checked:
                status = Text("Skipped", style="yellow bold")
            elif issue.name not in issues:
                status = Text("Passed", style="green bold")
            else:
                status = Text("Failed", style="red bold")
                x = result.get_issue(issue.name)
            table.add_row(issue.get_identifier(), issue.name, status,
                          ", ".join([_.path for _ in x.get_changes(repository)]) if x else "", ", ".join(issue.labels))
        console.print(table)

    except Exception as e:
        error_console.print(str(e))


@issues_group.command(help="Test an issue type")
@click.argument('issue_file', type=click.Path(exists=True))
@repository_arg
@changes_path_arg
@click.pass_obj
def test(config, issue_file, repository, changes_path=None):
    try:
        _check_changes_path(changes_path=changes_path)
        logger.debug(issue_file)
        repo = _get_repository(repository, local_path=changes_path)
        issues_list = [_() for _ in load_issue(issue_file)]
        logger.debug("Issue: %r", issues_list)
        logger.debug("Repository: %r", repo)
        # Configure Table
        table = Table(title=f"Check Issue Report of Repo [bold]{repository}[/bold]",
                      style="bold", expand=True)
        table.add_column("Issue ID", justify="left", style="white")
        table.add_column("Issue Name", justify="left", style="white bold")
        table.add_column("Status", style="white", overflow="fold", justify="center")
        table.add_column("Proposed Changes", justify="center", style="dark_orange")
        table.add_column("Tags", style="cyan", overflow="fold", justify="center")

        issues = []
        checked = []
        for issue in issues_list:
            checked.append(issue)
            issue_passed = issue.check(repo)
            if issue_passed:
                issues.append(issue)
        detected_issues = [_.name for _ in issues]
        for issue in issues_list:
            if issue.name not in detected_issues:
                status = Text("Passed", style="green bold")
            else:
                status = Text("Failed", style="red bold")
            table.add_row(issue.get_identifier(), issue.name, status,
                          ", ".join([_.path for _ in issue.get_changes(repository)]),
                          ", ".join(issue.labels))
        console.print(table)
    except Exception as e:
        logger.exception(e)
        error_console.print(str(e))


@issues_group.command(help="Generate a skeleton class for an issue type")
@click.argument('path', type=click.Path(exists=True, file_okay=False), default=".")
@click.pass_obj
def generate(config, path):
    logger.debug("Path: %r", path)
    name = Prompt.ask(Text.assemble(Text("Choose a name ", style="bold"), "(e.g., ", Text("'Missing Important RO-Crate File'", style="dark_orange"), ")"))
    logger.debug("Name: %r", name)
    class_name = Prompt.ask(Text.assemble(Text("Choose a class name ", style="bold"), "(e.g., ", Text('MissingFileIssue', style="dark_orange"), ")"))
    logger.debug("Class name: %r", class_name)
    description = Prompt.ask(Text("Choose a description", style="bold"))
    logger.debug("Class name: %r", description)
    labels = Prompt.ask(Text.assemble(Text("Choose a list of comma-separated labels ", style="bold"), "(e.g., ", Text("bug, enhancement", style="dark_orange"), ")"))
    logger.debug("labels: %r", labels)
    template = WorkflowRepositoryIssue.generate_template(class_name=class_name, name=name, description=description, labels=labels)
    logger.debug("Template: %r", template)
    output_file = os.path.join(path, f"{to_snake_case(class_name)}.py")
    with open(output_file, "w") as out:
        out.write(template)
        console.print(f"Issue class written @ {output_file}")
