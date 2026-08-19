import logging
import os
import inspect

from datetime import datetime

from utils.jsonUtils import fromJSONFile, toJSONFile

from config import LOG_PATH, LOGQUEUE_PATH, config

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logging.getLogger().setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def log(message: str, send_with_bot:bool = False, tipo: str = "info", only_file=False):
    now = datetime.now()
    
    if not only_file:
        if tipo == "errore":
            logger.error(message)
        elif tipo == "warning":
            logger.warning(message)
        else:
            logger.info(message)
            
        
    messageForFile = f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] - {inspect.stack()[1].filename} - " + message + "\n"
    messageForBot = message
    
    logQueue = fromJSONFile(LOGQUEUE_PATH)
    if send_with_bot and config.CANALE_LOG is not None:
        logQueue.append(f"#{tipo.upper()}\n" + messageForBot)
        toJSONFile(LOGQUEUE_PATH,logQueue)
        
    m = 'a'
    if not os.path.exists(LOG_PATH):
        m='w'
        
    with open(LOG_PATH,m, encoding="utf-8") as f:
        f.write(messageForFile)
    
