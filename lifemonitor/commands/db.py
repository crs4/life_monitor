# Copyright (c) 2020-2022 CRS4
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
from datetime import datetime

import click
from flask import current_app
from flask.cli import with_appcontext
from flask_migrate import cli, current, stamp, upgrade
from lifemonitor.auth.models import User
from lifemonitor.utils import encrypt_file, decrypt_file, hide_secret

# set module level logger
logger = logging.getLogger()

# export from this module
commands = [cli.db]

# update help for the DB command
cli.db.help = "Manage database"

# set initial revision number
initial_revision = '8b2e530dc029'


@cli.db.command()
@click.option("-r", "--revision", default="head")
@with_appcontext
def init(revision):
    """
    Initialize app database
    """
    from lifemonitor.db import create_db, db, db_initialized, db_revision

    is_initialized = db_initialized()
    logger.info("LifeMonitor app initialized: %r", is_initialized)
    if is_initialized:
        current_revision = db_revision()
        if not current_revision:
            # if DB is initialized with no revision
            # set the initial revision and then apply migrations
            stamp(revision=initial_revision)
            logger.info(f"Set initial revision: {initial_revision}")
        # Apply migrations
        logger.info(f"Applying migrations up to revision '{revision}'...")
        upgrade(revision=revision)
        logger.info("Migrations applied!")
        logger.info("Current revision: %r", db_revision())
    else:
        logger.debug("Initializing DB...")
        create_db(settings=current_app.config)
        db.create_all()
        stamp()
        current()
        logger.info("DB initialized")
        # create a default admin user if not exists
        admin = User.find_by_username('admin')
        if not admin:
            admin = User('admin')
            admin.password = current_app.config["LIFEMONITOR_ADMIN_PASSWORD"]
            db.session.add(admin)
            db.session.commit()


@cli.db.command()
@with_appcontext
def wait_for_db():
    """
    Wait until that DBMS service is up and running
    """
    from lifemonitor.db import db_initialized, db_revision

    is_initialized = False
    while not is_initialized:
        is_initialized = db_initialized()
    logger.info("DB initialized")

    current_revision = None
    while current_revision is None:
        current_revision = db_revision()
    logger.info(f"Current revision: {current_revision}")


# define common options
verbose_option = click.option("-v", "--verbose", default=False, is_flag=True, help="Enable verbose mode")
encryption_key_option = click.option("-k", "--encryption-key", default=None, help="Encryption key")
encryption_key_file_option = click.option("-kf", "--encryption-key-file",
                                          type=click.File("rb"),
                                          default=None, help="File containing the encryption key")


def backup_options(func):
    # backup command options (evaluated in reverse order!)
    func = verbose_option(func)
    func = encryption_key_file_option(func)
    func = encryption_key_option(func)
    func = click.option("-f", "--file", default=None, help="Backup filename (default 'hhmmss_yyyymmdd.tar')")(func)
    func = click.option("-d", "--directory", default="./", help="Directory path for the backup file (default '.')")(func)
    return func


@cli.db.command("backup")
@backup_options
@with_appcontext
def backup_cmd(directory, file, encryption_key, encryption_key_file, verbose):
    """
    Make a backup of the current app database
    """
    logger.debug("%r - %r - %r - %r - %r", file, directory, encryption_key, encryption_key_file, verbose)
    result = backup(directory, file, encryption_key, encryption_key_file, verbose)
    # report exit code to the main process
    sys.exit(result.returncode)


def backup(directory, file=None,
           encryption_key=None, encryption_key_file=None,
           verbose=False) -> subprocess.CompletedProcess:
    """
    Make a backup of the current app database
    """
    logger.debug("%r - %r - %r - %r - %r", file, directory, encryption_key, encryption_key_file, verbose)
    from lifemonitor.db import db_connection_params
    params = db_connection_params()
    if not file:
        file = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.tar"
    os.makedirs(directory, exist_ok=True)
    target_path = os.path.join(directory, file)
    cmd = f"PGPASSWORD={params['password']} pg_dump -h {params['host']} -U {params['user']} -F t {params['dbname']} > {target_path}"
    if verbose:
        print("Output file: %s" % target_path)
        print("Backup command: %s" % hide_secret(cmd, params['password']))
    result = subprocess.run(cmd, shell=True, capture_output=True)
    logger.debug("Backup result: %r", hide_secret(result, params['password']))
    if result.returncode == 0:
        msg = f"Created backup of database {params['dbname']} @ {target_path}"
        logger.debug(msg)
        print(msg)
        if encryption_key is not None or encryption_key_file is not None:
            msg = f"Encrypting backup file {target_path}..."
            logger.debug(msg)
            print(msg)

            # read the encryption key from the file if the key is not provided
            if encryption_key is None:
                encryption_key = encryption_key_file.read()

            # encrypt the backup file using the encryption key with the Fernet algorithm
            try:
                with open(target_path, "rb") as input_file:
                    with open(target_path + ".enc", "wb") as output_file:
                        encrypt_file(input_file, output_file, encryption_key, raise_error=True)
                # remove the original backup file
                os.remove(target_path)
                msg = f"Backup file {target_path} encrypted"
                logger.debug(msg)
                print(msg)
            except Exception as e:
                print("Unable to encrypt backup file '%s'. ERROR: %s" % (target_path, str(e)))
                sys.exit(1)
    else:
        click.echo("\nERROR Unable to backup the database: %s" % result.stderr.decode())
        if verbose and result.stderr:
            print("ERROR [stderr]: %s" % result.stderr.decode())
    return result


