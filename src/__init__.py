import os
import requests
import shelve
import json
import logging
import datetime
import random
import socket
from datetime import timedelta

from flask import Flask, render_template, jsonify
from slack_sdk import WebClient
from flask_apscheduler import APScheduler


# from apscheduler.schedulers.blocking import BlockingScheduler
from src.places import MenzaTroja, BufetTroja, CastleRestaurant

scheduler = APScheduler()

# sched = BlockingScheduler()
app = Flask(__name__)

app.config['places'] = [
        MenzaTroja,
        BufetTroja,
        CastleRestaurant
    ]
app.config['db'] = "data.db"


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

        for menu in place.get_menus():
            # translating is time-consuming, for now translate only food for the current day
            if menu.date == datetime.datetime.now().date():
                menu.translate()

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
                o["soups"] = [s.__dict__ for s in menu.soups]
                o["dishes"] = [d.__dict__ for d in menu.dishes]
                break
        overview.append(o)

    return overview

# heroku has a troublesome tendency of shutting down the app after 30 minutes
# we thus have to make all the settings persistent
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
# @sched.scheduled_job('fetch', hour=5, day_of_week="mon-fri")
def reload_places(force=False):
    # to ensure that the cache is reloaded once per day (not setting "24" to avoid second-like delays)
    cache_age = get_cache_age()
    
    if not force and cache_age < timedelta(hours=23):
        logger.info(f"Last update {cache_age} ago, not reloading")
        return

    logger.info(f"Reloading places")
    places = fetch_all_places()
    save_var("places", places)
    save_var("last_update", datetime.datetime.now())

    return success()


def get_cache_age():
    now = datetime.datetime.now()
    last_update = get_var('last_update')
    if not last_update:
        return now - datetime.datetime.min

    return now - last_update


# @sched.scheduled_job('dotd', hour=6, day_of_week="mon-fri")
def generate_dish_of_the_day():
    now = datetime.datetime.now()

    overview = get_overview_for_day(now.date())
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
    now = datetime.datetime.now()

    reload_places()
    overview = get_overview_for_day(now.date())
    last_update = get_var('last_update').strftime("%d %b %Y %H:%M:%S")
    
    return render_template('index.html', 
        date=now, 
        overview=overview,
        last_update=last_update,
        dotd=get_dish_of_the_day()
    )


@app.route('/test_invite', methods=['GET', 'POST'])
def test_invite():
    send_lunch_invite()
    return success()

@app.route('/test_overview', methods=['GET', 'POST'])
def test_overview():
    now = datetime.datetime.now()
    overview = get_overview_for_day(now.date())

    return overview, 200

@app.route('/test_places', methods=['GET', 'POST'])
def test_places():
    places = app.config["places"]
    return str([p.__dict__ for p in places]), 200

@app.route('/test_force_reload', methods=['GET', 'POST'])
def test_force_reload():
    reload_places(force=True)
    return success()


# @sched.scheduled_job('invite', hour=9, day_of_week="mon-fri")
def send_lunch_invite():
    dotd = get_dish_of_the_day()
    place_name = dotd["place"]
    dish_name = dotd["dish"]
    
    now = datetime.datetime.now()
    now_str = now.strftime("%Y-%m-%d")

    message = [
        {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": f"Today on the menu:\n🧑‍🍳 *{dish_name}* at *{place_name}*\n\nFull menu: https://tiny.cc/troja-lunch\n\nWho's going for lunch? 🙂"
            },
            "accessory": {
                "type": "image",
                "image_url": f"http://ufallab.ms.mff.cuni.cz/~kasner/cfm/{now_str}.png",
                "alt_text": "dish of the day"
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_The image was generated by Stable Diffusion. The dish name was translated by CUBBITT._"
            }
        }
    ]
    post_message(message)



def post_message(m):
    try:
        response = slack_client.chat_postMessage(
            channel="UV2PNNLE6",
            blocks=m
        )
    except SlackApiError as e:
        logger.error(e.response["error"])
        logger.exception(e)



def create_app(*args, **kwargs):

    # sched.start()
    # app.config['overview'] = None
    # app.config['last_update'] = None

    # shift two hours earlier to account for server time
    scheduler.add_job(id='fetch', func=reload_places, trigger="cron", hour=5, day_of_week="mon,tue,wed,thu,fri")
    scheduler.add_job(id='dotd', func=generate_dish_of_the_day, trigger="cron", hour=6, day_of_week="mon,tue,wed,thu,fri")
    scheduler.add_job(id='invite', func=send_lunch_invite, trigger="cron", hour=9, day_of_week="mon,tue,wed,thu,fri")
    scheduler.start()

    if socket.gethostname() == "rel2text":
        app.config["APPLICATION_ROOT"] = "/rel2text"
    
    random.seed(42)
    # reload_places()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)