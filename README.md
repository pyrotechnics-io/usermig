
# New Relic AD User Migration

This script allows you to migrate users from one authentication domain to another on New Relic.



## Installation

Checkout this repo and setup the dependencies for the python script

Run this inside your checkout directory

```bash
  python -m venv .venv
  .venv/bin/activate
  pip install -r requirements.txt
```

Confirm if the script runs ok with this:

```bash
chmod +x usermig.py
./usermig.py -h
```

## Usage

This script requires a configuration file to run. In the absense of one, it will create one for you

```bash
./usermig.py -c config.yml
```

Open the configuration file and enter in correct values for the fields inside

The filename.tsv file referenced in the configuration needs to be copied to the same directory as this script and must have the following fields

```
Name
Email
User type
Groups
```
> Exporting from the NR One frontend should give you these fields.

With the configuration and input file in place run the same command again:

```bash
./usermig.py -c config.yml
```

This should create users into the destination domain with their corresponding groups copied over.

If you need to run the script to just validate the input TSV, run it in dry run mode like so:

```bash
./usermig.py -c config.yml --dryrun
```

## Note

This script will only migrate users and does not attempt to move the assets (dashboards, keys, etc) tied to the user.
