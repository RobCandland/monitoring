#!/usr/bin/env python
# Most likely not python 3 compatible
# Be sure to modify parser.add_argument entries in main
# or supply Zenoss credentials/PD info via parameters

import argparse
import json
import requests
import re
import logging as log
from datetime import datetime
from datetime import date
from datetime import timedelta


def minutes_ago(now, minutes):
    # Get datetime x minutes ago, plus 1 second
    result = now - timedelta(minutes=minutes) - timedelta(seconds=1)
    return result


def get_log_entries(since, until, offset):
    url = 'https://api.pagerduty.com/log_entries'
    headers = {
        'Accept': 'application/vnd.pagerduty+json;version=2',
        'Authorization': 'Token token=' + options.apikeypd
    }
    since = datetime.strftime(since, '%Y-%m-%dT%H:%M:%SZ')
    until = datetime.strftime(until, '%Y-%m-%dT%H:%M:%SZ')
    payload = {
        'time_zone': 'UTC',
        'is_overview': 'true',
        'limit': 100,
        'since': since,
        'until': until,
        'offset': offset,
        'include[]': 'incidents'
    }
    r = requests.get(url, headers=headers, params=payload)
    log_entries = r.json()
    # log.debug("Log entries JSON from PagerDuty:")
    # log.debug(json.dumps(log_entries, indent = 4))
    return log_entries


def parse_log_entries(log_entries, counter):
    log.info("Parsing {0} PagerDuty log entries, offset is {1}".format(len(log_entries), counter))
    if options.onlyjson:
        # print("Sub entries JSON:")
        print (json.dumps(log_entries, indent=4))
        exit(0)
    if len(log_entries) is 0:
        log.info("No log entries found")
        return
    for index in range(len(log_entries)):
        # NOTE!!!!!  This needs to be customized for your PD service, put correct one
        # in options.pdservice:
        #            |||||||||||||||||
        if re.search(options.pdservice, log_entries[index][u'service'][u'summary']):
            log.debug("Got '{0}' PD service, proceeding".format(options.pdservice))
            # Assign maybe in future
            # if (log_entries[index][u'type'] == u'resolve_log_entry' or
            #     log_entries[index][u'type'] == u'assign_log_entry' or
            #     log_entries[index][u'type'] == u'acknowledge_log_entry'):
            if (log_entries[index][u'type'] == u'resolve_log_entry' or
               log_entries[index][u'type'] == u'acknowledge_log_entry'):
                log.debug("Got 'resolve/ack', proceeding")
                if not re.search('.*through the API', log_entries[index][u'summary']):
                    log.info("Alert action is website or PD app or text/phone, proceeding")
                    log.debug("<--------------------------------------->")
                    log.debug("This indexed {0} snippet of JSON is:".format(index))
                    log.debug(log_entries[index])
                    log.debug("<--------------------------------------->")
                    inczenver = log_entries[index][u'service'][u'summary']
                    log.debug("log_entries[{0}][u'service'][u'summary'] is {1}"
                              .format(index, inczenver))
                    inczenkey = log_entries[index][u'incident'][u'incident_key']
                    log.debug("log_entries[{0}][u'incident'][u'incident_key'] {1}"
                              .format(index, inczenkey))
                    log.debug("Derived Zenoss URL: {0}/zport/dmd/Events/viewDetail?evid={1}"
                              .format(zenhosturl, inczenkey))
                    incmodby = log_entries[index][u'summary']
                    log.debug("log_entries[{0}][u'summary'] is {1}".format(index, incmodby))
                    inctype = log_entries[index][u'type']
                    log.debug("log_entries[{0}][u'type'] is {1}".format(index, inctype))
                    inctitle = log_entries[index][u'incident'][u'title']
                    log.debug("log_entries[{0}][u'incident'][u'title'] {1}"
                              .format(index, inctitle))
                    incmodvia = log_entries[index][u'channel'][u'type']
                    log.debug("log_entries[{0}][u'channel'][u'type'] {1}"
                              .format(index, incmodvia))
                    incmodtime = log_entries[index][u'created_at']
                    log.debug("log_entries[{0}][u'created_at'] is {1}".format(index, incmodtime))
                    # Parse "type":"acknowledge_log_entry" to get Zenoss friendly names
                    # Maybe in future:
                    # if log_entries[index][u'type'] == "assign_log_entry":
                    #     incaction = u"assign"
                    # log.debug("ret is {0}, {1}, {2}".format(incaction, inczenkey, inctext))
                    if log_entries[index][u'type'] == "acknowledge_log_entry":
                        incaction = u"acknowledge"
                    elif log_entries[index][u'type'] == "resolve_log_entry":
                        incaction = u"close"
                    inctext = ((
                              u"Changing state of this alert to {0} as PagerDuty reports"
                              u" '{1} via {2} at {3}'. ({4})")
                              .format(incaction, incmodby, incmodvia, incmodtime, __file__))
                    log.info("Incident text (inctext) is ->{0}<-".format(inctext))
                    # Finally log then close/ack Zenoss event
                    if options.test:
                        log.info("Test mode activated, only logging in event in Zenoss, not")
                        log.info("running {0} on evid".format(incaction, inczenkey))
                        inctext += " - TESTING, not modifying event status, entering log only"
                        # Log to Zenoss event only, no close/ack
                        zeneventlog(incaction, inczenkey, inctext)
                    elif options.nologtest:
                        log.info("No log test mode, only printing message, not")
                        log.info("running {0} on evid {1}".format(incaction, inczenkey))
                        log.info("Incident text is ->{0}<-".format(inctext))
                    else:
                        # Log to Zenoss event, then close/ack event
                        zeneventlog(incaction, inczenkey, inctext)
                        zeneventmod(incaction, inczenkey)
                else:
                    log.info("Skipped index {0} of log_entries, as".format(index))
                    log.info("PagerDuty API was used.")
                    log.debug("<--------------------------------------->")
                    log.debug("This index {0} snippet of JSON is:".format(index))
                    log.debug(log_entries[index])
                    log.debug("<--------------------------------------->")
            else:
                log.info("Skipped index {0} of log_entries, not ack/resolve".format(index))
                log.debug("<--------------------------------------->")
                log.debug("This index {0} snippet of JSON is:".format(index))
                log.debug(log_entries[index])
                log.debug("<--------------------------------------->")
        else:
            log.info("Skipped index {0} of log_entries".format(index))
            log.info("as PagerDuty service is not {0}".format(options.pdservice))
            log.debug("<--------------------------------------->")
            log.debug("This index {0} snippet of JSON is:".format(index))
            log.debug(log_entries[index])
            log.debug("<--------------------------------------->")


