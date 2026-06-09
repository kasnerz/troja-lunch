from pydantic import BaseModel, ConfigDict
from typing import Literal
from src.utils import translate
# from utils import translate
import datetime

def parse_dish_from_dict(dish_dict):
    return Dish(name=dish_dict["name"], name_en=dish_dict["name_en"], type=dish_dict["type"], price=dish_dict["price"])

def parse_menu_from_dict(menu_dict, logger=None):
    dishes = [parse_dish_from_dict(x) for x in menu_dict["dishes"]]
    soups = [parse_dish_from_dict(x) for x in menu_dict["soups"]]
    date = datetime.datetime.strptime(menu_dict["date"], "%Y-%m-%d").date() if menu_dict["date"] else None
    place = menu_dict["place"]
    return Menu(dishes=dishes, soups=soups, date=date, place=place, logger=logger)

def parse_menus_from_dict(place_dict, logger=None):
    return [parse_menu_from_dict(x, logger=logger) for x in place_dict["menus"]]

class Dish(BaseModel):
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    name: str
    name_en: str
    type: Literal["main", "soup"]
    price: str | None


    def __init__(self, name, type="main", price=None, name_en=None, logger=None):
        super().__init__(name=name, name_en=name_en or name, type=type, price=price)
        self.logger = logger
    
    def translate(self):
        try:
            self.name_en = translate(self.name)
        except Exception as e:
            self.logger.error(f"Cannot translate dish {self.name}")
            self.logger.exception(e)

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return str(self.__dict__)
    
class Menu(BaseModel):
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    dishes: list[Dish]
    soups: list[Dish]
    date: datetime.date | None
    place: str | None
    is_translated: bool

    def __init__(self, dishes, soups, date=None, place=None, logger=None):
        super().__init__(dishes=dishes, soups=soups, date=date, place=place, is_translated=False)
        self.logger = logger
    
    def translate(self):
        self.logger.info(f"Translating menu for {self.place}")

        for x in self.dishes:
            try:
                x.translate()
            except Exception as e:
                self.logger.exception(e)

        for x in self.soups:
            try:
                x.translate()
            except Exception as e:
                self.logger.exception(e)

        self.is_translated = True

    def __str__(self):
        return str(self.__dict__)

class Place(BaseModel):
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    menus: list[Menu]

    def __init__(self):
        super().__init__(menus=[])

    def get_menus(self):
        return self.menus

    def fetch_menus(self):
        raise NotImplementedError