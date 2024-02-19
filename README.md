# troja-lunch 🍜

A web service providing access to menus for lunch places in the neighborhood of the [IMPAKT building](https://www.mff.cuni.cz/cs/vnitrni-zalezitosti/budovy-a-arealy/troja) of MFF UK.

Online version is available at **https://tiny.cc/troja-lunch**.

The service currently supports these places:
- Menza Troja
- Bufet Troja
- Castle Restaurant

More places from [this list](https://docs.google.com/document/d/1d9ryeOlgXGPu9qhMypvSUDp63iTMJAWtS1VrHD74FNs/edit) may be added in the future based on the demand.

The service uses the [CUBBITT API](https://lindat.mff.cuni.cz/services/translation/api/v2/doc) for translating the names of the dishes to English.

Please report any bugs on Github or directly to the author.


## Dish of the day
Every workday, the service generates a "dish of the day", which is a random dish selected from all the dishes available on a given day. 

For that dish, a computer-generated image is created using [Stable Diffusion](https://github.com/CompVis/stable-diffusion) prompted with the name of the dish and a couple of other attributes for improving the quality of the image.

The image is generated using a cron job around 9 AM. After the job is finished, the image for the current day should be accessible at `http://ufallab.ms.mff.cuni.cz/~kasner/troja-lunch/YYYY-mm-dd.png` and in the web service interface.

## Slackbot
The service is connected to a Slackbot in the ÚFAL MFF UK workspace called *lunchbot*. 

The bot is programmed to send regular posts to the *cfm-troja* channel, including the dish of the day and the invitations for lunch.