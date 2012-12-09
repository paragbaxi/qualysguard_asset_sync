try:
  from xml.etree import ElementTree
except ImportError:
  from elementtree import ElementTree
import gdata.spreadsheet.service
import gdata.service
import atom.service
import gdata.spreadsheet
import atom
# My imports
import alphanum
import argparse
import ConfigParser
import csv
import datetime
import logging
import netaddr
import os
import qgir_tools
import re
import string
import subprocess
import unicodedata
from lxml import objectify
from collections import defaultdict
from collections import OrderedDict
from itertools import izip_longest
from operator import itemgetter
from qualysconnect.util import build_v1_connector, build_v2_session

def PrintFeed(feed):
  for i, entry in enumerate(feed.entry):
    if isinstance(feed, gdata.spreadsheet.SpreadsheetsCellsFeed):
      print '%s %s\n' % (entry.title.text, entry.content.text)
    elif isinstance(feed, gdata.spreadsheet.SpreadsheetsListFeed):
      print '%s %s %s' % (i, entry.title.text, entry.content.text)
      # Print this row's value for each column (the custom dictionary is
      # built from the gsx: elements in the entry.) See the description of
      # gsx elements in the protocol guide.
      print 'Contents:'
      for key in entry.custom:
        print '  %s: %s' % (key, entry.custom[key].text)
      print '\n',
    else:
      print '%s %s\n' % (i, entry.title.text)

def ListGetAction(gd_client, key, wksht_id):
  # Get the list feed
  feed = gd_client.GetListFeed(key, wksht_id)
  return feed


def gdocs_print_offices(feed):
    """Print offices from Google Docs to screen."""
    # Go row by row of Google spreadsheet.
    for i, entry in enumerate(feed.entry):
        try:
            region = entry.custom['region'].text
            office = '%s - %s' % (region, entry.custom['office'].text)
            print office
        except AttributeError:
            None
    return True


def check_cmdb(feed):
    """Check what offices in CMDB are not in QualysGuard."""
    # Pull from CMDB here.
    cmdb_list = ['Site1', 'Site2']
    city_list = []
    not_found_list = []
    # Go row by row of Google spreadsheet.
    for i, entry in enumerate(feed.entry):
        try:
            city = entry.custom['office'].text
            if city not in cmdb_list:
                not_found_list.append(city)
            else:
                cmdb_list.remove(city)
                city_list.append(city)
        except AttributeError:
            None
    # Sort each list.
    not_found_list.sort()
    cmdb_list.sort()
    city_list.sort()
    print "{0:30s}\t\t{1:30s}".format('Following offices not found:', 'Remaining options from CMDB:')
    for a, b in izip_longest(not_found_list, cmdb_list, fillvalue = ''):
        print "{0:30s}\t\t{1:30s}".format(a, b)
    print '\nAsset groups from Google Docs found:'
    for l in city_list:
        print l
    return True


def ip_range_to_glob(ip_ranges):
    """Convert string ip_ranges to a string of ip ranges in glob format.
       
       Example:
       >>> ip_range_to_glob('10.0.0.0/24, 10.0.1.0/24')
       '10.0.0.0/23'
       >>> ip_range_to_glob('10.108.0.0/16')
       '10.108.0.0/16'       
       
       """
    # Check if already in glob format.
    logging.debug('ip_range_to_glob(%s)' % (ip_ranges))
#    globs = ip_ranges.split(', ')
#    logging.debug('globs = %s' % (globs))
#    new_ip_ranges = ''
#    for g in globs:
#        try:
#            if netaddr.valid_glob(g):
#                logging.debug('In glob format.')
#                # Convert to range: '192.168.0-2.*' --> '192.168.0.0-192.168.2.255'.
#                new_ip_ranges += '%s, ' % (str(netaddr.glob_to_iprange(g)))
#            else:
#                logging.debug('Not a glob.')
#                # Not a glob.
#                new_ip_ranges += '%s, ' % (g)
#        except ValueError, e:
#            # Not a glob.
#            new_ip_ranges += '%s, ' % (g)
#    ip_ranges = new_ip_ranges[:-2]
    logging.debug('ip_ranges = %s' % (ip_ranges))
    # Convert possible ranges to CIDR.
    ip_ranges = ip_range_to_cidr(ip_ranges)
    logging.debug('ip_range_to_cidr(ip_ranges) = %s' % (ip_ranges))
    # Expand range to individual IP addresses.
    ip_ranges = ip_range_expand(ip_ranges)
    # Merge IP addresses to range tuples format -- [(start, finish),...].
    ip_ranges = merge_ip_list(ip_ranges)
    logging.debug('merge_ip_list(ip_ranges) = %s' % (ip_ranges))
    ip_ranges_glob = ''
    for r in ip_ranges:
        if r[0] == r[1]:
            # Range is just one IP address.
            ip_ranges_glob += '%s, ' % (r[0])
        else:
            ip_ranges_glob += '%s-%s, ' % (r[0], r[1])
