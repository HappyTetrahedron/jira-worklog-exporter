# JIRA worklog exporter
This script exports a user's own work logs from JIRA and pushes them as calendar entries to a CalDAV server.

## Usage

```
./exporter.py -t JIRA_TOKEN -c CALDAV_URL -u CALDAV_USER -p CALDAV_PASSWORD -n CALENDAR_NAME -j JIRA_HOST [-r REPORT_FILTER_FILE] [-d DAYS_TO_PROCESS]
```

`JIRA_HOST` is the hostname of your JIRA instance, without protocol. E.g. `jira.mycompany.com`

The script will push your work logs from the last `DAYS_TO_PROCESS` days (default 3), including the current day.

**Note:** This script assumes that it has full purview over the given calendar and is free to mess with any events in there. It *will* delete existing events. It is thus strongly advisable to create a dedicated calendar for your JIRA work items on your CalDAV server.

### Custom JIRA filters

The filter to be used in JIRA to filter work-log items can be customized. By default, work logs are filtered to the current user. To customize the filter, my suggestion is to navigate to JIRA's worklog report page, configure the filters as desired, then use the browser's inspector to log network requests while exporting a CSV. **Make sure you include the `Start Time` and `Time Spent` attributes in your export.** In the generated `downloadWorklogDetailsReport` request, extract the `json` query parameter, URL-unencode it, and save the resulting JSON to a file. Pass this file as the report filter file using the `-r` parameter.