#!/usr/bin/env python3

#  Title       : usermig
#  Creator     : Harsha Baste
#  Created     : 15.02.2023 04:15:00 PM
#  Description : Helps migrate users from a passwordless auth domain to a New Relic auth domain

# Run the script with -h for command line options
"""

This script provides a means to migrate users from New Relic password domain onto the SAML/SSO domain
Assumptions: 
    (a) The new domain has already been created and has no users in it (for AD migration only)
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
__license__ = "MIT"

from string import Template
import argparse
import csv
import logging
import logging.handlers
import os
import sys
import yaml
from tqdm import tqdm
import time
import re
import nerdgraph

# ----[ Globals ]----

logger = logging.getLogger('usermig')
config = None

# ----[ Supporting Functions ]----

def sample_config(config_file):
    # FIXME: Define a set of options for the script
    contents = Template("""\
usermig:
    name: $name
    loglevel: $level
    tsv: filename.tsv
    api_key: NRAK-BlahBlah
    source_domain_id: 
    destination_domain_id: 
    """)
    data = contents.substitute(name="UserMig", level="INFO")
    try:
        f = open(config_file, "x")
        f.write(data)
        f.close()
        logger.info(
            "Boilerplate configuration created at {}".format(config_file))
    except FileExistsError:
        logger.error("Refusing to over-write an existing file!")
    sys.exit(1)


def read_config(config_file):
    global config
    logger.debug("Reading configuration from {}".format(config_file))
    with open(config_file, "r") as ymlfile:
        root = yaml.load(ymlfile, Loader=yaml.FullLoader)
    config = root["usermig"]


class CustomFormatter(argparse.RawDescriptionHelpFormatter, argparse.ArgumentDefaultsHelpFormatter):
    pass

class LogFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(asctime)-17s | %(levelname)-7s | %(module)s.%(funcName)-12s | %(lineno)-4d | %(message)s"
    datefmt="%d%m%Y:%H:%M:%S"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

def parse_args(args=sys.argv[1:]):
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__,
                                     formatter_class=CustomFormatter)

    g = parser.add_mutually_exclusive_group()
    g.add_argument("--debug",
                   "-d",
                   action="store_true",
                   default=False,
                   help="enable debugging")
    g.add_argument("--silent",
                   "-s",
                   action="store_true",
                   default=False,
                   help="don't log")
    g.add_argument("--dump-users",
                   "-u",
                   action="store_true",
                   default=False,
                   help="Dump users in the format the script expects")
    g.add_argument("--just-add-to-group",
                   "-j",
                   action="store_true",
                   default=False,
                   help="Just add users to the tsv specified group")
    g.add_argument("--dryrun",
                   "-r",
                   action="store_true",
                   default=False,
                   help="just parse and validates the tsv file")
    g = parser.add_argument_group("usermig settings")
    g.add_argument(
        "-c",
        "--config",
        dest="configfile",
        required=False,
        default="config.yml",
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
            sh = logging.handlers.SysLogHandler(address="/dev/log",
                                                facility=facility)
            sh.setFormatter(
                logging.Formatter("{0}[{1}]: %(message)s".format(
                    logger.name, os.getpid())))
            root.addHandler(sh)
        else:
            ch = logging.StreamHandler()
            ch.setFormatter(LogFormatter())
            root.addHandler(ch)


# ----[ Application ]----

regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'

def validate_row(idx, row):
    if row.keys() >= {"Name", "Email", "User type", "Groups"}:
        if re.fullmatch(regex, row["Email"]):
            if row["User type"].upper() in ["BASIC_USER_TIER", "CORE_USER_TIER", "FULL_USER_TIER", "BASIC", "CORE", "FULL PLATFORM"]:
                if row["Name"] and row["Groups"]:
                    # All checks passed
                    return None
                else:
                    return "Name or Groups is empty"
            else:
                return "User type is invalid"
        else:
            return "Email address is invalid"
    else:
        return "File does not have the correct header fields"
    return "Unknown error"

def parse_file(tsv_file_name):
    with open(tsv_file_name, "r") as tsvfile:
        reader = csv.DictReader(tsvfile, delimiter="\t")
        data = []
        for row in reader:
            error = validate_row(reader.line_num, row)
            if error is None:
                data.append(row)
            else:
                logger.warning("Ignored line: {}. Reason: {}".format(reader.line_num, error))
        return data

# finish the dump_users function here as called in main. Confirm if the user exists, 
# and then proceed to dump the users in the format this script expects for the tsv file
def dump_users(options, api_key, source_domain_id):
    logger.info("Dumping users in the format the script expects for the tsv file")
    userinfo = (nerdgraph.UsersQuery(source_domain_id)).execute(api_key, not options.dryrun)
    # Make sure the output is API friendly
    normalizer = {
        "BASIC": "BASIC_USER_TIER",
        "CORE": "CORE_USER_TIER",
        "FULL PLATFORM": "FULL_USER_TIER"
    } 
    print("Name\tEmail\tUser type\tGroups")
    for user in userinfo['data']['actor']['organization']['userManagement']['authenticationDomains']['authenticationDomains'][0]['users']['users']:
        print("\t".join([user['name'], user['email'],  normalizer[user['type']['displayName'].upper()], ",".join([group['displayName'] for group in user['groups']['groups']])]))

def main(options):
    logger.info("Starting {} ...".format(config["name"]))
    api_key = config["api_key"]
    destination_domain_id = config["destination_domain_id"]
    source_domain_id = config["source_domain_id"]
    
    if options.dump_users:
        dump_users(options, api_key, source_domain_id)
        sys.exit(0)
       
    tsvname = config["tsv"]
    logger.info("Parsing data from {}...".format(tsvname))
    users = parse_file(tsvname)
    
    if len(users) == 0:
        logger.error("No users found in the tsv file")
        sys.exit(1)
    else:
        logger.info("Found {} rows in the tsv file".format(len(users)))

    if options.dryrun:
        logger.info("Running in dryrun mode. Exiting after validating input")
        sys.exit(0)
    else:
        logger.warning("This run will commit changes")
        countdown = 10
        for i in tqdm(range(countdown), ncols=50, smoothing=50, desc="Confirming in {} seconds".format(countdown), bar_format='{l_bar} {bar}'):
            time.sleep(1) # sleep for 1 second

    if options.just_add_to_group:
        add_to_group(options, api_key, users, source_domain_id)
        sys.exit(0)
        
    migrate_domains(options, api_key, destination_domain_id, source_domain_id, users)
    logger.info("Done!")

def migrate_domains(options, api_key, destination_domain_id, source_domain_id, users):
    logger.info("Duplicating users in the target auth domain [{}]...".format(destination_domain_id))
    for user in users:
        logger.debug(user)

    # To improve execution performance we pull unique groups while looking
    # at each user and create the group if it hasnt been created already
    created_groups = dict()
    for user in users:
        logger.debug("Adding user {}".format(user["Email"]))
        userinfo = (nerdgraph.CreateUser(user["Email"], user["Name"], user["User type"].upper(),
                            destination_domain_id)).execute(api_key, not options.dryrun)
        user_id = userinfo['data']['userManagementCreateUser']['createdUser']['id']
        groups = user["Groups"].split(",")

        for group in groups:
            if group in created_groups:
                logger.debug("Group {} was seen before. Not creating ...".format(group))
            else:
                data = (nerdgraph.CreateGroup(destination_domain_id,
                                            group)).execute(api_key, not options.dryrun)
                id = data['data']['userManagementCreateGroup']['group']['id']
                logger.info("Created group {} with id {} ...".format(group, id))
                created_groups[group] = id

            group_id = created_groups[group]
            (nerdgraph.AddUserToGroup(group_id, user_id)).execute(api_key, not options.dryrun)

    # We now have to tie the roles to the groups
    role_mapping = (nerdgraph.RolesQuery(source_domain_id)).execute(api_key, not options.dryrun)
    groups = role_mapping['data']['actor']['organization']['authorizationManagement']['authenticationDomains']['authenticationDomains'][0]['groups']['groups']
    for group in groups:
        # See if this group belongs to something we created
        if group['displayName'] in created_groups:
            group_id = created_groups[group['displayName']]
            for role in group['roles']['roles']:
                role_id = role['roleId']
                account_id = role['accountId']
                logger.debug("Assigning {} ({}) Role {} AccountId {}".format(group['displayName'], group_id, role_id, account_id))
                nerdgraph.AssignRole(group_id, account_id,
                                    role_id).execute(api_key, not options.dryrun)

def add_to_group(options, api_key, users, source_domain_id):
    logger.info("Running in just add to group mode")
    all_groups_under_ad = (nerdgraph.GroupsQuery(source_domain_id)).execute(api_key, not options.dryrun)
    for user in users:
        groups = [group.strip() for group in user["Groups"].split(",")]
        userinfo = (nerdgraph.UsersQuery(source_domain_id)).execute(api_key, not options.dryrun)
        user_id = None
        
        # Locate the user and his existing groups
        for userobj in userinfo['data']['actor']['organization']['userManagement']['authenticationDomains']['authenticationDomains'][0]['users']['users']:
            if userobj['email'] == user["Email"]:
                logger.debug("Found user {}".format(user["Email"]))
                user_id = userobj['id']
                for group in userobj['groups']['groups']:
                    existing_group_name = group['displayName']
                    if existing_group_name in groups:
                        groups.remove(existing_group_name)
                break
        else:
            logger.error("User {} not found".format(user["Email"]))
            return
        
        if len(groups) == 0:
            logger.info("User {} is already a member of all the groups specified".format(user["Email"]))
            continue
        else:
            logger.info("Adding user {} to the following groups: {}".format(user["Email"], groups))
        
        # Make sure the groups already exist and/or create them where needed
        for group in groups:
            logger.debug("Looking for group {}".format(group))
            group_id = None
                # iterate through all_groups_under_ad and check if group exists
            for ad_group in all_groups_under_ad['data']['actor']['organization']['userManagement']['authenticationDomains']['authenticationDomains'][0]['groups']['groups']:
                if ad_group['displayName'] == group:
                    logger.debug("Found group {} with id {}".format(group, ad_group['id']))
                    group_id = ad_group['id']
                    break
            else:
                logger.debug("Group {} not found. Creating ...".format(group))
                data = (nerdgraph.CreateGroup(source_domain_id,
                                                group)).execute(api_key, not options.dryrun)
                id = data['data']['userManagementCreateGroup']['group']['id']
                logger.info("Created group {} with id {} ...".format(group, id))
                group_id = id
            (nerdgraph.AddUserToGroup(group_id, user_id)).execute(api_key, not options.dryrun)


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
        main(options)
    except KeyboardInterrupt:
        logger.info("Manually interrupted execution")
        sys.exit(255)
    except Exception as e:
        logger.exception("%s", e)
        sys.exit(2)
    sys.exit(0)