#        # Convert to glob format
#        s = netaddr.iprange_to_globs(r[0], r[1])
#        for j in s:
#            ip_ranges_glob += '%s, ' % (j)
    # Remove suffix ', '.
    ip_ranges_glob = ip_ranges_glob[:-2]
    return ip_ranges_glob


def glob_to_ip_range(globs):
    """Convert string of globs to a string of ip ranges in CIDR format.
       
       Example:
       >>> glob_to_ip_range('10.0.0.0/23')
       '10.0.0.0/24, 10.0.1.0/24'
       >>> glob_to_ip_range('10.108.0.0/16')
       '10.108.0.0/16'       
       
       """
    globs = globs.split(', ')
    ip_ranges = ''
    for i in globs:
        logging.debug('i = %s' % (i))
        try:
            i = netaddr.glob_to_cidrs(i)
            for j in i:
                ip_ranges += '%s, ' % (str(j))
        except ValueError, e:
            # Not a glob.
            logging.debug('ValueError: %s' % (e))
            ip_ranges += '%s, ' % (i)
        except netaddr.core.AddrFormatError, e:
            logging.debug(e)
            i = ip_range_to_cidr(i)
            for j in i:
                ip_ranges += '%s, ' % (str(j))
    ip_ranges = ip_ranges[:-2]
    logging.debug('ip_ranges = %s' % (ip_ranges))
    return ip_ranges


def gdocs_column_headers(feed):
    gdocs_headers = defaultdict(str)
    for i, entry in enumerate(feed.entry):
        cell = ''.join(entry.content.text.replace('%', '').lower().split())
        cell_id = entry.title.text
        cell_column = cell_id[:qgir_tools.index_of_first_digit(cell_id)]
        if not cell_id[qgir_tools.index_of_first_digit(cell_id)] == '1':
            break
        # print '%s %s\n' % (cell_id, ''.join(cell.lower().split()))
        gdocs_headers[cell] = gdocs_column_to_number(cell_column)
    return gdocs_headers


def gdocs_column_to_number(c):
    """Return number corresponding to excel-style column."""
    number = -25
    for l in c:
        if not l in string.ascii_letters:
            return False
        number += ord(l.upper()) - 64 + 25
    return number


def CellsGetAction(gd_client, key, wksht_id):
  # Get the feed of cells
  feed = gd_client.GetCellsFeed(key, wksht_id)
  return feed


def test(feed):
    """Test."""
    asset_group = ''#'AP - Bangalore'
    # Go row by row of Google spreadsheet.
    for i, entry in enumerate(feed.entry):
        try:
            region = entry.custom['region'].text
            office = '%s - %s' % (region, entry.custom['office'].text)
            if not office == asset_group:
                office_ip_range = entry.custom['ipaddressassignment'].text
                if (office_ip_range.startswith('N/A') or office_ip_range == ''):
                    continue
                #param = {'project': '%sSEC' % (region), 'assignee': entry.custom['itdirectore-mail'].text, 'Impacted Location': entry.custom['cmdbimpactedlocation'].text, 'qg_asset_group_id': 547072, }
                print office
                print office_ip_range
                print
            # Not the office we're looking for.
            continue
        except AttributeError:
            pass
    return True


def int2dot(intip):
    return '.'.join([ str((intip >> x * 8) & 0xFF) for x in [3, 2, 1, 0]])


def dot2int(dotip):
    return reduce(lambda r, x: int(x) + (r << 8), dotip.split('.'), 0)


def merge_ip_list(ip_list):
    if not ip_list:
        return []
    orig = map(dot2int, ip_list)
    orig.sort()
    start = orig[0]
    prev = start - 1
    res = []
    for x in orig:
        if x != prev + 1:
            res.append((int2dot(start), int2dot(prev)))
            start = x
        prev = x
    res.append((int2dot(start), int2dot(prev)))
    return res


