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
import sys
import os
import click
from flask import Blueprint

from ..utils import generate_encryption_key as gen_key, encrypt_file, decrypt_file

# set module level logger
logger = logging.getLogger(__name__)

# define the blueprint for DB commands
blueprint = Blueprint('ed', __name__)

# set CLI help
blueprint.cli.help = "Manage files encryption/decryption"


@blueprint.cli.command('generate-encryption-key')
@click.option("-f", "--key-file", type=click.Path(exists=False), default="lifemonitor.key", show_default=True)
def generate_encryption_key(key_file):
    """Generate a new encryption key"""
    try:
        # check if the key file already exists
        if os.path.exists(key_file):
            print("Key file '%s' already exists" % os.path.abspath(key_file))
            sys.exit(1)
        # generate the key
        key = gen_key()
        print("Key generated: %s" % key.decode("utf-8"))
        # save the key
        with open(key_file, "wb") as f:
            f.write(key)
        print("Key saved in '%s'" % os.path.abspath(key_file))
        sys.exit(0)
    except Exception as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        else:
            logger.error(f"Error generating key: {e}")
        sys.exit(1)


@blueprint.cli.command('encrypt')
@click.argument("input_file", metavar="input", type=click.File("rb"))
@click.option("-o", "--out", type=click.File("wb"), default="<FILENAME>.enc", show_default=True, help="Output file")
@click.option("-k", "--key", type=click.File("rb"), default="lifemonitor.key", show_default=True, help="Encryption key")
def encrypt(input_file, out, key):
    """Encrypt a file"""
    try:
        # check if the key file doesn't exist
        if not os.path.exists(key.name):
            print("Key file '%s' does not exist" % os.path.abspath(key.name))
            sys.exit(1)
        # check if the output file already exists
        if os.path.exists(out.name):
            print("Output file '%s' already exists" % os.path.abspath(out.name))
            sys.exit(1)
        # initialize the output file
        if out.name == "<FILENAME>.enc":
            out.name = "%s.enc" % os.path.basename(input_file.name)
        # read the key
        key = key.read()
        # encrypt the file
        encrypt_file(input_file, out, key)
        logger.debug(f"File encrypted: {out.name}")
        print(f"File encrypted: {out.name}")
        sys.exit(0)
    except Exception as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        else:
            logger.error(f"Error encrypting file: {e}")
        sys.exit(1)


@blueprint.cli.command('encrypt-folder')
@click.argument("input_folder", type=click.Path(exists=True))
@click.option("-o", "--output_folder", type=click.Path(exists=False), default="<INPUT_FOLDER>", show_default=True, help="Output file")
@click.option("-k", "--key", type=click.File("rb"), default="lifemonitor.key", show_default=True, help="Encryption key")
def encrypt_folder(input_folder, output_folder, key):

    # check if the key file doesn't exist
    if not os.path.exists(key.name):
        print("Key file '%s' does not exist" % os.path.abspath(key.name))
        sys.exit(1)

    # init the output folder
    if output_folder == "<INPUT_FOLDER>":
        output_folder = input_folder
    logger.debug(f"Using Output folder: {output_folder}")

    # read the key
    key_data = key.read()

    # walk on the input folder
    for root, dirs, files in os.walk(input_folder):
        for file in files:
            input_file = os.path.join(root, file)
            file_output_folder = root.replace(input_folder, output_folder)
            logger.warning(f"File output folder: {file_output_folder}")
            if not os.path.exists(file_output_folder):
                os.makedirs(file_output_folder, exist_ok=True)
                logger.debug(f"Created folder: {file_output_folder}")
            output_file = f"{os.path.join(file_output_folder, file)}.enc"
            logger.debug(f"Encrypting file: {input_file}")
            logger.debug(f"Output file: {output_file}")
            with open(input_file, "rb") as f:
                with open(output_file, "wb") as o:
                    encrypt_file(f, o, key_data)
                    logger.debug(f"File encrypted: {output_file}")
                    print(f"File encrypted: {output_file}")
            logger.debug(f"Removing file: {input_file}")
    print(f"Encryption completed: files on {output_folder}")
    sys.exit(0)


@blueprint.cli.command('decrypt')
@click.argument("input_file", metavar="input", type=click.File("rb"))
@click.option("-o", "--out", type=click.File("wb"), default="<FILENAME>", show_default=True, help="Output file")
@click.option("-k", "--key", type=click.File("rb"), default="lifemonitor.key", show_default=True, help="Encryption key")
def decrypt(input_file, out, key):
    """Decrypt a file"""
    try:
        # check if the key file doesn't exist
        if not os.path.exists(key.name):
            print("Key file '%s' does not exist" % os.path.abspath(key.name))
            sys.exit(1)
        # check if the output file already exists
        if os.path.exists(out.name):
            print("Output file '%s' already exists" % os.path.abspath(out.name))
            sys.exit(1)
        # initialize the output file
        if out.name == "<FILENAME>":
            out.name = "%s" % os.path.basename(input_file.name).removesuffix(".enc")
        # read the key
        key = key.read()
        # decrypt the file
        decrypt_file(input_file, out, key)
        logger.debug(f"File decrypted: {out.name}")
        print(f"File decrypted: {out.name}")
        sys.exit(0)
    except Exception as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(e)
        else:
            logger.error(f"Error decrypting file: {e}")
        sys.exit(1)


@blueprint.cli.command('decrypt-folder')
@click.argument("input_folder", type=click.Path(exists=True))
@click.option("-o", "--output_folder", type=click.Path(exists=False), default="<INPUT_FOLDER>", show_default=True, help="Output file")
@click.option("-k", "--key", type=click.File("rb"), default="lifemonitor.key", show_default=True, help="Encryption key")
def decrypt_folder(input_folder, output_folder, key):

    # check if the key file doesn't exist
    if not os.path.exists(key.name):
        print("Key file '%s' does not exist" % os.path.abspath(key.name))
        sys.exit(1)

    # init the output folder
    if output_folder == "<INPUT_FOLDER>":
        output_folder = input_folder
    logger.debug(f"Using Output folder: {output_folder}")

    # read the key
    key_data = key.read()

    # walk on the input folder
    for root, dirs, files in os.walk(input_folder):
        for file in files:
            input_file = os.path.join(root, file)
            file_output_folder = root.replace(input_folder, output_folder)
            logger.warning(f"File output folder: {file_output_folder}")
            if not os.path.exists(file_output_folder):
                os.makedirs(file_output_folder, exist_ok=True)
                logger.debug(f"Created folder: {file_output_folder}")
            output_file = f"{os.path.join(file_output_folder, file).removesuffix('.enc')}"
            logger.debug(f"Decrypting file: {input_file}")
            logger.debug(f"Output file: {output_file}")
            with open(input_file, "rb") as f:
                with open(output_file, "wb") as o:
                    decrypt_file(f, o, key_data)
                    logger.debug(f"File decrypted: {output_file}")
                    print(f"File decrypted: {output_file}")
            logger.debug(f"Removing file: {input_file}")
    print(f"Decryption completed: files on {output_folder}")
    sys.exit(0)
