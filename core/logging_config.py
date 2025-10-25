import logging
from core.config import Config

def setup_logging():
    logging.basicConfig(filename="bot.log", level=logging.DEBUG if Config.DEBUG else logging.INFO)
    if Config.DEBUG:
        logging.debug("Logging set to DEBUG")