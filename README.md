Github: https://github.com/ghee22/qualysguard_asset_sync

Copyright 2013 Parag Baxi

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

Description

The Python 2.7 call syncs QualysGuard's asset groups with a CMDB sourced from a Google Spreadsheet.

    Intelligently creates or updates asset groups with IPs. Also assigns default scanner and assigned scanners based on configurable criteria.
    Creates up to three asset groups per row/site. Use case: asset group to schedule scans during work hours for DHCP, typically workstations.
        Complete site range = "Region - Site"
        Site's specified DHCP column = "Region - Site DHCP"
        Site's specified static column = "Region - Site static"
    Consumes almost any kind of IP address groupingand converts to range IP address grouping in CMDB for easy human reading. Only nmap style is not supported (10.0.0-255.0-255). Example of what is supported:
        Original: "192.168.0.1, 192.168.0.2, 192.168.0.3, 192.168.2.0/24, 192.16.3.0-192.168.3.255"
        Converts to: "192.168.0.1-192.168.0.3, 192.168.2.0/23"
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
      -i INI, --ini INI     Configuration file for login (default =
                            config.ini).
      -k KEY, --key KEY     Google spreadsheet to access.
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
CMDB Google Spreadsheet

Each row is its own site/office. For example, the North American, New York site ("NA - New York" asset group) is on its own row.

Columns (in any order)

    "Region": Region of site. Example: "NA".
    "Office": Office name. Example: "New York".
    "IP Address Assignment": Complete IP range. Example: "10.1.0.0/16"
    "IP Address DHCP": DHCP range of office. Example: "10.1.128.0/17"
    "IP Address static": Optional, static range of office. This is calculated from complete range minus DHCP range. Example: "", or "10.1.0.0-10.1.255.255"

Configuration

config.ini:

; Semicolon (;) disables command.

;

[QualysGuard]

username = QualysGuard API username

password = QualysGuard API password

[Google]

username = cmdb@domain_name.com

password = CMDB Google password

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
