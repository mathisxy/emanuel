import logging
from core.config import Config

def setup_logging():

    logging.basicConfig(
        filename="bot.log",
        level=logging.DEBUG if Config.DEBUG else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True  # Python 3.8+
    )

    logging.info("Setup Logging...")
    if Config.DEBUG:
        logging.debug("Logging set to DEBUG")
