import os
from dotenv import load_dotenv
from requests import get
from utils.json_utils import fromJSON

load_dotenv()

class BotConfig:
    def __init__(self):
        self.TOKEN = os.getenv('TELEGRAM_TOKEN')
        self.CANALE_LOG = os.getenv('TELEGRAM_LOG_CHANNEL_ID') or None
        try:
            self.BOT_INFO = get(f'https://api.telegram.org/bot{self.TOKEN}/getMe', timeout=3.0)
            self.BOT_USERNAME = fromJSON(self.BOT_INFO.text)['result']['username']
        except Exception:
            self.BOT_INFO = None
            self.BOT_USERNAME = os.getenv('BOT_USERNAME', 'ilgruppodellegemellinebot')

        
bot_config = BotConfig()