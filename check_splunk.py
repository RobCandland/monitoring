#!/usr/bin/env python
# Nagios style monitoring check that will submit a search job to Splunk and count results
# Example to search for "Error sending HTTP request" and alert for more than 5 results:
# ./check_splunk.py -u splunkuser -p splunkpass\
#  -s 'index="asdf" host="*asdf*" earliest=-10m latest=-5m "Error sending HTTP request"'\
#  -e 'HTTP request error detected in Splunk for asdf' -H splunk.domain.com -t 5
# Requires requests module


def argparse():
    import argparse
    parser = argparse.ArgumentParser(description="Search splunk")
    parser.add_argument("-H", "--host", dest="host", type=str,
                        help="Splunk host", default="splunk.domain.com")
    parser.add_argument("-P", "--port", dest="port", type=int,
                        help="Optional port for Splunk host", default=8089)
    parser.add_argument("-v", "--verbose", action="count",
                        help="Output verbose messages, -vv increases verbosity",
                        default=0)
    parser.add_argument("-u", "--user", dest="user", type=str, help="Optional, splunk user",
                        default="splunkuser@domain.com")
    parser.add_argument("-p", "--passwd", dest="passwd", type=str,
                        help="Optional, splunk user password", default="splunkpass")
    parser.add_argument("-s", "--search", dest="search", type=str,
                        help="Required, splunk search query string", required=True)
    parser.add_argument("-e", "--errormsg", dest="errormsg", type=str,
                        help="Required, error message output for Nagios/Zenoss", required=True)
    parser.add_argument("-t", "--threshold", dest="threshold", type=int,
                        help="Threshold of number of results on which to alert, default is 0",
                        default=0)
    parser.add_argument("-n", "--nossl", dest="nossl", action="store_true",
                        help="Optional, don't use SSL")
    options = parser.parse_args()
    return options


def deflog(options):
    import logging as log
    levels = [log.WARNING, log.INFO, log.DEBUG]
    level = levels[min(len(levels)-1, options.verbose)]
    # if argparse -v is not passed log.warning is stderr by default
    # -v is log.info and -vv is log.debug
    log.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")
    return log


def splunkgetsessionkey(options, auth_url):
    import requests
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except:
        pass
    import sys
    log.info("Trying {0} to authenticate to Splunk API".format(auth_url))
    try:
        r = requests.post(auth_url,
                          data={'username': options.user,
                                'password': options.passwd,
                                'output_mode': 'json'},
                          verify=False)
    except:
        print("WARNING - Could not access {0}|".format(auth_url))
        sys.exit(1)
    log.info("Success from authentication, output is:")
    log.info("{0}".format(r.text))
    try:
        authjson = r.json()
        # JSON returned (if successfull) is like the following
        # {"sessionKey":"pn1^MWBRnKasdfksucMGnT5ryjNnzPasdflnlots_more_text"}
    except:
        print("WARNING - Could not retrieve JSON from {0}|".format(auth_url))
        sys.exit(1)
    try:
        sessionkey = authjson['sessionKey']
        log.info("Verified we got sessionkey in JSON output")
    except:
        print("WARNING - Could not retrieve sessionKey JSON value from {0}|".format(auth_url))
        sys.exit(1)
    return authjson


def splunkcreatesearch(search_url, search_query, sessionkey):
    import requests
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except:
        pass
    import sys

    # Create search job
    log.info("Trying {0} to create Splunk search in API".format(search_url))
    try:
        s = requests.post(search_url,
                          headers={'Authorization': 'Splunk {0}'.format(sessionkey)},
                          data={'search': search_query, 'output_mode': 'json'},
                          verify=False)
        log.info("Success creating search job, output is {0}".format(s.text))
    except:
        print("WARNING - Could not retrieve from {0}|".format(search_url))
        sys.exit(1)
    try:
        searchjson = s.json()
        # JSON returned if successfull is like:
        # {"sid":"1999888470.1553447"}
    except:
        print("WARNING - Could not retrieve JSON from {0}|".format(search_url))
        sys.exit(1)
    try:
        sid = searchjson['sid']
        log.info("Verified we got sid value in JSON output: {0}".format(sid))
    except:
        print("WARNING - Could not retrieve sessionKey JSON value from {0}|".format(r.json))
        sys.exit(1)
    return sid