def glob(feed, target_asset_groups = None):
    """Convert specified IP fields in Google Docs to glob format."""
    global args, gdocs_headers
    # Go row by row of Google spreadsheet.
    for i, entry in enumerate(feed.entry):
        #Flag to work on each type of office field. 
        do_office_ip = True
        do_static_ip = True
        do_dhcp_ip = True
        try:
            #if not '%s - %s' % (entry.custom['region'].text, entry.custom['office'].text) in "dhcp_ip_range"s:
            #    print 'Not found! %s - %s' % (entry.custom['region'].text, entry.custom['office'].text)
            region = entry.custom['region'].text
            office = '%s - %s' % (region, entry.custom['office'].text)
            # Continue to next office if limiting to specific offices.
            if target_asset_groups is not None:
                if office not in target_asset_groups:
                    logging.debug('%s not in target_asset_groups.' % (office))
                    continue
            # Assign IP ranges.
            office_ip_range = entry.custom['ipaddressassignment'].text
            dhcp_ip_range = entry.custom['ipaddressdhcp'].text
            static_ip_range = entry.custom['ipaddressstatic'].text
            # Check if there is any invalid data.
            invalid_values = gdocs_invalid(office_ip_range, dhcp_ip_range, static_ip_range)
            # Continue updating office.
            if args.office_ip and invalid_values['do_office_ip']:
                office_ip_range = ip_range_to_glob(invalid_values['office_ip_range'])
                gd_client.UpdateCell(row = i + 2, col = gdocs_headers['ipaddressassignment'], inputValue = office_ip_range, key = args.key, wksht_id = 1)
                print '%s: %s' % (office, office_ip_range)
            if args.dhcp_ip and invalid_values['do_dhcp_ip']:
                dhcp_ip_range = ip_range_to_glob(invalid_values['dhcp_ip_range'])
                gd_client.UpdateCell(row = i + 2, col = gdocs_headers['ipaddressdhcp'], inputValue = dhcp_ip_range, key = args.key, wksht_id = 1)
                print '%s DHCP: %s' % (office, dhcp_ip_range)
            if args.static_ip and invalid_values['do_static_ip']:
                static_ip_range = ip_range_to_glob(invalid_values['static_ip_range'])
                gd_client.UpdateCell(row = i + 2, col = gdocs_headers['ipaddressstatic'], inputValue = static_ip_range, key = args.key, wksht_id = 1)
                print '%s static: %s' % (office, static_ip_range)
        except AttributeError:
            pass
    return True


def gdocs_invalid(office_ip_range, dhcp_ip_range, static_ip_range):
    """Return dictionary of any invalid or missing data fields from Google Spreadsheet."""
    invalid_values = defaultdict(str)
    invalid_values['office_ip_range'] = office_ip_range
    invalid_values['dhcp_ip_range'] = dhcp_ip_range
    invalid_values['static_ip_range'] = static_ip_range
    invalid_values['do_office_ip'] = True
    invalid_values['do_dhcp_ip'] = True
    invalid_values['do_static_ip'] = True
    invalid_values['continue'] = True
    # Check for valid data       
    if office_ip_range is None and dhcp_ip_range is None:
        # No data.  Continue to next office.
        logging.debug('office_ip_range is None and dhcp_ip_range is None.')
        invalid_values['continue'] = False
    # Set flags on which asset groups to update based on prerequisites.
    # Check if office has its own unique IP range.
    if office_ip_range is not None and (office_ip_range.startswith('N/A') or office_ip_range == ''):
        # Office does not have unique office range.
        # Do not update office range. 
        invalid_values['do_office_ip'] = False
    else:
        # Convert glob to CIDR format
        logging.debug('office_ip_range = %s' % (office_ip_range))
        invalid_values['office_ip_range'] = glob_to_ip_range(office_ip_range)
    # Check if office has its own DHCP IP range.
    if dhcp_ip_range is not None and (dhcp_ip_range.startswith('N/A') or dhcp_ip_range == ''):
        # Office does not have DHCP range specified.
        # Do not update DHCP or static range. 
        invalid_values['do_dhcp_ip'] = False
        if args.static_ip:
            print 'Warning:  Cannot calculate static IP without valid DHCP IP range.'
            logging.warning('Warning:  Cannot calculate static IP without valid DHCP IP range.')
        invalid_values['do_static_ip'] = False
    else:
        # Convert glob to CIDR format
        logging.debug('dhcp_ip_range = %s' % (dhcp_ip_range))
        invalid_values['dhcp_ip_range'] = glob_to_ip_range(dhcp_ip_range)
    # Check if office has static range.
    if (static_ip_range is not None and static_ip_range.startswith('N/A')) or office_ip_range is None:
        # Office does not have complete office range specified or a unique static range.
        # Do not update static range.
        invalid_values['do_static_ip'] = False
    else:
        # Convert glob to CIDR format
        logging.debug('static_ip_range = %s' % (static_ip_range))
        invalid_values['static_ip_range'] = glob_to_ip_range(static_ip_range)
    # Debug booleans.
    logging.debug('do_office_ip = %s' % (invalid_values['do_office_ip']))
    logging.debug('do_dhcp_ip = %s' % (invalid_values['do_dhcp_ip']))
    logging.debug('do_static_ip = %s' % (invalid_values['do_static_ip']))
    # Return
    return invalid_values


