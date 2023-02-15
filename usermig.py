#!/usr/bin/env python3

#  Title       : usermig
#  Creator     : Harsha Baste
#  Created     : 15.02.2023 04:15:00 PM
#  Description : Helps migrate users from a passwordless auth domain to a New Relic auth domain

# Run the script with -h for command line options
"""

This script provides a means to migrate users from New Relic password domain onto the SAML/SSO domain
Assumptions: 
    (a) The new domain has already been created and has no users in it.
    (b) The list of users specified has been pre-vetted and complies with the format required

Disclaimer:
    This Python script is provided "as is" and without any express or implied warranties, 
    including, without limitation, the implied warranties of merchantability and fitness 
    for a particular purpose. The author and contributors of this script will not be liable 
    for any damages, including direct, indirect, incidental, consequential, special, or 
    exemplary damages, arising from the use of this script, even if advised of the possibility 
    of such damages. Use of this script is at your own risk. By using this script, you agree 
    to indemnify and hold harmless the author and contributors from any and all claims,
    damages, and expenses (including reasonable attorney fees) arising from or related to 
    your use of the script. 


"""

__author__ = "Harsh Baste"
__version__ = "0.1.0"
__license__ = "Proprietary"

import argparse
import csv
import logging
import logging.handlers
import os
import sys
from string import Template

import yaml

import nerdgraph

# ----[ Globals ]----

logger = logging.getLogger('usermig')
config = None

# ----[ Supporting Functions ]----


def sample_config(config_file):
    # FIXME: Define a set of options for the script
    contents = Template(
        """\
usermig:
    name: $name
    loglevel: $level
    tsv: filename.tsv
    api_key: NRAK-BlahBlah
    source_domain_id: 
    destination_domain_id: 
    """
    )
    data = contents.substitute(name="UserMig", level="DEBUG")
    try:
        f = open(config_file, "x")
        f.write(data)
        f.close()
        logger.info("Boilerplate configuration created at {}".format(config_file))
    except FileExistsError:
        logger.error("Refusing to over-write an existing file!")
    sys.exit(1)


def read_config(config_file):
    global config
    logger.debug("Reading configuration from {}".format(config_file))
    with open(config_file, "r") as ymlfile:
        root = yaml.load(ymlfile, Loader=yaml.FullLoader)
    config = root["usermig"]


class CustomFormatter(
    argparse.RawDescriptionHelpFormatter, argparse.ArgumentDefaultsHelpFormatter
):
    pass


def parse_args(args=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description=sys.modules[__name__].__doc__, formatter_class=CustomFormatter
    )

    g = parser.add_mutually_exclusive_group()
    g.add_argument(
        "--debug", "-d", action="store_true", default=False, help="enable debugging"
    )
    g.add_argument(
        "--silent", "-s", action="store_true", default=False, help="don't log"
    )
    # FIXME: modify these options
    g = parser.add_argument_group("usermig settings")
    g.add_argument(
        "-c",
        "--config",
        dest="configfile",
        required=False,
        default="ml",
        help="File to read the TSV user list from",
    )

    return parser.parse_args(args)


def setup_logging(options):
    """Configure logging."""
    root = logging.getLogger("")
    root.setLevel(logging.WARNING)
    logger.setLevel(options.debug and logging.DEBUG or logging.INFO)
    if not options.silent:
        if not sys.stderr.isatty():
            facility = logging.handlers.SysLogHandler.LOG_DAEMON
            sh = logging.handlers.SysLogHandler(address="/dev/log", facility=facility)
            sh.setFormatter(
                logging.Formatter(
                    "{0}[{1}]: %(message)s".format(logger.name, os.getpid())
                )
            )
            root.addHandler(sh)
        else:
            ch = logging.StreamHandler()
            ch.setFormatter(
                logging.Formatter(
                    "%(asctime)-17s %(levelname)-7s | %(module)s.%(funcName)s.%(lineno)d | %(message)s",
                    datefmt="%d%m%Y:%H:%M:%S",
                )
            )
            root.addHandler(ch)


def parse_file(tsv_file_name):
    with open(tsv_file_name, "r") as tsvfile:
        reader = csv.DictReader(tsvfile, delimiter="\t")
        data = []
        for row in reader:
            data.append(row)
        return data


# ----[ Application Logic ]----


def main(options):
    logger.info("Starting {} ...".format(config["name"]))
    api_key = config["api_key"]

    tsvname = config["tsv"]
    logger.info("Parsing data from {tsvname}...")

    users = parse_file(tsvname)

    destination_domain_id = config["destination_domain_id"]
    logger.info(
        "Duplicating users in the target auth domain {destination_domain_id}..."
    )

    # To improve execution performance we pull unique groups while looking
    # at each user and create the group if it hasnt been created already
    created_groups = dict()
    for user in users:
        group = user["group_name"]
        if group in created_groups:
            logger.debug("Group {group} was seen before. Not creating ...")
        else:
            logger.info("Creating group {group} ...")
            data = nerdgraph.CreateGroup(destination_domain_id, group).execute(api_key)
            # TODO: Pull out the group id
            id = data["group_id"]
            created_groups[group] = id

        group_id = created_groups[group]
        nerdgraph.CreateUser(
            user["email"], user["name"], user["user_type"], destination_domain_id
        ).execute(api_key)
        nerdgraph.AddUserToGroup(group_id, destination_domain_id).execute(api_key)

    # We now have to tie the roles to the groups
    role_mapping = nerdgraph.RolesQuery().execute(api_key)
    for group in role_mapping.groups:  # TODO: Fix this
        for role in group.roles:  # TODO: Fix this
            nerdgraph.AssignRole(group.id, role.id, role.account_id).execute(api_key)

    logger.info("Done!")


# ----[ Entry Point ]----
if __name__ == "__main__":
    options = parse_args()

    # Config always over-rides the command line
    if options.configfile:
        if os.path.exists(options.configfile):
            read_config(options.configfile)
        else:
            sample_config(options.configfile)

    if "loglevel" in config:
        lvl = config["loglevel"]
        logger.debug("Configuration over-ride for log level: {}".format(lvl))
        logger.setLevel(lvl)
        options.debug = logging.getLevelName(logger.level) == "DEBUG"
        if options.debug:
            options.silent = False
    setup_logging(options)

    try:
        print("\n".join(main(options)))
    except Exception as e:
        logger.exception("%s", e)
        sys.exit(1)
    sys.exit(0)

# ----[ Unit Tests ]----

# FIXME: Write proper unit tests
# import pytest  # noqa: E402
# import shlex  # noqa: E402

# def test_main(args, expected):
#     assert true == expected
