import os
import requests
import json
import socket
import logging
import datetime
from datetime import timedelta
from flask import Flask, render_template, jsonify, request, url_for
from collections import defaultdict
from slack_sdk import WebClient

from .places import Menu, Dish
from .places import MenzaTroja, BufetTroja, CastleRestaurant

from flask_apscheduler import APScheduler

scheduler = APScheduler()
app = Flask(__name__)

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO, datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

greetings = ["hi", "hello", "hello there", "hey"]

SLACK_SIGNING_SECRET = os.environ['SLACK_SIGNING_SECRET']
slack_token = os.environ['SLACK_BOT_TOKEN']
# VERIFICATION_TOKEN = os.environ['VERIFICATION_TOKEN']

#instantiating slack client
slack_client = WebClient(slack_token)

# # An example of one of your Flask app's routes
# @app.route("/")
# def event_hook(request):
#     json_dict = json.loads(request.body.decode("utf-8"))
#     # if json_dict["token"] != VERIFICATION_TOKEN:
#     #     return {"status": 403}

#     if "type" in json_dict:
#         if json_dict["type"] == "url_verification":
#             response_dict = {"challenge": json_dict["challenge"]}
#             return response_dict
#     return {"status": 500}
#     return

# slack_events_adapter = SlackEventAdapter(
#     SLACK_SIGNING_SECRET, "/slack/events", app
# )  


# @slack_events_adapter.on("app_mention")
# def handle_message(event_data):
#     def send_reply(value):
#         event_data = value
#         message = event_data["event"]
#         if message.get("subtype") is None:
#             command = message.get("text")
#             channel_id = message["channel"]
#             if any(item in command.lower() for item in greetings):
#                 message = (
#                     "Hello <@%s>! :tada:"
#                     % message["user"]  # noqa
#                 )
#                 slack_client.chat_postMessage(channel=channel_id, text=message)
#     thread = Thread(target=send_reply, kwargs={"value": event_data})
#     thread.start()
#     return Response(status=200)

def fetch_all():
    all_menus = []

    for place_cls in app.config['places']:
        place = place_cls()
        try:
            logger.info(f"Fetching data for {place.name}")
            menu = place.get_menu()
            all_menus.append(menu)
        except Exception as e:
            logger.error(f"Error when fetching data for {place.name}")
            logger.exception(e)
    
    return all_menus


def process_overview(menus, date):
    overview = []    

    for place in menus:
        for menu in place:  
            if menu.date == date:
                menu.translate()   
                overview.append({
                    "name" : menu.place,
                    "soups" : [s.__dict__ for s in menu.soups],
                    "dishes" : [d.__dict__ for d in menu.dishes]
                })

    overview.sort(key=lambda x: x["name"])
    return overview

def get_overview():
    return get_overview_from_cache()
    # now = datetime.datetime.now() 

    # if not is_cache_valid(now):
    #     return get_overview_full()
    # else:
    #     return get_overview_from_cache()


# def is_cache_valid(time):
#     cache_update_time = app.config['args'].cache_update_time

#     return app.config['last_update'] is not None \
#             and time - app.config['last_update'] < timedelta(minutes=cache_update_time)

def get_overview_from_cache():
    return app.config['overview']

@app.before_first_request
def reload_overview():
    now = datetime.datetime.now() 

    menus = fetch_all()
    overview = process_overview(menus, now.date())
    save_overview_to_cache(overview)


def save_overview_to_cache(overview):
    app.config['overview'] = overview
    app.config['last_update'] = datetime.datetime.now()


@app.route('/', methods=['GET', 'POST'])
def index():
    logger.info(f"Page loaded")

    now = datetime.datetime.now() 
    overview = get_overview()
    last_update = app.config['last_update'].strftime("%A %d %b %Y %H:%M:%S")
    
    return render_template('index.html', 
        date=now.strftime("%A %d %B %Y"), 
        overview=overview,
        last_update=last_update
    )

def create_app(*args, **kwargs):
    app.config['places'] = [
        MenzaTroja,
        BufetTroja,
        CastleRestaurant
    ]
    app.config['overview'] = None
    app.config['last_update'] = None

    scheduler.add_job(id='fetch', func=reload_overview, trigger="cron", hour=7, replace_existing=True)
    scheduler.start()

    # reload_overview()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)