def gdoc_qg_sync(feed, qg_asset_groups, target_asset_groups = None):
    """Sync Google Docs offices to QualysGuard."""
    global args, gdocs_headers
    # Keep track of failed asset group updates.
    failed_qg_updates = []
    # Go row by row of Google spreadsheet.
    for i, entry in enumerate(feed.entry):
        #Flag to work on each type of office field. 
        do_office_ip = True
        do_static_ip = True
        do_dhcp_ip = True
        try:
            #if not '%s - %s' % (entry.custom['region'].text, entry.custom['office'].text) in "dhcp_ip_range"s:
            #    print 'Not found! %s - %s' % (entry.custom['region'].text, entry.custom['office'].text)
            region = entry.custom['region'].text
            office = '%s - %s' % (region, entry.custom['office'].text)
            # Continue to next office if limiting to specific offices.
            if target_asset_groups is not None:
                if office not in target_asset_groups:
                    logging.debug('%s not in target_asset_groups.' % (office))
                    continue
            # Assign IP ranges.
            office_ip_range = entry.custom['ipaddressassignment'].text
            dhcp_ip_range = entry.custom['ipaddressdhcp'].text
            static_ip_range = entry.custom['ipaddressstatic'].text
            # Check if there is any invalid data.
            invalid_values = gdocs_invalid(office_ip_range, dhcp_ip_range, static_ip_range)
            if not invalid_values['continue']:
                # No valid office and DHCP information.  Continue to the next office
                continue
            # Continue updating office.
            office_ip_range = invalid_values['office_ip_range']
            dhcp_ip_range = invalid_values['dhcp_ip_range']
            static_ip_range = invalid_values['static_ip_range']
            print office
            # Recalculate static range if specified.
            if (args.static_ip and invalid_values['do_static_ip']) and not args.skip_calc_static:
                # Diff DHCP range from office range.
                static_ip_range = ip_range_diff(office_ip_range, dhcp_ip_range)
                if static_ip_range == '':
                    print 'ERROR:  Diff\'d static_ip_range is empty.'
                # Update static range holder to be uploaded.
                entry.custom['ipaddressstatic'].text = static_ip_range
                # Convert glob to CIDR format
                static_ip_range = ip_range_to_glob(static_ip_range)
                # Change static range in Google Docs.
                gd_client.UpdateCell(row = i + 2, col = gdocs_headers['ipaddressstatic'], inputValue = static_ip_range, key = args.key, wksht_id = 1)
            if not args.skip_qg_update:
                # Update asset groups in QualysGuard.
                for f in qg_update_ip_range(qg_asset_groups, region, office, invalid_values['do_office_ip'], invalid_values['do_dhcp_ip'], invalid_values['do_static_ip'], office_ip_range, dhcp_ip_range, static_ip_range):
                    # Keep track of any failed asset groups.
                    failed_qg_updates.append(f)
            # Print as a string.
            #print '%s: %s' % (office, static_ip_range)
        except AttributeError:
            pass
    return failed_qg_updates

def qg_ag_add_edit(qg_asset_groups, office):
    """Return 'add' or 'edit' for whether an asset group exists."""
    for d in qg_asset_groups:
        if d['office'] == office:
            # Edit QualysGuard asset group.
            return 'edit'
    # Add QualysGuard asset group.
    return 'add'


def qg_update_ip_range(qg_asset_groups, region, office, do_office, do_dhcp, do_static, office_ip_range = None, dhcp_ip_range = None, static_ip_range = None):
    """Update QualysGuard asset group's IP ranges."""
    global args
    # Keep track of which asset groups failed to update.
    failed_updates = []
    # Remove all spaces in IP ranges.
    if office_ip_range is not None:
        office_ip_range = office_ip_range.replace(' ', '')
        office_ip_range = office_ip_range.replace('/32', '')
    if dhcp_ip_range is not None:
        dhcp_ip_range = dhcp_ip_range.replace(' ', '')
        dhcp_ip_range = dhcp_ip_range.replace('/32', '')
    if static_ip_range is not None:
        static_ip_range = static_ip_range.replace(' ', '')
        static_ip_range = static_ip_range.replace('/32', '')
    # Assign scanner appliances based on region.
    scanners = {
        'AP': 'Name_of_AP_scanner',
        'EAME': 'Name_of_EAME_scanner',
        'LATAM': 'Name_of_LATAM_scanner',
        'NA': 'Name_of_NA_scanner',
        }.get(region, False)    # False is default if office is not found.
    # Assign default scanner appliance to other offices.
    if not scanners:
        scanners = {
        'Alt1': 'Alternate_scanner_#1',
        'Alt2': 'Alternate_scanner_#2',
        }.get(region, False)    # False is default if office is not found.
        if not scanners:
            print 'Does not have scanner, using NA_New_York.'
            scanners = 'NA_New_York'
    # Assign default scanner appliance based on region.
    scanner_default = {
        'AP': 'Name_of_AP_scanner',
        'EAME': 'Name_of_EAME_scanner',
        'LATAM': 'Name_of_LATAM_scanner',
        'NA': 'Name_of_NA_scanner',
        }.get(region, False)    # False is default if office is not found.
    # Assign default scanner appliance to WW offices.
    if not scanner_default:
        scanner_default = {
        'Alt1': 'Alternate_scanner_#1',
        'Alt2': 'Alternate_scanner_#2',
        }.get(region, False)    # False is default if office is not found.
        if not scanner_default:
            print 'Does not have default scanner, using NA scanner.'
            scanner_default = 'Name_of_NA_scanner'
    # Add/update office asset group.
    if office_ip_range is not None and do_office and args.office_ip:
        this_asset_group = office
        failed_updates.append(qg_update_ag(qg_asset_groups, this_asset_group, office_ip_range, scanners, scanner_default))
    # Add/update office's DHCP asset group.
    if dhcp_ip_range is not None and do_dhcp and args.dhcp_ip:
        this_asset_group = office + ' DHCP'
        failed_updates.append(qg_update_ag(qg_asset_groups, this_asset_group, dhcp_ip_range, scanners, scanner_default))
    # Add/update office's static asset group.
    if static_ip_range is not None and do_static and args.static_ip:
        this_asset_group = office + ' static'
        failed_updates.append(qg_update_ag(qg_asset_groups, this_asset_group, static_ip_range, scanners, scanner_default))
    # Remove None from failed set in case update was successful.
    failed_updates = remove_values_from_list(failed_updates, None)
    return failed_updates

