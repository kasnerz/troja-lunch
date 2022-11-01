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
from src.utils import translate

import warnings

# Ignore dateparser warnings regarding pytz
warnings.filterwarnings(
    "ignore",
    message="The localize method is no longer necessary, as this time zone supports the fold attribute",
)

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO, datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

class Place:
    def __init__(self):
        self.menus = []

    def get_menus(self):
        return self.menus

    def fetch_menus(self):
        raise NotImplementedError


class Menu:
    def __init__(self, dishes, soups, date=None, place=None):
        self.dishes = dishes
        self.soups = soups        # maybe not that beautiful
        self.date = date
        self.place = place
        self.is_translated = False
    
    def translate(self):
        logger.info(f"Translating menu for {self.place}")

        for x in self.dishes:
            try:
                x.translate()
            except Exception as e:
                logger.exception(e)

        for x in self.soups:
            try:
                x.translate()
            except Exception as e:
                logger.exception(e)

        self.is_translated = True

    def __str__(self):
        return str(self.__dict__)


class Dish:
    def __init__(self, name, type="main", price=None):
        self.name = name
        self.name_en = name
        self.type = type
        self.price = price
    
    def translate(self):
        try:
            self.name_en = translate(self.name)
        except Exception as e:
            logger.error(f"Cannot translate dish {self.name}")
            logger.exception(e)

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return str(self.__dict__)

    
class MenzaTroja(Place):
    def __init__(self):
        super().__init__()
        self.name = "Menza Troja"
        self.url = "https://kamweb.ruk.cuni.cz/webkredit/Api/Ordering/Rss?canteenId=27&locale=cs"
        self.tab_id = "menza"

    def fetch_menus(self):
        rss = requests.get(self.url).content.decode("utf-8")
        rss = html.unescape(rss)
        content = bs(rss, features="xml")
        
        menus = []

        for day in content.find_all("item"):
            menu_date = day.find("title").text
            menu_date = dateparser.parse(menu_date).date()
        
            menu_date_detail = day.find("div")
            lists = menu_date_detail.find_all("ul")

            if len(lists) == 2:  # we have a soup
                soups = [Dish(lists[0].find("li").text.strip(), type="soup")]
                dish_menu = lists[1]
            elif len(lists) == 1:
                logger.warning(f"No soup found in menza on {menu_date}")
                soups = []
                dish_menu = lists[0]

            dishes = [Dish(el.text.strip()) for el in dish_menu.find_all("li")]
            dishes = [x for x in dishes if "svátek" not in x.name]
            
            m = Menu(dishes, soups=soups, date=menu_date, place=self.name)
            menus.append(m)

        self.menus = menus
        return True

                

class BufetTroja(Place):
    def __init__(self):
        super().__init__()
        self.name = "Bufet Troja"
        self.url = "https://aurora.troja.mff.cuni.cz/pavlu/bufet.pdf"
        self.tab_id = "bufet"
    
    def _has_food(self, s):
        return re.search(r"^\s*(\d){2,4}g ", s)     # contains weight

    def _has_date(self, s):
        return re.search(r"\d{1,2}\.\s*\d{1,2}\.\s*\d{4}", s)

    def _has_soup(self, s):
        return "polévka" in s.lower()

    def _is_last(self, s):
        return "Dále nabízíme" in s

    def fetch_menus(self):
        pdf = requests.get(self.url)

        with open('bufet_tmp.pdf', 'wb') as f:
            f.write(pdf.content)

        text = textract.process('bufet_tmp.pdf', method='pdftotext', layout=True)
        text = text.decode("utf-8").split("\n")
        menus = []
        m = None
        
        for i in text:
            if self._has_date(i):
                if m is not None:
                    menus.append(m)

                menu_date = re.search(r"\d{1,2}\.\s*\d{1,2}\.\s*\d{4}", i).group(0)
                current_date = datetime.datetime.strptime(menu_date, "%d.%m.%Y").date()
                m = Menu(dishes=[], soups=[], date=current_date, place=self.name)

            if self._has_soup(i) and m is not None:
                soup = re.search(r"(polévka [\w\s,]*\w)", i, flags=re.IGNORECASE).group(1)
                price = re.search("(\d+),-\s*$", i)

                if price:
                    price = price.group(1)

                if soup:
                    soup = Dish(soup.strip().capitalize(), price=price, type="soup")
                    m.soups.append(soup)

            if self._has_food(i) and m is not None:
                dish = re.search(r"\d+g\s*([^\d]*[^\W\d])", i, flags=re.IGNORECASE).group(1)
                price = re.search("(\d+),-\s*$", i)

                if price:
                    price = price.group(1)

                dish = Dish(dish.strip().capitalize(), price=price)
                m.dishes.append(dish)

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
        rss = requests.get(self.url).content.decode("utf-8")
        html = bs(rss, "lxml")
        menus = []

        for day in html.find_all("div", {"class" : "food-sub-section"})[:5]:
            menu_date = day.find("h3").text.strip()
            menu_date = re.sub(r"[^\d\.]", "", menu_date)

            try:
                menu_date = datetime.datetime.strptime(menu_date, "%d.%m.%Y").date()
                
                dishes = day.find_all("div", {"class" : "row pb-3 pt-2 py-md-1"})
                dishes = [x.text.strip() for x in dishes]
                dishes = [re.sub(r"\s*[-–—]{0,1}\s*(\d\w{0,1},{0,1}\s*){1,9}\s*\t", "", x) for x in dishes] # remove alergens
                dishes = [re.search(r"([^\d]*)?\s*(\d+) Kč\s*$", x) for x in dishes]
                soups = [Dish(dishes[0].group(1), price=dishes[0].group(2), type="soup")]
                dishes = [Dish(x.group(1), price=x.group(2)) for x in dishes[1:]]
                
                m = Menu(dishes, soups=soups, date=menu_date, place=self.name)
                menus.append(m)
            except Exception as e:
                logger.exception(e)
                continue
        
        self.menus = menus
        return True
        

# if __name__ == "__main__":
    # today = datetime.datetime.now()

    # place = MenzaTroja()
    # place = BufetTroja()
    # place = CastleRestaurant()
    # place.fetch_menus()
    # print(place.get_menus())