#!/usr/bin/env python3
import pytz
import datetime
import requests
import holidays

def timezone():
    return 'Europe/Prague'

def tz():
    return pytz.timezone(timezone())

def now():
    return datetime.datetime.now(tz())

def today():
    return now().date()

def is_holiday():
    return today() in holidays.CZ()

def translate(s):
    url = "https://lindat.mff.cuni.cz/services/translation/api/v2/languages/"
    data = {
        "src" : "cs",
        "tgt" : "en",
        "input_text" : s
    }
    res = requests.post(url, data=data)
    return res.text.strip()