def remove_values_from_list(the_list, val):
    """Remove each 'val' from 'the_list'."""
    return [value for value in the_list if value != val]

def qg_update_ag(qg_asset_groups, this_asset_group, ag_ip_range, scanners, scanner_default):
    """Update QualysGuard asset group.  Return reason if failed, or None if successful."""
    failed = defaultdict(str)
    # Check if QualysGuard asset group already exists.
    action = qg_ag_add_edit(qg_asset_groups, this_asset_group)
    query = ('action=%s&title=%s&host_ips=%s&scanner_appliances=%s&default_scanner_appliance=%s' % (action, this_asset_group, ag_ip_range, scanners, scanner_default)).replace(' ', '+')
    xml_output = qg_command(1, 'asset_group.php', query)
    tree = objectify.fromstring(xml_output)
    if tree.RETURN.attrib['status'] == 'SUCCESS':
        print 'Updated QualysGuard %s.' % (this_asset_group)
    else:
        print 'Unable to update QualysGuard \'%s\'.  Error message below.' % (this_asset_group)
        print '%s' % str(tree.RETURN).strip()
        failed['city'] = this_asset_group
        failed['reason'] = str(tree.RETURN).strip()
        return failed
        #  TODO:  Add hosts
        # <RETURN status="FAILED" number="5101">Invalid value for 'host_ips' : 10.182.7.0 (not assigned to AG owner). IPs do not exist in the user account.</RETURN>
    return None

def CellsUpdateAction(gd_client, key, wksht_id, row, col, inputValue):
  """Update Google Docs's specific cell."""
  entry = gd_client.UpdateCell(row = row, col = col, inputValue = inputValue,
      key = key, wksht_id = wksht_id)
  if isinstance(entry, gdata.spreadsheet.SpreadsheetsCell):
    print 'Updated!'


def ip_range_expand(ip_range):
    """Return list of ip addresses from ip_range.
       Example:  
       >>> ip_range_expand(['10.0.0.0/31', '10.0.0.3/32'])
       ['10.0.0.0', '10.0.0.1', '10.0.0.3']
       """
    ip_range_expanded = []
    for cidr_object in ip_range:
        # Expand each CIDR.
        for ip_addy in netaddr.IPNetwork(cidr_object):
            # Add individual IP to expansion range.
            ip_range_expanded.append(str(ip_addy))
    return qgir_tools.unique(ip_range_expanded)


def ip_range_diff(source_ip_range, remove_ip_range):
    """Return source_ip_range after excluding remove_ip_range."""
    # Convert IP ranges to CIDR.
    source_ip_range = ip_range_to_cidr(source_ip_range)
    remove_ip_range = ip_range_to_cidr(remove_ip_range)
    logging.debug('source_ip_range = %s' % (source_ip_range))
    logging.debug('remove_ip_range = %s' % (remove_ip_range))
    # Expand each range.
    source_ip_range_expanded = ip_range_expand(source_ip_range)
    remove_ip_range_expanded = ip_range_expand(remove_ip_range)
#    logging.debug('remove_ip_range_expanded = %s' % (remove_ip_range_expanded))
    # Remove each matching source IP address individually.
    for i in remove_ip_range_expanded:
        try:
            source_ip_range_expanded.remove(i)
        except ValueError:
            # Value not in source_ip_range
            continue
    # Convert remaining range to CIDR.
