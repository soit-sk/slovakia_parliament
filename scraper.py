#!/usr/bin/python
# -*- coding: utf8 -*-

post_params_txt = """__EVENTARGUMENT=
__EVENTTARGET=
__LASTFOCUS=
__SCROLLPOSITIONX=0
__SCROLLPOSITIONY=342
_searchModule=schodze/cpt
_searchText=
_sectionLayoutContainer$ctl00$_calendarApp=nrdi
_sectionLayoutContainer$ctl00$_calendarLang=
_sectionLayoutContainer$ctl00$_calendarMonth=7
_sectionLayoutContainer$ctl00$_calendarYear=2014
_sectionLayoutContainer$ctl00$_monthSelector=7
_sectionLayoutContainer$ctl00$_yearSelector=2014
_sectionLayoutContainer$ctl01$_dateFrom=
_sectionLayoutContainer$ctl01$_dateFrom$dateInput=
_sectionLayoutContainer$ctl01$_dateTo=
_sectionLayoutContainer$ctl01$_dateTo$dateInput=
_sectionLayoutContainer$ctl01$_meetingNr=
_sectionLayoutContainer$ctl01$_personKey=
_sectionLayoutContainer$ctl01$_search=Vyhľadať
_sectionLayoutContainer$ctl01$_searchIn=new
_sectionLayoutContainer$ctl01$_termNr=6
_sectionLayoutContainer$ctl01$_text=
_sectionLayoutContainer_ctl01__dateFrom_ClientState={"minDateStr":"1/1/1900 0:0:0","maxDateStr":"12/31/2099 0:0:0"}
_sectionLayoutContainer_ctl01__dateFrom_calendar_AD=[[1900,1,1],[2099,12,30],[2014,7,13]]
_sectionLayoutContainer_ctl01__dateFrom_calendar_SD=[]
_sectionLayoutContainer_ctl01__dateFrom_dateInput_ClientState={"enabled":true,"emptyMessage":"","minDateStr":"1/1/1900 0:0:0","maxDateStr":"12/31/2099 0:0:0"}
_sectionLayoutContainer_ctl01__dateFrom_dateInput_text=
_sectionLayoutContainer_ctl01__dateTo_ClientState={"minDateStr":"1/1/1900 0:0:0","maxDateStr":"12/31/2099 0:0:0"}
_sectionLayoutContainer_ctl01__dateTo_calendar_AD=[[1900,1,1],[2099,12,30],[2014,7,13]]
_sectionLayoutContainer_ctl01__dateTo_calendar_SD=[]
_sectionLayoutContainer_ctl01__dateTo_dateInput_ClientState={"enabled":true,"emptyMessage":"","minDateStr":"1/1/1900 0:0:0","maxDateStr":"12/31/2099 0:0:0"}
_sectionLayoutContainer_ctl01__dateTo_dateInput_text=
_sectionLayoutContainer_ctl01__meetingNr_ClientState={"enabled":true,"emptyMessage":"","minValue":1,"maxValue":200}
_sectionLayoutContainer_ctl01__meetingNr_text="""

import fileinput
import itertools
import requests
import scraperwiki
from bs4 import BeautifulSoup
from datetime import datetime

url = 'http://www.nrsr.sk/web/default.aspx?sid=schodze%2frozprava'

def get_post_params():
    """
    Read HTTP POST parameters that we need to put to POST request.
    These were obtained through Firebug.
    """

    global post_params_txt

    d = dict()
    for line in post_params_txt.split('\n'):
        key, value = line.rstrip().split('=', 1)
        d[key] = value
    return d


def get_input_value(html, input_id):
    return html.body.find('input', attrs={'id': input_id}).attrs['value']


def get_term_numbers(html):
    attrs = {'id': '_sectionLayoutContainer_ctl01__termNr'}
    options = html.find('select', attrs=attrs).find_all('option')
    return [int(option.attrs['value']) for option in options]


