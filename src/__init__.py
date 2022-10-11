import os
import requests
import json
import logging
import datetime
import random
from datetime import timedelta

from flask import Flask, render_template, jsonify
from slack_sdk import WebClient
from flask_apscheduler import APScheduler

from .places import MenzaTroja, BufetTroja, CastleRestaurant

scheduler = APScheduler()
app = Flask(__name__)

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
        places.append(place)
    
    return places


def get_overview_for_day(date):
    places = app.config["places"]
    overview = []

    for place in places:
        o = {
            "name" : place.name,
            "tab_id" : place.tab_id,
            "soups" : [],
            "dishes" : []
        }
        for menu in place.get_menus():
            if menu.date == date:
                menu.translate()
                o["soups"] = [s.__dict__ for s in menu.soups]
                o["dishes"] = [d.__dict__ for d in menu.dishes]
                break
        overview.append(o)

    return overview


@app.before_first_request
def reload_places():
    # to ensure that the cache is reloaded once per day (not setting "24" to avoid second-like delays)
    if get_cache_age() < timedelta(hours=23):
        return

    places = fetch_all_places()
    app.config["places"] = places
    app.config['last_update'] = datetime.datetime.now()


def get_cache_age():
    now = datetime.datetime.now()
    if not app.config['last_update']:
        return now - datetime.datetime.min

    return now - app.config['last_update']


def generate_dish_of_the_day():
    now = datetime.datetime.now()

    overview = get_overview_for_day(now.date())
    places_with_dishes = [p for p in overview if p["dishes"]]

    if not places_with_dishes:
        app.config["dish_of_the_day"] = {
            "place" : "The Restaurant at the End of the Universe",
            "dish" : "Ameglian Major Cow"
        }
        return

    place = random.choice(places_with_dishes)
    place_name = place["name"]

    dish = random.choice(place["dishes"])
    dish_name = dish["name_en"] or dish["name"]

    dotd = {
        "place" : place_name,
        "dish" : dish_name
    }
    app.config["dish_of_the_day"] = dotd
    logger.info(f"Generated dish of the day: {dish_name} at {place_name}")

    return dotd


def get_dish_of_the_day():
    dotd = app.config.get("dish_of_the_day")

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

    # the overview will be cached at this point either due to the @app.before_first_request decorator
    # or due to the regular scheduler
    overview = get_overview_for_day(now.date())
    last_update = app.config['last_update'].strftime("%d %b %Y %H:%M:%S")
    
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
              "text": f"Dish of the day:\n🧑‍🍳 *{dish_name}* at *{place_name}*\nFull menu: https://troja-lunch.herokuapp.com/\n\nWho's going for lunch?"
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
    app.config['places'] = [
        MenzaTroja,
        BufetTroja,
        CastleRestaurant
    ]
    app.config['overview'] = None
    app.config['last_update'] = None

    # heroku operates in GMT, hours are shifted to account for that
    scheduler.add_job(id='fetch', func=reload_places, trigger="cron", hour=5, day_of_week="mon,tue,wed,thu,fri")
    scheduler.add_job(id='dotd', func=generate_dish_of_the_day, trigger="cron", hour=6, day_of_week="mon,tue,wed,thu,fri")
    scheduler.add_job(id='invite', func=send_lunch_invite, trigger="cron", hour=9, day_of_week="mon,tue,wed,thu,fri")
    scheduler.start()
    
    random.seed(42)
    # reload_places()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)