@cli.db.command()
@click.argument("file")
@click.option("-s", "--safe", default=False, is_flag=True,
              help="Preserve the current database renaming it as '<dbname>_yyyymmdd_hhmmss'")
@encryption_key_option
@encryption_key_file_option
@verbose_option
@with_appcontext
def restore(file, safe, encryption_key, encryption_key_file, verbose):
    """
    Restore a backup of the app database
    """
    from lifemonitor.db import (create_db, db_connection_params, db_exists,
                                drop_db, rename_db)

    # initialize the encrypted file reference
    encrypted_file = None

    # check if DB file exists
    if not os.path.isfile(file):
        print("File '%s' not found!" % file)
        sys.exit(128)

    try:

        # check if the DB backup is encrypted and the key or key file is provided
        if file.endswith(".enc"):
            if encryption_key is None and encryption_key_file is None:
                print("The backup file '%s' is encrypted but no encryption key is provided!" % file)
                sys.exit(128)

            # read the encryption key from the file if the key is not provided
            if encryption_key is None:
                encryption_key = encryption_key_file.read()

            # Set the reference to the encrypted file
            encrypted_file = file

            # decrypt the backup file using the encryption key with the Fernet algorithm
            file = file.removesuffix(".enc")
            with open(encrypted_file, "rb") as input_file:
                with open(file, "wb") as output_file:
                    decrypt_file(input_file, output_file, encryption_key)
            logger.debug("Decrypted backup file '%s' to '%s'", encrypted_file, file)

        # check if delete or preserve the current app database (if exists)
        new_db_name = None
        params = db_connection_params()
        db_copied = False
        if db_exists(params['dbname']):
            if safe:
                answer = input(f"The database '{params['dbname']}' will be renamed. Continue? (y/n): ")
                if not answer.lower() in ('y', 'yes'):
                    sys.exit(0)
            else:
                answer = input(f"The database '{params['dbname']}' will be delete. Continue? (y/n): ")
                if not answer.lower() in ('y', 'yes'):
                    sys.exit(0)
            # create a snapshot of the current database
            new_db_name = f"{params['dbname']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            rename_db(params['dbname'], new_db_name)
            db_copied = True
            msg = f"Created a DB snapshot: data '{params['dbname']}' temporarily renamed as '{new_db_name}'"
            logger.debug(msg)
            if verbose:
                print(msg)
        # restore database
        create_db(current_app.config)
        cmd = f"PGPASSWORD={params['password']} pg_restore -h {params['host']} -U {params['user']} -d {params['dbname']} -v {file}"
        if verbose:
            print("Dabaset file: %s" % file)
            print("Backup command: %s" % hide_secret(cmd, params['password']))
        result = subprocess.run(cmd, shell=True)
        logger.debug("Restore result: %r", hide_secret(cmd, params['password']))
        if result.returncode == 0:
            if db_copied and safe:
                print(f"Existing database '{params['dbname']}' renamed as '{new_db_name}'")
            msg = f"Backup {file} restored to database '{params['dbname']}'"
            logger.debug(msg)
            print(msg)
            # if mode is set to 'not safe'
            # delete the temp snapshot of the current database
            if not safe:
                drop_db(db_name=new_db_name)
                msg = f"Current database '{params['dbname']}' deleted"
                logger.debug(msg)
                if verbose:
                    print(msg)
        else:
            # if any error occurs
            # restore the previous latest version of the DB
            # previously saved as temp snapshot
            if new_db_name:
                # delete the db just created
                drop_db()
                # restore the old database snapshot
                rename_db(new_db_name, params['dbname'])
                db_copied = True
                msg = f"Database restored '{params['dbname']}' renamed as '{new_db_name}'"
                logger.debug(msg)
                if verbose:
                    print(msg)
            print("ERROR: Unable to restore the database backup")
            if verbose and result.stderr:
                print("ERROR [stderr]: %s" % result.stderr.decode())
    finally:
        if encrypted_file and os.path.isfile(file):
            # remove the decrypted file
            os.remove(file)
            logger.debug("Removed decrypted backup file '%s'", file)

    # report exit code to the main process
    sys.exit(result.returncode)


@cli.db.command()
@click.argument("snapshot", default="current")
@with_appcontext
def drop(snapshot):
    """
    Drop (a snapshot of) the app database.

    A snapshot is specified by a datetime formatted as yyyymmdd_hhmmss: e.g., 20220324_100137.

    If no snaphot is provided the current app database will be removed.
    """
    from lifemonitor.db import db_connection_params, drop_db
    db_name = db_connection_params()['dbname']
    if snapshot and snapshot != "current":
        if not snapshot.startswith(db_name):
            db_name = f"{db_name}_{snapshot}"
        else:
            db_name = snapshot
    answer = input(f"The database '{db_name}' will be removed. Are you sure? (y/n): ")
    if answer.lower() in ('y', 'yes'):
        drop_db(db_name=db_name)
        print(f"Database '{db_name}' removed")
    else:
        print("Database deletion aborted")