def set_validation_params(params, html):
    """
    These need to be set for every POST request.
    """
    params['__VIEWSTATE'] = get_input_value(html, '__VIEWSTATE')
    params['__EVENTVALIDATION'] = get_input_value(html, '__EVENTVALIDATION')


def parse_html(html, term_nr):
    """
    Parse HTML for a result page and return list of dicts with data that
    can be saved to the scraperwiki sqlite.
    """

    # Get table rows. Class is used to highlight alternating rows, so
    # get both of them.
    rows = html.body.find_all('tr', attrs={'class': 'tab_zoznam_nalt'}) + \
           html.body.find_all('tr', attrs={'class': 'tab_zoznam_nonalt'})

    data_rows = []
    for row in rows:
        cols = row.find_all('td')

        data_row = {'term_nr': term_nr}

        # Meeting number, E.g.: '1.'
        data_row['meeting_number'] = int(cols[0].text.strip().rstrip('.'))

        # Date of the speech. E.g.: '4. 4. 2012'
        date = datetime.strptime(cols[1].text.strip(), "%d. %m. %Y").date()

        # Time of the speech. E.g.: '10:03:39 - 10:19:13'
        times = cols[2].text.strip().split('\n', 1)[0].split(' - ')
        times = [datetime.strptime(t, '%H:%M:%S').time() for t in times]

        # Now create datetime objects by combining date and times
        data_row['time_from'] = datetime.combine(date, times[0])
        data_row['time_to'] = datetime.combine(date, times[1])

        # Representative
        data_row['member'] = cols[3].find('strong').text.strip()

        # HTTP links
        links = cols[4].find_all('a')
        data_row['speech_video'] = links[0].attrs['href']
        data_row['proceedings_video'] = links[1].attrs['href']
        data_row['transcript'] = links[2].attrs['href']

        data_rows.append(data_row)

    return data_rows

def save_results(data_rows, nr):
    if len(data_rows) != 20:
        print "Got {} rows for page #{}".format(len(data_rows), nr)
        print data_rows
    if len(data_rows) == 0:
        return
    for row in data_rows:
        scraperwiki.sqlite.save(unique_keys=["speech_video"], data=row)

if __name__ == "__main__":
    post_params = get_post_params()
    session = requests.session()

    # Initial GET request to get __VIEWSTATE and __EVENTVALIDATION
    response = session.get(url)
    if not response.ok:
        raise Exception("Failed to fetch %s" % url)
    html = BeautifulSoup(response.text)
    # Electoral term numbers.
    term_numbers = get_term_numbers(html)

    for term_nr in term_numbers:
        # Read POST parameters and set term number.
        post_params = get_post_params()
        post_params['_sectionLayoutContainer$ctl01$_termNr'] = term_nr

        # First search request.
        params = dict(post_params)
        set_validation_params(params, html)
        response = session.post(url, data=params)
        if not response.ok:
            raise Exception("Failed to fetch %s" % url)
        html = BeautifulSoup(response.text)
        save_results(parse_html(html, term_nr), 1)

        for page_nr in itertools.count(2):
            # Set basic POST params.
            params = dict(post_params)
            set_validation_params(params, html)

            # Specify result page number.
            params['__EVENTARGUMENT'] = "Page${}".format(page_nr)
            params['__EVENTTARGET'] = '_sectionLayoutContainer$ctl01$_newDebate'

            # This is only useful for first request, paging doesn't work with it.
            del params['_sectionLayoutContainer$ctl01$_search']

            # Make a POST request.
            response = session.post(url, data=params)
            if not response.ok:
                raise Exception("Failed to fetch %s", url)

            # Parse and save data.
            html = BeautifulSoup(response.text)
            data = parse_html(html, term_nr)
            save_results(data, page_nr)

            # TODO:
            # save page_nr to db variable, so we can continue from previous run
            if not data:
                print "No data for page #{}, ending".format(page_nr)
                return
