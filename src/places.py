#!/usr/bin/env python3
import requests
import html
import datetime
import textract
import logging
import re
import os
import dateparser
from bs4 import BeautifulSoup as bs
from collections import defaultdict
import json
import pprint

from src.llm_parsing import llm_parse_menu
from src.type_defs import Dish, Menu, Place, parse_menus_from_dict

import warnings

# Ignore dateparser warnings regarding pytz
warnings.filterwarnings(
    "ignore",
    message="The localize method is no longer necessary, as this time zone supports the fold attribute",
)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class MenzaTroja(Place):
    def __init__(self):
        super().__init__()
        self.name = "Menza Troja"
        self.menza_id = 17
        self.session_start_url = "https://kam-septim-fe.is.cuni.cz/webcarecanteenapiweb/core/1.0/sessionStart"
        self.menu_url_template = "https://kam-septim-fe.is.cuni.cz/webcarecanteenapiweb/canteen/1.0/menuBoard?canteenIds={}&from={}&to={}"
        self.url = (
            f"https://kam-septim-fe.is.cuni.cz/menu?view=day&canteen={self.menza_id}"
        )
        self.tab_id = "menza"

    def fetch_menus(self):
        session_start_response = requests.post(self.session_start_url)
        if session_start_response.status_code != 200:
            logger.error(
                f"Failed to start session for {self.name}! Status code: {session_start_response.status_code}"
            )
            return False

        session_token = session_start_response.json().get("sessionToken")
        if not session_token:
            logger.error(
                f"Failed to start session for {self.name}! No session token received."
            )
            return False

        # Prague timezone
        date = datetime.datetime.now(
            tz=datetime.timezone(datetime.timedelta(hours=2))
        ).date()
        date_string = date.strftime("%Y-%m-%d")
        menu_url = self.menu_url_template.format(
            self.menza_id, date_string, date_string
        )
        menu_headers = {"X-SESSION-TOKEN": session_token}

        menu_response = requests.get(menu_url, headers=menu_headers)
        if menu_response.status_code != 200:
            logger.error(
                f"Failed to fetch menu for {self.name}! Status code: {menu_response.status_code}"
            )
            return False

        menu_data = menu_response.json()
        pprint.pprint(menu_data)

        meals = menu_data[0].get("menu", [])

        soups = []
        dishes = []
        for meal in meals:
            if meal.get("group") == "Polévka":
                dish = Dish(
                    meal.get("product", {}).get("name", ""),
                    type="soup",
                    price=f"{meal.get('price', 0)} ({meal.get('otherPrices', [])[0].get('price', 0)})",
                    logger=logger,
                )
                soups.append(dish)
            else:
                dish = Dish(
                    meal.get("product", {}).get("name", ""),
                    price=f"{meal.get('price', 0)} ({meal.get('otherPrices', [])[0].get('price', 0)})",
                    logger=logger,
                )
                dishes.append(dish)

        menu = Menu(dishes, soups=soups, date=date, place=self.name, logger=logger)

        self.menus = [menu]
        return True


class BufetTroja(Place):
    def __init__(self):
        super().__init__()
        self.name = "Bufet Troja"
        self.url = "https://aurora.troja.mff.cuni.cz/pavlu/bufet.pdf"
        self.tab_id = "bufet"

    def fetch_menus(self):
        pdf = requests.get(self.url, timeout=20)
        if pdf.status_code != 200:
            logger.error(
                f"Failed to fetch menu for {self.name}! Status code: {pdf.status_code}"
            )
            return False

        with open("bufet_tmp.pdf", "wb") as f:
            f.write(pdf.content)

        text = textract.process("bufet_tmp.pdf", method="pdftotext", layout=True)
        text = text.decode("utf-8")

        try:
            menu = json.loads(llm_parse_menu(text, place_name=self.name))
            self.menus = parse_menus_from_dict(menu, logger=logger)
        except Exception as e:
            logger.exception("LLM parsing failed for Bufet Troja!")
            logger.exception(e)
            return False

        return True