def zeneventopencheck(evid):
    # This function is not needed but here for possible future use
    log.info("Checking Zenoss evid {0}".format(evid))
    zenup = (options.zenuser, options.zenpass)
    zenapiurl = zenhosturl + "/zport/dmd/evconsole_router"
    payload = {"action": "EventsRouter",
               "method": "detail",
               "data": [
                   {
                       "evids": evid
                   }
               ],
               "tid": 1}
    r = requests.post(zenapiurl, json=payload, verify=False, auth=zenup)
    j = r.json()
    if j[u'result'][u'event'][0][u'eventState'] == "New":
        return True
    else:
        return False


def zeneventlog(ackorclose, evid, message):
    log.info("Log to Zenoss evid {0} before {1}, message: {2}".format(evid, ackorclose, message))
    zenup = (options.zenuser, options.zenpass)
    zenapiurl = zenhosturl + "/zport/dmd/evconsole_router"
    payload = {"action": "EventsRouter",
               "method": "write_log",
               "data": [
                   {
                       "evid": evid,
                       "message": message
                   }
               ],
               "tid": 1}
    r = requests.post(zenapiurl, json=payload, verify=False, auth=zenup)
    j = r.json()
    # Testing
    # log.debug(d = json.dumps(j, indent=4))
    if j[u'result'][u'success'] is True:
        log.info("Success logging to evid {0}".format(evid))
        return True
    else:
        log.info("Could not update Zenoss event log for {0}".format(inczenkey))
        return False


