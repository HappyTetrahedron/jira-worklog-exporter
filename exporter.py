#!/usr/bin/env python3
import requests
import json
import datetime
import csv
import io
import re
from icalendar import Calendar, Event, vText
import caldav

REPORT_URL = 'https://{}/rest/jttp-rest/latest/download-report/downloadWorklogDetailsReportAsCSV'
QUERY_PARAMS = {
    "worklogTimeExport": "seconds"
}

WORKLOG_ID_REGEX = re.compile(r'\[JIRA:(\S+)\]')
START_TIME_FORMAT = '%d. %b %Y %H:%M'

START_TIME_KEY = "Start Time"
TIME_SPENT_KEY = "Time Spent (s)"
WORKLOG_DESCRIPTION_KEY = "Worklog Description"
ISSUE_NUMBER_KEY = "Issue Key"
ISSUE_TITLE_KEY = "Issue Summary"
WORKLOG_ID_KEY = "Worklog ID"

BUCKET_ISSUE_KEYS = ["ALDE-2", "ALDE-3", "ALDE-7"]

KEYS = [
    START_TIME_KEY,
    TIME_SPENT_KEY,
    WORKLOG_DESCRIPTION_KEY,
    ISSUE_NUMBER_KEY,
    ISSUE_TITLE_KEY,
    WORKLOG_ID_KEY,
]

DAYS_TO_PROCESS = 4

def get_worklogs(token, reportfilter, from_timestamp, to_timestamp, jira):
    with open(reportfilter) as filterfile:
        filter = json.load(filterfile)

        filter["filterCondition"]["worklogStartDate"] = from_timestamp
        filter["filterCondition"]["worklogEndDate"] = to_timestamp

        query_params = dict(**QUERY_PARAMS)
        query_params["json"] = json.dumps(filter, separators=(',',':'))
        headers = {
            "Authorization": f"Bearer {token}"
        }

        res = requests.get(REPORT_URL.format(jira), params=query_params, headers=headers)
        return res.text

def parse_csv(csv_text):
    reader = csv.reader(io.StringIO(csv_text))

    first_row = next(reader)
    key_index = {}

    for key in KEYS:
        key_index[key] = first_row.index(key)

    events = []

    for row in reader:
        event = {}
        for key in KEYS:
            event[key] = row[key_index[key]]
        events.append(event) 

    return events


def create_event_properties(jira_event):
    short_desc = jira_event[WORKLOG_DESCRIPTION_KEY].splitlines()[0]
    start_time = datetime.datetime.strptime(jira_event[START_TIME_KEY], START_TIME_FORMAT)
    seconds = int(jira_event[TIME_SPENT_KEY])
    end_time = start_time + datetime.timedelta(seconds=seconds)
    summary = f'{jira_event[ISSUE_NUMBER_KEY]}: {short_desc}' \
        if jira_event[ISSUE_NUMBER_KEY] not in BUCKET_ISSUE_KEYS \
        else f'{short_desc}'
    return {
        "dtstart": start_time,
        "dtend": end_time,
        "summary": summary,
        "description": f"{jira_event[ISSUE_NUMBER_KEY]}: {jira_event[ISSUE_TITLE_KEY]}\n\n{jira_event[WORKLOG_DESCRIPTION_KEY]}\n\n[JIRA:{jira_event[WORKLOG_ID_KEY]}]"
    }


def update_event(caldav_event, jira_event):
    props = create_event_properties(jira_event)
    for key, val in props.items():
        getattr(caldav_event.vobject_instance.vevent, key).value = val
    caldav_event.save()


def find_matching_caldav_event(jira_event, caldav_events):
    for e in caldav_events:
        alldata = "".join(e.data.split())
        match = WORKLOG_ID_REGEX.search(alldata)
        if match:
            existing_id = match.group(1)
            if existing_id == jira_event[WORKLOG_ID_KEY]:
                return e
    return None


def push_to_caldav(events, url, user, password, name, fromtime, totime, wipe):
    with caldav.DAVClient(
        url=url,
        username=user,
        password=password,
    ) as client:
        p = client.principal()
        calendars = p.calendars()
        calendar = next(iter([c for c in calendars if c.name == name]))

        calendar_events = calendar.search(
            start=fromtime,
            end=totime,
            event=True,
            expand=False,
        )

        if wipe:
            for e in calendar_events:
                e.delete()
            calendar_events = []

        for event in events:
            c = find_matching_caldav_event(event, calendar_events)
            if c:
                update_event(c, event)
            else:
                calendar.save_event(**create_event_properties(event))


def main(opts):
    today = (datetime.date.today() + datetime.timedelta(days=1))
    past = today - datetime.timedelta(days=opts.days)
    today_timestamp = int(today.strftime("%s")) * 1000 # it's milliseconds
    past_timestamp = int(past.strftime("%s")) * 1000

    csv_text = get_worklogs(opts.token, opts.reportfilter, past_timestamp, today_timestamp, opts.jira)
    events = parse_csv(csv_text)

    push_to_caldav(events, opts.url, opts.user, opts.password, opts.calendar, past, today, opts.wipe)


if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-t', '--token', dest='token', type='string', help="Jira account token")
    parser.add_option('-j', '--jira-domain', dest='jira', type='string', help="JIRA domain")
    parser.add_option('-r', '--report-filter', dest='reportfilter', type='string', default="report-filter.json", help="Json file with your JIRA report filter definition")
    parser.add_option('-c', '--caldav-host', dest='url', type='string', help="CalDAV host")
    parser.add_option('-u', '--caldav-user', dest='user', type='string', help="CalDAV user")
    parser.add_option('-p', '--caldav-pass', dest='password', type='string', help="CalDAV password")
    parser.add_option('-n', '--calendar-name', dest='calendar', type='string', help="CalDAV calendar name")
    parser.add_option('-d', '--days', dest='days', type='int', help="How many days to go back in time", default=DAYS_TO_PROCESS)
    parser.add_option('-w', '--wipe', dest='wipe', action='store_true', help="If set, remove all existing events within time range from target calendar", default=False)

    (opts, args) = parser.parse_args()
    main(opts)