#    logging.debug('source_ip_range_expanded = %s' % (source_ip_range_expanded))
    source_ip_range = netaddr.cidr_merge(source_ip_range_expanded)
    logging.debug('source_ip_range = %s' % (source_ip_range))
    # Convert each CIDR block to string.
    result_cidr = []
    for cidr_object in source_ip_range:
        result_cidr.append(str(cidr_object))
    # Convert entire list to a string.
    result_cidr = ', '.join(result_cidr)
    logging.debug('result_cidr = %s' % (result_cidr))
    # Remove '/32' (single IP) and return diff'd range.
    return result_cidr.replace('/32', '')


def ip_range_to_cidr(ip_network_string):
    """Convert ip_network_string into CIDR notation."""
    # Split string into list by ', ' delimiter.
    ip_network_cidr = []
    ip_network_list = ip_network_string.split(', ')
    for ip_object in ip_network_list:
        # For every ip range ('10.182.71.0-10.182.75.255'), convert to individual slash notation, 10.182.71.0/24, 10.182.72.0/22.
        if '-' in ip_object:
            # The object is a range.
            dash = ip_object.find('-')
            # First part of ip range.
            ip_start = ip_object[:dash]
            # Last part of ip range.
            ip_end = ip_object[dash + 1:]
            # Generate lists of IP addresses in range.
            ip_range = list(netaddr.iter_iprange(ip_start, ip_end))
            # Convert start & finish range to CIDR.
            ip_range = netaddr.cidr_merge(ip_range)
            # May be one or more objects in list.
            # Example 1:  '10.182.71.0-10.182.75.255' ==> ['10.182.71.0/24, 10.182.72.0/22']
            # Example 2:  '10.182.90.0-10.182.91.255' ==> ['10.182.90.0/23']
            # Add each CIDR to ip_network.
            for ip_object in ip_range:
                 ip_network_cidr.append(str(ip_object))
        else:
            # The object is not a range, just add it.
            logging.debug('ip_object = %s' % (ip_object))
            ip_network_cidr.append(str(netaddr.IPNetwork(ip_object).cidr))
    # Return as a string with delimiter ', '
    return ip_network_cidr


def qg_command(api_version, command, command_parameter = '', asset_group = None):
    """Run QualysGuard command and return status."""
    global qgc, qgs
    # Format asset group for QualysGuard API call.
    if not asset_group == None:
        asset_group_curl = asset_group.replace(' ', '+')
        query += asset_group_curl
    # Set paramaters for QualysGuard API v2
    if api_version == 1:
        # Return xml file for scan of asset_group for qid.
        # Set paramaters for QualysGuard API v1
        xml_output = qgc.request(command, command_parameter)
    elif api_version == 2:
        # Call QualysGuard API v2
        xml_output = qgs.request(command, command_parameter)
    else:
        logging.error('API version unrecognized.')
        return False
    logging.debug('qg_command xml_output =')
    logging.debug(xml_output)
    # Return API call result.
    return xml_output


def qg_ag_set():
    """Return set of current QualysGuard asset groups."""
    xml_output = qg_command(1, 'asset_group_list.php')
    # Objectify XML string.
    tree = objectify.fromstring(xml_output)
    # Parse tree for each asset group title.
    #logging.debug('Parsing report...')
    qg_asset_groups = set()
    for a in tree.ASSET_GROUP:
        # Extract asset group titles.
        try:
            qg_asset_groups.add(unicodedata.normalize('NFKD', unicode(a.TITLE.text)).encode('ascii', 'ignore').strip())
        except AttributeError:
            print 'Could not decipher:  %s' % (a.TITLE.text)
    return qg_asset_groups


def qg_ag_list():
    """Return list of current QualysGuard asset groups."""
    xml_output = qg_command(1, 'asset_group_list.php')
    # Objectify XML string.
    tree = objectify.fromstring(xml_output)
    # Parse tree for each asset group title.
    #logging.debug('Parsing report...')
    qg_asset_groups = []
    for a in tree.ASSET_GROUP:
        # Extract asset group titles.
        try:
            qg_asset_groups.append({'office': unicodedata.normalize('NFKD', unicode(a.TITLE.text)).encode('ascii', 'ignore').strip(), 'id': unicodedata.normalize('NFKD', unicode(a.ID.text)).encode('ascii', 'ignore').strip()})
        except AttributeError:
            print 'Could not decipher:  %s' % (a.TITLE.text)
    # Sort asset groups.
    qg_asset_groups = sorted(qg_asset_groups, key = itemgetter('office'))
    return qg_asset_groups


