from src.type_defs import Place
from openai import OpenAI
import os

PROMPT = """Extract the menus from the following text. For each day of the week, there is a menu. The menu consists of dishes and soups. Each dish has a name, type (main or soup), and price (if available).

The output should follow this JSON schema:

```json
{{
    "$defs": {{
        "Dish": {{
            "additionalProperties": true,
            "properties": {{
                "name": {{
                    "title": "Name",
                    "type": "string"
                }},
                "name_en": {{
                    "title": "Name En",
                    "description": "Translated name of the dish",
                    "type": "string"
                }},
                "type": {{
                    "enum": [
                        "main",
                        "soup"
                    ],
                    "title": "Type",
                    "type": "string"
                }},
                "price": {{
                    "anyOf": [
                        {{
                            "type": "string"
                        }},
                        {{
                            "type": "null"
                        }}
                    ],
                    "title": "Price"
                }}
            }},
            "required": [
                "name",
                "name_en",
                "type",
                "price"
            ],
            "title": "Dish",
            "type": "object"
        }},
        "Menu": {{
            "additionalProperties": true,
            "properties": {{
                "dishes": {{
                    "items": {{
                        "$ref": "#/$defs/Dish"
                    }},
                    "title": "Dishes",
                    "description": "List of main dishes in the menu (excluding soups).",
                    "type": "array"
                }},
                "soups": {{
                    "items": {{
                        "$ref": "#/$defs/Dish"
                    }},
                    "title": "Soups",
                    "description": "List of soups in the menu.",
                    "type": "array"
                }},
                "date": {{
                    "anyOf": [
                        {{
                            "format": "date",
                            "type": "string"
                        }},
                        {{
                            "type": "null"
                        }}
                    ],
                    "title": "Date"
                }},
                "place": {{
                    "anyOf": [
                        {{
                            "type": "string"
                        }},
                        {{
                            "type": "null"
                        }}
                    ],
                    "title": "Place",
                    "description": "Name of the restaurant. This should be always '{place_name}'."
                }},
                "is_translated": {{
                    "title": "Is Translated",
                    "type": "boolean"
                }}
            }},
            "required": [
                "dishes",
                "soups",
                "date",
                "place",
                "is_translated"
            ],
            "title": "Menu",
            "description": "Menu for a specific day of the week.",
            "type": "object"
        }}
    }},
    "additionalProperties": true,
    "properties": {{
        "menus": {{
            "items": {{
                "$ref": "#/$defs/Menu"
            }},
            "title": "Menus",
            "type": "array"
        }}
    }},
    "required": [
        "menus"
    ],
    "title": "Place",
    "type": "object"
}}
```


"""

def llm_parse_menu(text, place_name=None):   
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
            {"role": "user", "content": PROMPT.format(place_name=place_name) + text}
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "place-menu-description",
                "schema": Place.model_json_schema()
            },
        },
    )

    return response.choices[0].message.content