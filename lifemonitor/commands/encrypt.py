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

import base64
import logging
import os
import sys

import click
from flask import Blueprint

from ..utils import (decrypt_file, decrypt_folder, encrypt_file,
                     encrypt_folder, generate_asymmetric_encryption_keys,
                     generate_symmetric_encryption_key, serialization)

# set module level logger
logger = logging.getLogger(__name__)

# define the blueprint for DB commands
blueprint = Blueprint('ed', __name__)

# set CLI help
blueprint.cli.help = "Manage files encryption/decryption"

# define the encryption key options
encryption_asymmetric_option = click.option("-a", "--encryption-asymmetric", is_flag=True, default=False,
                                            help="Use asymmetric encryption", show_default=True)
encryption_key_option = click.option("-k", "--encryption-key", default=None, help="Encryption key")
encryption_key_file_option = click.option("-kf", "--encryption-key-file",
                                          type=click.File("rb"), default="lifemonitor.key",
                                          help="File containing the encryption key")


@blueprint.cli.command('gen-keys')
@click.option("-f", "--key-file", type=click.Path(exists=False), default="lifemonitor.key", show_default=True)
@encryption_asymmetric_option
def generate_encryption_keys_cmd(key_file, encryption_asymmetric):
    """Generate a new pair of encryption keys"""
    try:
        # init reference to the key (symmetric or asymmetric) bytes
        key = None
        # check if the key file already exists
        if os.path.exists(key_file):
            print("Key file '%s' already exists" % os.path.abspath(key_file))
            sys.exit(1)
        if not encryption_asymmetric:
            # generate the key
            key = generate_symmetric_encryption_key()
            print("Key generated: %s" % key.decode("utf-8"))
            # save the key
            with open(key_file, "wb") as f:
                f.write(key)
            print("Key saved in '%s'" % os.path.abspath(key_file))
        else:
            # generate the key pair
            priv, pub = generate_asymmetric_encryption_keys(key_filename=key_file)
            logger.debug(f"Keys saved: private={key_file}, public={key_file + '.pub'}")
            logger.debug(f"Private key: {priv}")
            logger.debug(f"Public key: {pub}")
            print("Keys saved: private=%s, public=%s" % (key_file, key_file + ".pub"))
            # set reference to the public key
            key = pub.public_bytes(encoding=serialization.Encoding.PEM,
                                   format=serialization.PublicFormat.SubjectPublicKeyInfo)
        # generate the kubernetes secret containing the key
        with open(key_file + ".secret.yaml", "w") as f:
            with open(os.path.join("k8s", "backup-key.secret.yaml"), "r") as t:
                # base 64 encode the key
                f.write(t.read().replace("<base64-encoded-encryption-key>",
                                         base64.b64encode(key).decode("utf-8")))
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
@encryption_key_option
@encryption_key_file_option
@encryption_asymmetric_option
def encrypt_cmd(input_file, out, encryption_key, encryption_key_file, encryption_asymmetric):
    """Encrypt a file"""
    try:
        # log the parameters
        logger.debug(f"Input file: {input_file.name}")
        logger.debug(f"Output file: {out.name}")
        logger.debug(f"Encryption key: {encryption_key}")
        logger.debug(f"Encryption key file: {encryption_key_file.name}")

        # # check if the key or key file are not set
        if encryption_key is None and encryption_key_file is None:
            print("ERROR: Key or key file should be set")
            sys.exit(1)
        # check if the output file already exists
        if os.path.exists(out.name):
            print("ERROR: Output file '%s' already exists" % os.path.abspath(out.name))
            sys.exit(1)
        # initialize the output file
        if out.name == "<FILENAME>.enc":
            out.name = "%s.enc" % os.path.abspath(input_file.name)

        # read the encryption key from the file if the key is not provided
        if encryption_key is None:
            encryption_key = encryption_key_file.read()

        # encrypt the file
        encrypt_file(input_file, out, encryption_key, encryption_asymmetric=encryption_asymmetric)
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
@encryption_key_option
@encryption_key_file_option
@encryption_asymmetric_option
def encrypt_folder_cmd(input_folder, output_folder,
                       encryption_key, encryption_key_file, encryption_asymmetric):

    # log the parameters
    logger.debug(f"Input folder: {input_folder}")
    logger.debug(f"Output file: {output_folder}")
    logger.debug(f"Encryption key: {encryption_key}")
    logger.debug(f"Encryption key file: {encryption_key_file.name}")

    # # check if the key or key file are not set
    if encryption_key is None and encryption_key_file is None:
        print("ERROR: Key or key file should be set")
        sys.exit(1)

    # init the output folder
    if output_folder == "<INPUT_FOLDER>":
        output_folder = input_folder
    logger.debug(f"Using Output folder: {output_folder}")

    # read the encryption key from the file if the key is not provided
    if encryption_key is None:
        encryption_key = encryption_key_file.read()

    # encrypt the folder
    encrypted_files = encrypt_folder(input_folder, output_folder, encryption_key, encryption_asymmetric=encryption_asymmetric)
    print(f"Encryption completed: {encrypted_files} files encrypted on {output_folder}")
    sys.exit(0)


