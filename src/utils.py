#!/usr/bin/env python3
import pytz
import datetime
import requests
import holidays
from pydantic import BaseModel
import os
from openai import OpenAI
import json

class TranslationOutput(BaseModel):
    translation: str

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

def translate(s, provider="e-infra"):
    match provider:
        case "e-infra":
            client = OpenAI(
                base_url="https://llm.ai.e-infra.cz/v1",
                api_key=os.getenv("E_INFRA_API_TOKEN")
            )

            response = client.chat.completions.create(
                model="mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at structured data extraction.",
                    },
                    {"role": "user", "content": "Translate the following dish name from Czech to English. Write your output as a json: `{{\"translation\": \"...\"}}`\n\n" + s}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "place-menu-description",
                        "schema": TranslationOutput.model_json_schema()
                    },
                },
            )

            try:
                text = response.choices[0].message.content
                return json.loads(text)["translation"]
            except Exception:
                return s

        case "lindat":
            url = "https://lindat.mff.cuni.cz/services/translation/api/v2/languages/"
            data = {
                "src" : "cs",
                "tgt" : "en",
                "input_text" : s
            }
            res = requests.post(url, data=data)
            return res.text.strip()