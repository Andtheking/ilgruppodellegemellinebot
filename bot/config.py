import os
from dotenv import load_dotenv
from requests import get
from utils.json_utils import fromJSON

load_dotenv()

class Config:
    def __init__(self):
        self.TOKEN = os.getenv['TELEGRAM_TOKEN']
        self.CANALE_LOG = os.getenv['TELEGRAM_LOG_CHANNEL_ID'] or None
        self.BOT_INFO = get(f'https://api.telegram.org/bot{self.TOKEN}/getMe')
        self.BOT_USERNAME = fromJSON(self.BOT_INFO.text)['result']['username']
        
config = Config()