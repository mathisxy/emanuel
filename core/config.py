from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN")
    API_KEY: str = os.getenv("API_KEY")
    MODEL: str = os.getenv("MODEL")
    AI: str = os.getenv("AI", "mistral")
    MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL")
    MAX_MESSAGE_COUNT: int = int(os.getenv("MAX_MESSAGE_COUNT", 3))
    TOTAL_MESSAGE_SEARCH_COUNT: int = int(os.getenv("TOTAL_MESSAGE_SEARCH_COUNT"), 20)
    INSTRUCTIONS: str = os.getenv("INSTRUCTIONS", "")
    NAME: str = os.getenv("NAME", "Bot")
    DISCORD_ID: str = os.getenv("DISCORD_ID")
    USERNAMES_CSV_FILE_PATH: str = os.getenv("USERNAMES_PATH")