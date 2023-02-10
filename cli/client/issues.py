# Copyright (c) 2020-2022 CRS4
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
import sys

import click
from cli.client.utils import get_repository, init_output_path
# from flask.cli import with_appcontext
from lifemonitor.api.models.issues import (WorkflowRepositoryIssue,
                                           find_issue_types, load_issue)
from lifemonitor.utils import to_snake_case
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

logger = logging.getLogger(__name__)

issues_list = find_issue_types()

custom_theme = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "error": "bold red"
})


console = Console(theme=custom_theme)
error_console = Console(stderr=True, style="bold red")

repository_arg = click.argument('repository', type=str, default=".")
output_path_arg = click.option('-o', '--output-path', type=click.Path(file_okay=False), default=None)


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
                      Syntax(i.description, "html"), ", ".join([_.get_identifier() for _ in i.depends_on]), ", ".join(i.labels))
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


@issues_group.command(help="Check for issues on a Workflow RO-Crate repository")
@repository_arg
@output_path_arg
@click.pass_obj
# @with_appcontext
def check(config, repository, output_path=None):
    try:
        init_output_path(output_path=output_path)
        repo = get_repository(repository, local_path=output_path)
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
        # show optional messages
        console.print("\n\n")
        for issue in result.issues:
            for message in issue._messages:
                console.print(f"[{message.type.value}]{message.type.name}:[/{message.type.value}] {message.text}")
        console.print("\n\n")
    except Exception as e:
        logger.exception(e)
        error_console.print(str(e))


@issues_group.command(help="Test an issue type")
@click.argument('issue_file', type=click.Path(exists=True))
@click.option('-c', '--issue-class', type=str, multiple=True, default=None, )
@click.option('-w', '--write', is_flag=True, help="Write proposed changes.")
@repository_arg
@output_path_arg
@click.pass_obj
# @with_appcontext
def test(config, issue_file, issue_class, write, repository, output_path=None):
    proposed_files = []
    try:
        logger.debug("issue classes: %r", issue_class)
        init_output_path(output_path=output_path)
        logger.debug(issue_file)
        repo = get_repository(repository, local_path=output_path)
        issues_types = load_issue(issue_file)
        logger.debug("Types of issues: %r", [_ for _ in issues_types])
        issues_list = [_() for _ in issues_types if not issue_class or _.__name__ in issue_class]
        logger.debug("List of issues: %r", issues_list)
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
            issue_files = [_.path for _ in issue.get_changes(repository)]
            table.add_row(issue.get_identifier(), issue.name, status,
                          ", ".join(issue_files),
                          ", ".join(issue.labels))
            proposed_files.extend(issue_files)
        console.print(table)

        # show optional messages
        console.print("\n\n")
        for issue in issues:
            for message in issue._messages:
                console.print(f"[{message.type.value}]{message.type.name}:[/{message.type.value}] {message.text}")
        console.print("\n\n")
    except Exception as e:
        logger.exception(e)
        error_console.print(str(e))
    finally:
        logger.debug("Write: %r -> %r", write, proposed_files)
        if not write and proposed_files:
            for f in proposed_files:
                logger.debug("Deleting %s", f)
                os.remove(f)


@issues_group.command(help="Generate a skeleton class for an issue type")
@output_path_arg
@click.pass_obj
def generate(config, output_path):
    init_output_path(output_path=output_path)
    logger.debug("Path: %r", output_path)
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
    output_file = os.path.join(output_path, f"{to_snake_case(class_name)}.py")
    with open(output_file, "w") as out:
        out.write(template)
        console.print(f"Issue class written @ {output_file}")