def zeneventmod(ackorclose, evid):
    log.info("Setting Zenoss evid {0} to {1}".format(evid, ackorclose))
    # ackorclose needs to be one of: close|reopen|acknowledge|unacknowledge
    zenup = (options.zenuser, options.zenpass)
    zenapiurl = zenhosturl + "/zport/dmd/evconsole_router"
    payload = {"action": "EventsRouter",
               "method": ackorclose,
               "data": [
                   {
                       "evids": [
                           evid
                       ]
                   }
               ],
               "tid": 1}
    r = requests.post(zenapiurl, json=payload, verify=False, auth=zenup)
    j = r.json()
    d = json.dumps(j, indent=4)
    if j[u'result'][u'success'] is True:
        log.info("Zenoss event with evid of {0} {1} successfully".format(evid, ackorclose))
        return True
    else:
        log.info("Attempt to {0} evid of {1} failed:{2}".format(ackorclose, evid, d))
        return False

if __name__ == '__main__':
    description = "Query PagerDuty v2 API to get Log_Entries for alerts ack'd or resolved "
    description += "via PagerDuty and modify associated events in Zenoss 4.2.5 by "
    description += "ack-ing or closing via Zenoss API after entering a log.  Running with -m 1 "
    description += "will query PagerDuty logs between now and one minute previous. "
    description += "Note that this works only with PagerDuty Zenpack installed. "
    description += "Intended to be run via cron once a minute."
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("-v", "--verbose", action="count",
                        help="Output verbose messages, -vv increases verbosity")
    parser.add_argument("-m", "--minutes", default=1, type=int,
                        help="Interval of previous minutes back to check PagerDuty")
    parser.add_argument("-H", "--zenhost", default="zenoss.domain.com",
                        help="Zenoss host, default is zenoss.domain.com")
    parser.add_argument("-P", "--zenport", default=8080,
                        help="Zenoss port")
    parser.add_argument("-u", "--zenuser", default="zenuser",
                        help="Zenoss user that can manage events")
    parser.add_argument("-p", "--zenpass", default="passw0rd",
                        help="Zenoss password")
    parser.add_argument("-a", "--apikeypd", default="CHANGE_ME-GET_FROM_PAGERDUTY",
                        help="PagerDuty API Key")
    parser.add_argument("-o", "--onlyjson", action="store_true",
                        help="Output JSON only and exit")
    parser.add_argument("-t", "--test", action="store_true",
                        help="Test, retrieve from PD, log to event in Zenoss only")
    parser.add_argument("-n", "--nologtest", action="store_true",
                        help="Test, retrieve from PD, no change to Zenoss, use with -v")
    parser.add_argument("-s", "--pdservice", default="CHANGE_ME_TO_PD_SERVICE_NAME",
                        help="PagerDuty Service name")
    options = parser.parse_args()

    if options.zenport == 443:
        zenhosturl = "https://" + options.zenhost
    else:
        zenhosturl = "http://" + options.zenhost + ":" + str(options.zenport)

    levels = [log.WARNING, log.INFO, log.DEBUG]
    level = levels[min(len(levels)-1, options.verbose)]
    log.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")

    log.info("Starting PagerDuty/Zenoss event integration script")
    log.info("Querying for the following time range.")

    now = datetime.utcnow()
    then = minutes_ago(now, options.minutes)
    log.info("From: {0}".format(datetime.strftime(then, '%Y-%m-%dT%H:%M:%SZ')))
    log.info("  To: {0}".format(datetime.strftime(now, '%Y-%m-%dT%H:%M:%SZ')))

    foo = True
    counter = 0
    while foo is True:
        # Get log entries with appropriate offset, needed for PagerDuty pagination
        log_entries_all = get_log_entries(then, now, counter)
        log_entries = log_entries_all[u'log_entries']
        # Note that parse_log_entries calls other functions
        parse_log_entries(log_entries, counter)
        # Testing
        # log.info("log_entries_all[u'more'] is {0}".format(log_entries_all[u'more']))
        if log_entries_all[u'more'] is True:
            log.info("PagerDuty pagination detected, getting 100 more")
            counter += 100
        else:
            foo = False

    log.info("Script finished")
    log.info("--------------------------------------------------")
# EOF