def splunkcheckjobloop(status_url, sessionkey):
    import requests
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except:
        pass
    import time
    import sys
    # Set variables and run while loop that checks job status
    isdone = ''
    isfailed = ''
    isnotdone = True
    while isnotdone:
        try:
            status = requests.get(status_url,
                                  headers={'Authorization': 'Splunk {0}'.format(sessionkey)},
                                  data={'output_mode': 'json'},
                                  verify=False)
        except:
            print("WARNING - Could not retrieve from {0}|".format(status_url))
            sys.exit(1)
        try:
            statusjson = status.json()
            isdone = statusjson['entry'][0]['content']['isDone']
            isfailed = statusjson['entry'][0]['content']['isFailed']
            log.info("JSON validated, status - isDone - {0}, isFailed - {1}"
                     .format(isdone, isfailed))
            if isdone is True:
                isnotdone = False
            if isfailed is True:
                print("WARNING - Splunk job with sid {0} failed|".format(sid))
                sys.exit(1)
            time.sleep(1)
        except:
            print("WARNING - Could not retrieve JSON from {0}".format(status_url))
            sys.exit(1)
    return statusjson


def splunkretrieveresults(results_url, sessionkey):
    import requests
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except:
        pass
    import sys
    # Retrieve search results
    log.info("Trying {0} for search results via Splunk API".format(results_url))
    try:
        results = requests.get(results_url,
                               headers={'Authorization': 'Splunk {0}'.format(sessionkey)},
                               data={'output_mode': 'json'},
                               verify=False)
    except:
        print("WARNING - Could not retrieve from {0}|".format(results))
        sys.exit(1)
    try:
        resultsjson = results.json()
    except:
        print("WARNING - Could not retrieve JSON from {0}|".format(results_url))
        sys.exit(1)
    return resultsjson


if __name__ == '__main__':
    import sys
    import json
    import logging as log
    options = argparse()
    log = deflog(options)
    log.info("Starting Splunk API search to {0}:{1} with user {2}"
             .format(options.host, options.port, options.user))

    # Make sure search query starts with search
    if not options.search.startswith('search'):
        search_query = 'search ' + options.search
    log.info("search_query is ->{0}<-".format(search_query))

    # Define some URL's
    if options.nossl:
        base_url = 'http://' + options.host + ':' + str(options.port)
    else:
        base_url = 'https://' + options.host + ':' + str(options.port)
    auth_url = base_url + '/services/auth/login'
    search_url = base_url + '/services/search/jobs'

    # Step 1, authenticate and get a session key
    authjson = splunkgetsessionkey(options, auth_url)
    sessionkey = authjson['sessionKey']

    # Step 2, create search job, get search id
    sid = splunkcreatesearch(search_url, search_query, sessionkey)

    # Step 3, run while loop that checks job status
    # Construct status_url with sid in path:
    status_url = base_url + '/services/search/jobs/' + sid + '/'
    log.info("Trying {0} for status of Splunk job".format(status_url))
    statusjson = splunkcheckjobloop(status_url, sessionkey)
    log.info("Success getting status")
    log.debug("statusjson is {0}".format(statusjson))

    # Step 4, retrieve results
    # Construct results_url with sid in path
    results_url = base_url + '/services/search/jobs/' + sid + '/results'
    resultsjson = splunkretrieveresults(results_url, sessionkey)
    log.info("Success getting results from Splunk API")
    log.debug("resultsjson is {0}".format(resultsjson))

    # Count number of results, print Nagios style output and exit
    numberofresults = 0
    for key in resultsjson['results']:
        if key['_raw']:
            value = key['_raw']
            numberofresults += 1

    if numberofresults > options.threshold:
        log.info("Got {0} results, last _raw key value of results JSON is:"
                 .format(numberofresults))
        log.info("{0}End of _raw key value".format(value))
        print("CRITICAL - {0}, error count is {1}|resultsfound={1};;;0"
              .format(options.errormsg, numberofresults))
        sys.exit(2)
    else:
        log.info("Retrieved results, zero found")
        print("OK - zero results from search|resultsfound=0;;;0")
        sys.exit(0)