@blueprint.cli.command('decrypt')
@click.argument("input_file", metavar="input", type=click.File("rb"))
@click.option("-o", "--out", type=click.File("wb"), default="<FILENAME>", show_default=True, help="Output file")
@encryption_key_option
@encryption_key_file_option
@encryption_asymmetric_option
def decrypt_cmd(input_file, out, encryption_key, encryption_key_file, encryption_asymmetric):
    """Decrypt a file"""
    try:
        # log the parameters
        logger.debug(f"Input file: {input_file.name}")
        logger.debug(f"Output file: {out.name}")
        logger.debug(f"Encryption key: {encryption_key}")
        logger.debug(f"Encryption key file: {encryption_key_file.name}")

        # check if the key or key file are not set
        if encryption_key is None and encryption_key_file is None:
            print("ERROR: Key or key file should be set")
            sys.exit(1)

        # check if the output file already exists
        if os.path.exists(out.name):
            print("Output file '%s' already exists" % os.path.abspath(out.name))
            sys.exit(1)
        # initialize the output file
        if out.name == "<FILENAME>":
            out.name = "%s" % os.path.abspath(input_file.name).removesuffix(".enc")
        # read the encryption key from the file if the key is not provided
        if encryption_key is None:
            encryption_key = encryption_key_file.read()
        # decrypt the file
        decrypt_file(input_file, out, encryption_key, encryption_asymmetric=encryption_asymmetric)
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
@encryption_key_option
@encryption_key_file_option
@encryption_asymmetric_option
def decrypt_folder_cmd(input_folder, output_folder,
                       encryption_key, encryption_key_file, encryption_asymmetric):

    # log the parameters
    logger.debug(f"Input folder: {input_folder}")
    logger.debug(f"Output file: {output_folder}")
    logger.debug(f"Encryption key: {encryption_key}")
    logger.debug(f"Encryption key file: {encryption_key_file.name}")

    # check if the key or key file are not set
    if encryption_key is None and encryption_key_file is None:
        print("ERROR: Key or key file should be set")
        sys.exit(1)

    # init the output folder
    if output_folder == "<INPUT_FOLDER>":
        output_folder = input_folder
    logger.debug(f"Using Output folder: {output_folder}")

    # read the encryption key from the file if the key is not provided
    if encryption_key is None:
        encryption_key = encryption_key_file.read()

    # decrypt the folder
    decrypted_files = decrypt_folder(input_folder, output_folder,
                                     encryption_key, asymmetric_encryption=encryption_asymmetric)
    print(f"Decryption completed: {decrypted_files} files decrypted on {output_folder}")
    sys.exit(0)
