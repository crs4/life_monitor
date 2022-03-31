# Copyright (c) 2022 CRS4
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


import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import click
from click_option_group import GroupedOption, optgroup
from flask import current_app
from flask.blueprints import Blueprint
from flask.cli import with_appcontext
from flask.config import Config
from lifemonitor.utils import FtpUtils

from .db import backup, backup_options

# set module level logger
logger = logging.getLogger()

# define the blueprint for DB commands
_blueprint = Blueprint('backup', __name__)

# set help for the CLI command
_blueprint.cli.help = "Manage backups of database and RO-Crates"


class RequiredIf(GroupedOption):
    def __init__(self, *args, **kwargs):
        self.required_if = kwargs.pop('required_if')
        assert self.required_if, "'required_if' parameter required"
        kwargs['help'] = ("%s (NOTE: This argument is required if '%s' is True)" %
                          (kwargs.get('help', ''), self.required_if)).strip()
        super(RequiredIf, self).__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        we_are_present = self.name in opts
        other_present = self.required_if in opts

        if other_present:
            if not we_are_present:
                raise click.UsageError(
                    "Illegal usage: '%s' is required when '%s' is True" % (
                        self.name, self.required_if))
            else:
                self.prompt = None

        return super(RequiredIf, self).handle_parse_result(
            ctx, opts, args)


def synch_otptions(func):
    func = optgroup.option('--enable-tls', default=False, is_flag=True, show_default=True,
                           help="Enable FTP over TLS")(func)
    func = optgroup.option('-t', '--target', default="/", show_default=True,
                           help="Remote target path")(func)
    func = optgroup.option('-p', '--password', cls=RequiredIf, required_if='synch',
                           help="Password fot the FTPS account")(func)
    func = optgroup.option('-u', '--user', cls=RequiredIf, required_if='synch',
                           help="Username of the FTPS account")(func)
    func = optgroup.option('-h', '--host', cls=RequiredIf, required_if='synch',
                           help="Hostame of the FTPS server")(func)
    func = optgroup.group('\nSettings to connect with a remote site via FTPS')(func)
    func = click.option('-s', '--synch', default=False, show_default=True,
                        is_flag=True, help="Enable sync with a remote FTPS server")(func)
    return func


def __remote_synch__(source: str, target: str,
                     host: str, user: str, password: str,
                     enable_tls: bool):
    try:
        ftp_utils = FtpUtils(host, user, password, enable_tls)
        ftp_utils.sync(source, target)
        print("Synch of local '%s' with remote '%s' completed!" % (source, target))
        return 0
    except Exception as e:
        logger.debug(e)
        print("Unable to synch remote site. ERROR: %s" % str(e))
        return 1


@_blueprint.cli.group(name="backup", invoke_without_command=True)
@with_appcontext
@click.pass_context
def bck(ctx):
    if not ctx.invoked_subcommand:
        auto(current_app.config)


@bck.command("db")
@backup_options
@synch_otptions
@with_appcontext
def db_cmd(file, directory, verbose, *args, **kwargs):
    """
    Make a backup of the database
    """
    result = backup_db(directory, file, verbose, *args, **kwargs)
    sys.exit(result)


def backup_db(directory, file=None, verbose=False, *args, **kwargs):
    logger.debug(sys.argv)
    result = backup(directory, file, verbose)
    if result.returncode == 0:
        synch = kwargs.pop('synch', False)
        if synch:
            return __remote_synch__(source=directory, **kwargs)
    return result.returncode


@bck.command("crates")
@click.option("-d", "--directory", default="./", show_default=True,
              help="Local path to store RO-Crates")
@synch_otptions
@with_appcontext
def crates_cmd(directory, *args, **kwargs):
    """
    Make a backup of the registered workflow RO-Crates
    """
    result = backup_crates(current_app.config, directory, *args, **kwargs)
    sys.exit(result)


def backup_crates(config, directory, *args, **kwargs):
    assert config.get("DATA_WORKFLOWS", None), "DATA_WORKFLOWS not configured"
    rocrate_source_path = config.get("DATA_WORKFLOWS").removesuffix('/')
    os.makedirs(directory, exist_ok=True)
    result = subprocess.run(f'rsync -avh --delete {rocrate_source_path}/ {directory} ', shell=True, capture_output=True)
    if result.returncode == 0:
        print("Created backup of workflow RO-Crates @ '%s'" % directory)
        synch = kwargs.pop('synch', False)
        if synch:
            logger.debug("Remaining args: %r", kwargs)
            return __remote_synch__(source=directory, **kwargs)
    else:
        print("Unable to backup workflow RO-Crates\n%s", result.stderr.decode())
    return result.returncode


def auto(config: Config):
    logger.debug("Current app config: %r", config)
    base_path = config.get("BACKUP_LOCAL_PATH", None)
    if not base_path:
        click.echo("No BACKUP_LOCAL_PATH found in your settings")
        sys.exit(0)

    # set paths
    base_path = base_path.removesuffix('/')  # remove trailing '/'
    db_backups = f"{base_path}/db"
    rc_backups = f"{base_path}/crates"
    logger.debug("Backup paths: %r - %r - %r", base_path, db_backups, rc_backups)
    # backup database
    result = backup(db_backups)
    if result.returncode != 0:
        sys.exit(result.returncode)
    # backup crates
    result = backup_crates(config, rc_backups)
    if result != 0:
        sys.exit(result)
    # clean up old files
    retain_days = int(config.get("BACKUP_RETAIN_DAYS", -1))
    logger.debug("RETAIN DAYS: %d", retain_days)
    if retain_days > -1:
        now = time.time()
        for file in Path(db_backups).glob('*'):
            if file.is_file():
                logger.debug("Check st_mtime of file %s: %r < %r",
                             file.absolute(), os.path.getmtime(file), now - int(retain_days) * 86400)
                if os.path.getmtime(file) < now - int(retain_days) * 86400:
                    logger.debug("Removing %s", file.absolute())
                    os.remove(file.absolute())
                    logger.info("File %s removed from remote site", file.absolute())
    # synch with a remote site
    if config.get("BACKUP_REMOTE_PATH", None):
        # check REMOTE_* params
        required_params = ["BACKUP_REMOTE_PATH", "BACKUP_REMOTE_HOST",
                           "BACKUP_REMOTE_USER", "BACKUP_REMOTE_PASSWORD",
                           "BACKUP_REMOTE_ENABLE_TLS"]
        for p in required_params:
            if not config.get(p, None):
                print(f"Missing '{p}' on your settings!")
                print("Required params are: %s", ", ".join(required_params))
                sys.exit(128)
        __remote_synch__(base_path, config.get("BACKUP_REMOTE_PATH"),
                         config.get("BACKUP_REMOTE_HOST"),
                         config.get("BACKUP_REMOTE_USER"), config.get("BACKUP_REMOTE_PASSWORD"),
                         config.get("BACKUP_REMOTE_ENABLE_TLS", False))
    else:
        logger.warning("Remote backup not configured")


# export backup command
commands = [bck]
