#!/usr/bin/env python3

import requests

def translate(s):
    url = "https://lindat.mff.cuni.cz/services/translation/api/v2/languages/"
    data = {
        "src" : "cs",
        "tgt" : "en",
        "input_text" : s
    }
    res = requests.post(url, data=data)
    return res.text.strip()

if __name__ == "__main__":
    translate("svíčková")