def qg_print_asset_groups(qg_asset_groups):
    """Print asset groups to screen."""
    # Print each asset group and ID #.
    print 'All asset groups in QualysGuard:'
    for a in qg_asset_groups:
        print '%s, %s' % (a['office'], a['id'])
    print
    offices = gdocs_offices(feed)
    print 'All asset groups in QualysGuard that are not in Google Docs:'
    for a in qg_asset_groups:
        if not a['office'] in offices and 'DHCP' not in a['office'] and 'static' not in a['office']:
            print a['office']
    return True


def gdocs_offices(feed):
    """Print offices from Google Docs to screen."""
    # Go row by row of Google spreadsheet.
    offices = set()
    for i, entry in enumerate(feed.entry):
        try:
            region = entry.custom['region'].text
            office = '%s - %s' % (region, entry.custom['office'].text)
            offices.add(office)
        except AttributeError:
            None
    return offices


def qradar_sync(bucket_file):
    """Sync site network information to QRadar as "buckets" from buckets file."""
    logging.debug('qradar_sync(%s)' % (bucket_file))
    # Read CSV buckets
    # Format is, 'Region.Site, IP range 1, IP range 2, ...
    csv_file = csv.reader(open(bucket_file, 'rb'), delimiter = ',')
    logging.debug('Reading in %s.' % (csv_file))
    # Store info in dictionary as list of IP ranges.
    buckets = defaultdict(str)
    for row in csv_file:
        # E.g.: d['EAME.Beirut'] = ['10.122.0.0-10.122.108.255', ' 10.122.110.0-10.122.255.255']
        buckets[row[0]] = row[1:]
    # Convert list of IP ranges to CIDR format.
    print 'Converting each site to CIDR format...\n'
    for site in sorted(buckets.keys()):
        logging.debug('Converting %s.' % (site))
        # Merge list of IP ranges to a string with a comma delimiter.
        ip_ranges = ''
        for ip_range in buckets[site]:
            # Strip out spaces and add delimiter.
            ip_ranges += ip_range.strip() + ', '
        # E.g.: '10.122.0.0-10.122.108.255, 10.122.110.0-10.122.255.255, '
        # Remove last ', '.
        ip_ranges = ip_ranges[:-2]
        # E.g.: '10.122.0.0-10.122.108.255, 10.122.110.0-10.122.255.255'
        buckets[site] = ip_range_to_cidr(ip_ranges)
        print site, buckets[site]
        logging.critical('%s: %s' % (site, str(buckets[site])))
    print '\nCIDR conversion complete.'
    print 'Writing tab-delimited CSV file...\n'
    # Write out new CSV file.
    with open('%s_converted.csv' % (bucket_file[:-4]), 'wb') as out_file:
        # Write tab-delimited file.
        csv_writer = csv.writer(out_file, dialect = 'excel-tab')
        # Write out each site with one CIDR per row.
        for site in sorted(buckets.keys()):
            for cidr in buckets[site]:
                csv_writer.writerow([site, cidr])
    return True


def ConfigSectionMap(section):
    dict1 = {}
    options = Config.options(section)
    for option in options:
        try:
            dict1[option] = Config.get(section, option).replace('\\n', '')
            if dict1[option] == -1:
                DebugPrint("skip: %s" % option)
        except:
            print("exception on %s!" % option)
            dict1[option] = None
    return dict1


#
#  Begin
#
print 'Logged into Google Docs...'
# Declare the command line flags/options we want to allow.
parser = argparse.ArgumentParser(description = 'Sync CMDB from Google Spreadsheet to QualysGuard.')
parser.add_argument('-a', '--asset_group',
                    help = 'Asset group(s) -- office -- to sync.  If not specified, sync all offices.')
parser.add_argument('-b', '--debug', action = 'store_true',
                    help = 'Outputs additional information to log.')
parser.add_argument('-c', '--static_ip', action = 'store_true',
                    help = 'Calculates and syncs only static IP range.')
parser.add_argument('-d', '--dhcp_ip', action = 'store_true', default = False,
                    help = 'Syncs DHCP range.')
parser.add_argument('--check_cmdb', action = 'store_true',
                    help = 'Check CMDB\'s office listings against Google Doc\'s offices.')
parser.add_argument('-f', '--print_offices', action = 'store_true', default = False,
                    help = 'Print all offices.')
parser.add_argument('-g', '--glob', action = 'store_true',
                    help = 'Convert IP ranges in Google Docs to glob format (\'10.0.0.0, 10.0.0.1, 10.0.0.2\' --> \'10.0.0.0-10.0.0.2\').')
parser.add_argument('-i', '--ini', default = 'config.ini',
                    help = 'Configuration file for login.')
parser.add_argument('-k', '--key', default = 'default_google_spreadsheet_here',
                    help = 'Google spreadsheet to access.')
parser.add_argument('-o', '--office_ip', action = 'store_true',
                    help = 'Syncs office IP range.')
parser.add_argument('-p', '--print_asset_groups', action = 'store_true',
                    help = 'Print all QualysGuard asset groups.')
