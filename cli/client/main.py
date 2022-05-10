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

import logging

import click

from rich.console import Console
from rich.text import Text

from issues import issues_group


from lifemonitor import get_version
__version__ = get_version()
del get_version


@click.group(help=f"LifeMonitor CLI (ver {__version__})")
@click.option("--debug", "debug", is_flag=True, default=False)
@click.pass_context
def cli(ctx: click.Context, debug):
    ctx.obj = ctx.obj or {}
    ctx.obj["debug"] = debug
    if debug:
        logging.basicConfig(level=logging.DEBUG)


@cli.command(help="Show CLI version")
def version():
    console = Console()
    console.print(Text.assemble("Version: ", Text(__version__, style="white bold")))


if __name__ == '__main__':
    cli.add_command(issues_group)
    cli.main(prog_name="lm")
