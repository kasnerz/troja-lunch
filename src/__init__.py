import os
import requests
import shelve
import json
import logging
import datetime
import random

from datetime import timedelta
from src.utils import now, today, timezone, is_holiday

from flask import Flask, render_template, jsonify, url_for
from slack_sdk import WebClient
from flask_apscheduler import APScheduler

from apscheduler.schedulers.background import BackgroundScheduler

from src.places import MenzaTroja, BufetTroja, CastleRestaurant


app = Flask(__name__)

app.config['places'] = [
        MenzaTroja,
        BufetTroja,
        CastleRestaurant
    ]
app.config['channels'] = {
    "user" : "UV2PNNLE6",
    "default" : "C014KEBJA1M"
}
app.config['db'] = "data.db"

# scheduler = APScheduler(timezone=app.config['timezone'])
scheduler = BackgroundScheduler(timezone=timezone())

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO, datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

SLACK_SIGNING_SECRET = os.environ['SLACK_SIGNING_SECRET']
slack_token = os.environ['SLACK_BOT_TOKEN']
slack_client = WebClient(slack_token)


def success():
    resp = jsonify(success=True)
    return resp

def fetch_all_places():
    places = []

    for place_cls in app.config['places']:
        place = place_cls()
        try:
            logger.info(f"Fetching data for {place.name}")
            place.fetch_menus()
        except Exception as e:
            logger.error(f"Error when fetching data for {place.name}")
            logger.exception(e)

        try:
            for menu in place.get_menus():
                # translating is time-consuming, for now translate only dishes for the current day
                if menu.date == today():
                    menu.translate()
        except Exception as e:
            logger.error(f"Error when translating menu for {place.name}")
            logger.exception(e)

        places.append(place)
    
    return places


def get_overview_for_day(date):
    places = get_var("places")
    overview = []

    for place in places:
        o = {
            "name" : place.name,
            "tab_id" : place.tab_id,
            "url" : place.url,
            "soups" : [],
            "dishes" : []
        }
        for menu in place.get_menus():
            if menu.date == date:
                if not menu.is_translated:
                    logger.warning("Menu was not translated, translating now...")
                    menu.translate()

                o["soups"] = [s.__dict__ for s in menu.soups]
                o["dishes"] = [d.__dict__ for d in menu.dishes]
                break
        overview.append(o)

    return overview

def save_var(key, val):
    with shelve.open(app.config["db"]) as db:
        db[key] = val

    
def get_var(key):
    with shelve.open(app.config['db']) as db:
        if not key in db:
            return None

        return db[key]

@app.route('/delete_config', methods=['GET'])
def delete_config():
    if os.path.exists(app.config['db']):
        os.remove(app.config['db'])

    return success()


@app.before_first_request
def reload_places(force=False):
    cache_age = get_cache_age()
    
    if not force and cache_age and cache_age < timedelta(hours=12):
        logger.info(f"Last update {cache_age} ago, not reloading")
        return

    logger.info(f"Reloading places")
    places = fetch_all_places()
    save_var("places", places)
    save_var("last_update", now())

    return success()


def get_cache_age():
    now_time = now()
    last_update = get_var('last_update')

    if not last_update:
        return None

    return now_time - last_update


def generate_dish_of_the_day():
    overview = get_overview_for_day(today())
    places_with_dishes = [p for p in overview if p["dishes"]]

    if not places_with_dishes:
        save_var("dish_of_the_day", {
            "place" : "The Restaurant at the End of the Universe",
            "dish" : "Ameglian Major Cow"
        })
        return

    place = random.choice(places_with_dishes)
    place_name = place["name"]

    dish = random.choice(place["dishes"])
    dish_name = dish["name_en"] or dish["name"]

    dotd = {
        "place" : place_name,
        "dish" : dish_name
    }
    save_var("dish_of_the_day", dotd)
    logger.info(f"Generated dish of the day: {dish_name} at {place_name}")

    return dotd


def get_dish_of_the_day():
    dotd = get_var("dish_of_the_day")

    if not dotd:
        logger.warning("Dish of the day was not generated, generating now...")
        dotd = generate_dish_of_the_day()

    return dotd


@app.route('/dotd', methods=['GET'])
def dotd():
    dotd = get_dish_of_the_day()
    return dotd["dish"], 200


@app.route('/', methods=['GET', 'POST'])
def index():
    logger.info(f"Page loaded")
    reload_places()
    overview = get_overview_for_day(today())
    last_update = get_var('last_update').strftime("%d %b %Y %H:%M:%S")
    
    return render_template('index.html', 
        date=now(), 
        overview=overview,
        last_update=last_update,
        dotd=get_dish_of_the_day()
    )


@app.route('/test_invite', methods=['GET', 'POST'])
def test_invite():
    send_lunch_invite(channel="user")
    return success()

@app.route('/test_overview', methods=['GET', 'POST'])
def test_overview():
    overview = get_overview_for_day(today())

    return overview, 200

@app.route('/test_places', methods=['GET', 'POST'])
def test_places():
    places = app.config["places"]
    return str([p.__dict__ for p in places]), 200

@app.route('/test_force_reload', methods=['GET', 'POST'])
def test_force_reload():
    reload_places(force=True)
    return success()


def send_lunch_invite(channel="default"):
    if channel == "default" and is_holiday():
        return

    dotd = get_dish_of_the_day()
    place_name = dotd["place"]
    dish_name = dotd["dish"]
    
    now_str = now().strftime("%Y-%m-%d")

    message = [
        {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": f"Today on the <https://tiny.cc/troja-lunch|menu>:\n🧑‍🍳 *{dish_name}* at *{place_name}*\n\nWhere to go? 🍝 _Menza_  🌭 _Bufet_   🏰 _Castle_  🥕 _Elsewhere_\n"
            },
            "accessory": {
                "type": "image",
                "image_url": f"http://ufallab.ms.mff.cuni.cz/~kasner/troja-lunch/{now_str}.png",
                "alt_text": "dish of the day"
            }
        },
        {
			"type": "divider"
		}
    ]
    post_message(message, channel)



def post_message(m, channel="default"):
    try:
        response = slack_client.chat_postMessage(
            channel=app.config["channels"][channel],
            blocks=m
        )
    except SlackApiError as e:
        logger.error(e.response["error"])
        logger.exception(e)



def create_app(*args, **kwargs):
    scheduler.add_job(id='fetch', func=lambda: reload_places(force=True), trigger="cron", hour=7, day_of_week="mon,tue,wed,thu,fri")
    # for menus that are added later
    scheduler.add_job(id='fetch_extra', func=lambda: reload_places(force=True), trigger="cron", hour=10, day_of_week="mon,tue,wed,thu,fri")
    scheduler.add_job(id='dotd', func=generate_dish_of_the_day, trigger="cron", hour=8, day_of_week="mon,tue,wed,thu,fri")
    scheduler.add_job(id='invite', func=send_lunch_invite, trigger="cron", hour=11, day_of_week="mon,tue,wed,thu,fri")
    scheduler.start()

    random.seed(42)
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)