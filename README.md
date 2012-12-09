qg_asset_sync
=============

QualysGuard Asset Sync

Note: This is not supported by Qualys, it is community built. Thanks to Qnimbus for the solution below.
Download

Github: https://github.com/ghee22/qualysguard_asset_sync
Description

The Python 2.7 call syncs QualysGuard's asset groups with a CMDB sourced from a Google Spreadsheet.

    Intelligently creates or updates asset groups with IPs. Also assigns default scanner and assigned scanners based on configurable criteria.
    Consumes almost any kind of IP address groupingand converts to range IP address grouping in CMDB for easy human reading. Only nmap style is not supported (10.0.0-255.0-255).
    Intelligently deletes asset groups that no longer exist in CMDB.
    Also creates a buckets.csv file to sync CMDB to sync to IBM QRadar's "buckets".

Note: This can easily be modified to support CSV files.

Usage

$ python sync_qg_asset_groups.py -h
Logged into Google Docs...

usage: sync_qg_asset_groups.py [-h] [-a ASSET_GROUP] [-b] [-c] [-d]

                               [--check_cmdb] [-f] [-g] [-i INI] [-k KEY] [-o]

                               [-p] [-r] [-s] [--skip_calc_static]

                               [--skip_qg_update] [--test]

Sync CMDB from Google Spreadsheet to QualysGuard.

optional arguments:

  -h, --help            show this help message and exit

  -a ASSET_GROUP, --asset_group ASSET_GROUP

                        Asset group(s) -- office -- to sync. If not specified,

                        sync all offices.

  -b, --debug           Outputs additional information to log.

  -c, --static_ip       Calculates and syncs only static IP range.

  -d, --dhcp_ip         Syncs DHCP range.

  --check_cmdb          Check CMDB's office listings against Google Doc's

                        offices.

  -f, --print_offices   Print all offices.

  -g, --glob            Convert IP ranges in Google Docs to glob format

                        ('10.0.0.0, 10.0.0.1, 10.0.0.2' -->

                        '10.0.0.0-10.0.0.2').

  -i INI, --ini INI     Configuration file for login & JIRA issues (default =

                        config.ini).

  -k KEY, --key KEY     Google spreadsheet to access. If not specified, access

                        rm2 office tracker.

  -o, --office_ip       Syncs office IP range.

  -p, --print_asset_groups

                        Print all QualysGuard asset groups.

  -r, --qradar          Sync QRadar buckets, create tab-delimited CSV file

                        from Google Spreadsheet.

  -s, --sync            Sync all IP ranges (office, DHCP, and static).

  --skip_calc_static    Skip calculating static range.

  --skip_qg_update      Skip updating QualysGuard asset groups.

  --test                Test.

Requirements
Source

    Python 2.7
    lxml
    python-qualysconnect
    netaddr
    gdata (for Google Spreadsheet connection)

It's fairly simple to install these packages using pip.
How to install libraries

Install pip:

$ curl https://raw.github.com/pypa/pip/master/contrib/get-pip.py | sudo python

Install libraries:

$ sudo pip install lxml

License

GPL v3

Thank you to Chris Hulan (chris.hulan@gmail.com) for alphanum.