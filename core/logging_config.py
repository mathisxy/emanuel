import logging
from core.config import Config

def setup_logging():

    logging.basicConfig(
        filename="bot.log",
        level=Config.LOGLEVEL,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True  # Python 3.8+
    )