parser.add_argument('-r', '--qradar', action = 'store_true',
                    help = 'Sync QRadar buckets, create tab-delimited CSV file from Google Spreadsheet.')
parser.add_argument('-s', '--sync', action = 'store_true',
                    help = 'Sync all IP ranges (office, DHCP, and static).')
parser.add_argument('--skip_calc_static', action = 'store_true',
                    help = 'Skip calculating static range.')
parser.add_argument('--skip_qg_update', action = 'store_true',
                    help = 'Skip updating QualysGuard asset groups.')
parser.add_argument('--test', action = 'store_true', default = False,
                    help = 'Test.')
# Parse arguements.
args = parser.parse_args()
# Create log directory.
PATH_LOG = 'log'
if not os.path.exists(PATH_LOG):
    os.makedirs(PATH_LOG)
# Set log options.
now = datetime.datetime.now()
LOG_FILENAME = '%s/sync_host_ips.py-%s.log' % (
    PATH_LOG, datetime.datetime.now().strftime('%Y-%m-%d.%H-%M-%S'))
if args.debug:
    # Enable debug level of logging.
    print "Logging level set to debug."
    logging.basicConfig(filename = LOG_FILENAME, format = '%(asctime)s %(message)s',
                        level = logging.DEBUG)
else:
    logging.basicConfig(filename = LOG_FILENAME, format = '%(asctime)s %(message)s',
                        level = logging.INFO)
# Read from configuration file.
Config = ConfigParser.ConfigParser()
Config.read(args.ini)
# Google login information
gd_client = gdata.spreadsheet.service.SpreadsheetsService()
gd_client.email = ConfigSectionMap('Google')['username']
gd_client.password = ConfigSectionMap('Google')['password']
gd_client.source = 'google_spreadsheet'
gd_client.ProgrammaticLogin()
# QualysGuard credentials
qg_username = ConfigSectionMap('QualysGuard')['username']
qg_password = ConfigSectionMap('QualysGuard')['password']
# Log in to both QualysGuard APIs.
qgc = build_v1_connector()
qgs = build_v2_session()
qgs.connect()
# Turn on flags for all types of IP ranges if --sync parameter specified.
if args.sync:
    args.static_ip = True
    args.office_ip = True
    args.dhcp_ip = True
# Validate input.
if not (args.static_ip or \
        args.office_ip or \
        args.dhcp_ip or \
        args.print_asset_groups or \
        args.print_offices or \
        args.qradar or \
        args.test or \
        args.check_cmdb or \
        args.glob):
    parser.print_help()
    exit()
# Convert comma delimited asset group string specified (if any) into a set.
if args.asset_group is not None:
    asset_group_copy = args.asset_group.split(',')
    args.asset_group = set()
    for a in asset_group_copy:
        if len(a) > 0:
            args.asset_group.add(a.strip())
# Obtain rm2 tracker feed. 
feed = ListGetAction(gd_client, args.key, 1)
feed2 = CellsGetAction(gd_client, args.key, 1)
gdocs_headers = gdocs_column_headers(feed2)
# Retreive current list of asset groups
qg_asset_groups = []
if not (args.test or \
        args.skip_qg_update or \
        args.glob):
    qg_asset_groups = qg_ag_list()
# (Optional) Print asset groups to screen.
if args.print_asset_groups:
    qg_print_asset_groups(qg_asset_groups)
    exit()
# (Optional) Print offices to screen.
if args.print_offices:
    gdocs_print_offices(feed)
    exit()
# (Optional) Print offices to screen.
if args.test:
    # Print headers.
    print 'Headers and associated column number:'
    for key in sorted(gdocs_headers.iterkeys()):
        print '%s %s' % (key, gdocs_headers[key])
    # Print sites.
    print
    print 'Sites and associated IP address assignment:'
    test(feed)
    exit()
# (Optional) Print offices to screen.
if args.check_cmdb:
    check_cmdb(feed)
    exit()
# (Optional) Print offices to screen.
if args.glob:
    glob(feed, args.asset_group)
    exit()
# (Optional) Print offices to screen.
if args.qradar:
    print 'Creating bucket file to sync with QRadar.\n'
    bucket_file = qradar_sync('buckets.csv')
    if bucket_file:
        print 'QRadar bucket file, %s, created.' % (bucket_file)
    else:
        print 'Unable to create QRadar bucket file.'
    exit()
# Sync Google Docs with QualysGuard
logging.debug('args.asset_group = %s' % (args.asset_group))
failed_qg_updates = gdoc_qg_sync(feed, qg_asset_groups, args.asset_group)
if failed_qg_updates:
    # At least one asset group failed.
    print 'The asset groups below failed to update.'
    for f in failed_qg_updates:
        print '\'%s\': %s' % (f['city'], f['reason'])
exit(0)