class BufetTrojaOld(Place):
    def __init__(self):
        super().__init__()
        self.name = "Bufet Troja"
        self.url = "https://aurora.troja.mff.cuni.cz/pavlu/bufet.pdf"
        self.tab_id = "bufet"
        self._week_days = ["pondělí", "úterý", "středa", "čtvrtek", "pátek"]

    def _has_food(self, s):
        return re.search(r"\s*(\d){2,4}\s*gr ", s)  # contains weight

    def _has_price(self, s):
        return re.search(r"\s\d{2,3},-", s)

    def _has_date(self, s):
        return re.search(r"\d{1,2}\.\s*\d{1,2}\.\s*\d{4}", s)

    def _get_monday_date(self, s):
        date_friday = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})[^\d]*$", s)
        date_friday = datetime.date(
            int(date_friday.group(3)),
            int(date_friday.group(2)),
            int(date_friday.group(1)),
        )
        return date_friday - datetime.timedelta(days=4)

    def _get_weekday(self, s):
        for day in self._week_days:
            if day in s.lower():
                return day
        return None

    def _has_soup(self, s):
        return "polévka" in s.lower()

    def _is_last(self, s):
        return "Dále nabízíme" in s

    def fetch_menus(self):
        pdf = requests.get(self.url, timeout=20)

        if pdf.status_code != 200:
            logger.error(
                f"Failed to fetch menu for {self.name}! Status code: {pdf.status_code}"
            )
            return False

        with open("bufet_tmp.pdf", "wb") as f:
            f.write(pdf.content)

        text = textract.process("bufet_tmp.pdf", method="pdftotext", layout=True)
        text = text.decode("utf-8")
        text = text.split("\n")
        menus = []
        m = None

        monday_date = datetime.datetime.fromtimestamp(0)  # fallback
        food_first_line = ""  # buffer for food names that are split into multiple lines

        for i in text:
            if self._has_date(i):
                monday_date = self._get_monday_date(i)
                continue

            extracted_weekday = self._get_weekday(i)
            if extracted_weekday is not None:
                if m is not None:
                    menus.append(m)

                menu_date = monday_date + datetime.timedelta(
                    days=self._week_days.index(extracted_weekday)
                )
                m = Menu(
                    dishes=[], soups=[], date=menu_date, place=self.name, logger=logger
                )

            if self._has_soup(i) and m is not None:
                soup = re.search(
                    r"(polévka [\w\s,]*\w)\s+\d+,-", i, flags=re.IGNORECASE
                ).group(1)
                price = re.search("(\d+),-\s*$", i)

                if price:
                    price = price.group(1)

                if soup:
                    soup = Dish(
                        soup.strip().capitalize(),
                        price=price,
                        type="soup",
                        logger=logger,
                    )
                    m.soups.append(soup)

            if self._has_food(i) and m is not None:
                dish = re.search(
                    r"\d+\s*gr\s*([^\d]*[^\W\d])", i, flags=re.IGNORECASE
                ).group(1)

                if self._has_price(i):
                    price = re.search("(\d+),-\s*$", i)

                    dish = Dish(
                        dish.strip().capitalize(), price=price.group(1), logger=logger
                    )
                    m.dishes.append(dish)

                else:  # food was probably split into multiple lines
                    food_first_line = dish.strip()
            elif food_first_line != "" and self._has_price(i):
                price = re.search("(\d+),-\s*$", i)
                food_second_line = re.search(
                    r"([^\d]*[^\W\d])\s*\d+,-\s*$", i, flags=re.IGNORECASE
                ).group(1)

                dish = Dish(
                    (food_first_line + " " + food_second_line.strip()).capitalize(),
                    price=price.group(1),
                    logger=logger,
                )
                m.dishes.append(dish)
                food_first_line = ""

            if self._is_last(i):
                break

        menus.append(m)
        os.remove("bufet_tmp.pdf")
        self.menus = menus
        return True


class CastleRestaurant(Place):
    def __init__(self):
        super().__init__()
        self.name = "Castle Restaurant"
        # the menu fetched by JS at https://www.castle-restaurant.cz/poledni-menu
        self.url = "https://www.prazskejrej.cz/menu-na-web/castle-residence"
        self.tab_id = "castle"

    def fetch_menus(self):
        rss = requests.get(self.url, timeout=20)
        if rss.status_code != 200:
            logger.error(
                f"Failed to fetch menu for {self.name}! Status code: {rss.status_code}"
            )
            return False
        rss = rss.content.decode("utf-8")
        html = bs(rss, "lxml")
        menus = []

        for day in html.find_all("div", {"class": "food-sub-section"})[:5]:
            menu_date = day.find("h3").text.strip()
            menu_date = re.sub(r"[^\d\.]", "", menu_date)

            try:
                menu_date = datetime.datetime.strptime(menu_date, "%d.%m.%Y").date()

                dishes = day.find_all("div", {"class": "row pb-3 pt-2 py-md-1"})
                dishes = [x.text.strip() for x in dishes]
                dishes = [
                    re.sub(r"\s*[-–—]{0,1}\s*(\d\w{0,1},{0,1}\s*){1,9}\s*\t", "", x)
                    for x in dishes
                ]  # remove alergens
                dishes = [re.search(r"([^\d]*)?\s*(\d+) Kč\s*$", x) for x in dishes]
                soup_name = (
                    dishes[0].group(1).replace(" –", "")
                )  # remove en dash which get improperly translated
                soup_name = soup_name[0] + soup_name[1:].lower()
                soups = [
                    Dish(
                        soup_name.strip(),
                        price=dishes[0].group(2),
                        type="soup",
                        logger=logger,
                    )
                ]
                dishes = [
                    Dish(x.group(1).strip(), price=x.group(2), logger=logger)
                    for x in dishes[1:]
                ]

                m = Menu(
                    dishes, soups=soups, date=menu_date, place=self.name, logger=logger
                )
                menus.append(m)
            except Exception as e:
                logger.exception(e)
                continue

        self.menus = menus
        return True


if __name__ == "__main__":
    today = datetime.datetime.now()
    place = BufetTroja()
    place = MenzaTroja()
    place = CastleRestaurant()
    place.fetch_menus()
    print("\n".join([str(menu) for menu in place.get_menus()]))
