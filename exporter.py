#!/usr/bin/env python3
import requests
import json
import datetime
import csv
import io
from icalendar import Calendar, Event, vText
import caldav

REPORT_URL = 'https://{}/rest/jttp-rest/latest/download-report/downloadWorklogDetailsReportAsCSV'
QUERY_PARAMS = {
    "worklogTimeExport": "seconds"
}

START_TIME_FORMAT = '%d. %b %Y %H:%M'

START_TIME_KEY = "Start Time"
TIME_SPENT_KEY = "Time Spent (s)"
WORKLOG_DESCRIPTION_KEY = "Worklog Description"
ISSUE_NUMBER_KEY = "Issue Key"
ISSUE_TITLE_KEY = "Issue Summary"

KEYS = [
    START_TIME_KEY,
    TIME_SPENT_KEY,
    WORKLOG_DESCRIPTION_KEY,
    ISSUE_NUMBER_KEY,
    ISSUE_TITLE_KEY
]

DAYS_TO_PROCESS = 3

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


def to_ical(events):
    cal = Calendar()

    for event in events:
        start_time = datetime.datetime.strptime(event[START_TIME_KEY], START_TIME_FORMAT)
        seconds = int(event[TIME_SPENT_KEY])
        end_time = start_time + datetime.timedelta(seconds=seconds)

        cal_event = Event()
        cal_event.add('summary', f'{event[ISSUE_NUMBER_KEY]}: {event[WORKLOG_DESCRIPTION_KEY]}')
        cal_event.add('dtstart', start_time), 
        cal_event.add('dtend', end_time), 
        cal_event['description'] = vText(f"{event[ISSUE_NUMBER_KEY]}: {event[ISSUE_TITLE_KEY]}")
        cal.add_component(cal_event)
    
    return cal.to_ical().decode("utf-8")


def push_to_caldav(events, url, user, password, name, fromtime, totime):
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

        for e in calendar_events:
            e.delete()
        for event in events:
            short_desc = event[WORKLOG_DESCRIPTION_KEY].splitlines()[0]
            start_time = datetime.datetime.strptime(event[START_TIME_KEY], START_TIME_FORMAT)
            seconds = int(event[TIME_SPENT_KEY])
            end_time = start_time + datetime.timedelta(seconds=seconds)
            summary = f'{event[ISSUE_NUMBER_KEY]}: {short_desc}' \
                if event[ISSUE_NUMBER_KEY] not in ["ALDE-2", "ALDE-3"] \
                else f'{short_desc}'
            calendar.save_event(
                dtstart=start_time,
                dtend=end_time,
                summary=summary,
                description=f"{event[ISSUE_NUMBER_KEY]}: {event[ISSUE_TITLE_KEY]}\n\n{event[WORKLOG_DESCRIPTION_KEY]}"
            )


def main(opts):
    today = (datetime.date.today() + datetime.timedelta(days=1))
    past = today - datetime.timedelta(days=opts.days)
    today_timestamp = int(today.strftime("%s")) * 1000 # it's milliseconds
    past_timestamp = int(past.strftime("%s")) * 1000

    csv_text = get_worklogs(opts.token, opts.reportfilter, past_timestamp, today_timestamp, opts.jira)
    events = parse_csv(csv_text)

    push_to_caldav(events, opts.url, opts.user, opts.password, opts.calendar, past, today)


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

    (opts, args) = parser.parse_args()
    main(opts)