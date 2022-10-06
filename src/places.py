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
from .translate import translate


logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO, datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


class Menu:
    def __init__(self, dishes, soups, date=None, place=None):
        self.dishes = dishes
        self.soups = soups        # maybe not that beautiful
        self.date = date
        self.place = place
    
    def translate(self):
        logger.info(f"Translating menu for {self.place}")
        for x in self.dishes:
            x.translate()

        for x in self.soups:
            x.translate()
    
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


class Place:
    pass

    
class MenzaTroja(Place):
    def __init__(self):
        self.name = "Menza Troja"
        self.url = "https://kamweb.ruk.cuni.cz/webkredit/Api/Ordering/Rss?canteenId=27&locale=cs"

    def get_menu(self):
        rss = requests.get(self.url).content.decode("utf-8")
        rss = html.unescape(rss)
        content = bs(rss, features="xml")
        
        menu = []

        for day in content.find_all("item"):
            menu_date = day.find("title").text
            menu_date = dateparser.parse(menu_date).date()
        
            menu_date_detail = day.find("div")
            lists = menu_date_detail.find_all("ul")

            if len(lists) == 2:  # we have soup
                soup = Dish(lists[0].find("li").text.strip(), type="soup")
                dish_menu = lists[1]
            elif len(lists) == 1:
                logger.warning("No soup found or something is broken")
                soup = None
                dish_menu = lists[0]

            dishes = [Dish(el.text.strip()) for el in dish_menu.find_all("li")]
            m = Menu(dishes, soups=[soup], date=menu_date, place=self.name)
            menu.append(m)

        return menu

                

class BufetTroja(Place):
    def __init__(self):
        self.name = "Bufet Troja"
        self.url = "https://aurora.troja.mff.cuni.cz/pavlu/bufet.pdf"
    
    def _is_food(self, s):
        return re.search(r"^\s*(\d){2,4}g ", s)     # contains weight

    def _is_date(self, s):
        return re.search(r"\d{1,2}\.\s*\d{1,2}\.\s*\d{4}", s)

    def _is_soup(self, s):
        return "polévka" in s.lower()

    def get_menu(self):
        pdf = requests.get(self.url)

        with open('bufet_tmp.pdf', 'wb') as f:
            f.write(pdf.content)

        text = textract.process('bufet_tmp.pdf')
        text = text.decode("utf-8").split("\n")
        menu = []
        m = None
        
        for i in text:
            if self._is_date(i):
                if m is not None:
                    menu.append(m)

                menu_date = re.sub(r"[^\d\.]", "", i)
                current_date = dateparser.parse(menu_date).date()
                m = Menu(dishes=[], soups=[], date=current_date, place=self.name)

            elif self._is_soup(i) and m is not None:
                soup = Dish(i.strip(), type="soup")
                m.soups.append(soup)

            elif self._is_food(i) and m is not None:
                dish = Dish(i.split("g ")[1])
                m.dishes.append(dish)

        menu.append(m)
            
        os.remove("bufet_tmp.pdf")
        return menu




class CastleRestaurant(Place):
    def __init__(self):
        self.name = "Castle Restaurant"
        # the menu fetched by JS at https://www.castle-restaurant.cz/poledni-menu
        self.url = "https://www.prazskejrej.cz/menu-na-web/castle-residence"
    
    def get_menu(self):
        rss = requests.get(self.url).content.decode("utf-8")
        html = bs(rss, "lxml")
        menu = []

        for day in html.find_all("div", {"class" : "food-sub-section"})[:5]:
            menu_date = day.find("h3").text.strip()
            menu_date = re.sub(r"[^\d\.]", "", menu_date)
            menu_date = datetime.datetime.strptime(menu_date, "%d.%m.%Y").date()
            
            dishes = day.find_all("div", {"class" : "col align-self-center flex-grow-1 order-2 order-xs-4"})
            dishes = [x.text.strip() for x in dishes]
            dishes = [re.sub(r"\s*[-–—]{0,1}\s*(\d\w{0,1},{0,1}\s*){1,9}\s*$", "", x) for x in dishes] # remove alergens
            
            soup = Dish(dishes[0], type="soup")
            dishes = [Dish(x) for x in dishes[1:]]
            
            m = Menu(dishes, soups=[soup], date=menu_date, place=self.name)
            menu.append(m)
        
        return menu
        

if __name__ == "__main__":
    # today = datetime.datetime.now()

    # place = MenzaTroja()
    # place = BufetTroja()
    place = CastleRestaurant()
    print(place.get_menu())