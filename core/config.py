import logging

from dotenv import load_dotenv
import os

from typing import Literal, List

load_dotenv()

class Config:

    @staticmethod
    def extract_loglevel(value: str) -> int:
        level = value.upper()
        numeric_level: int = getattr(logging, level)

        if not isinstance(numeric_level, int):
            raise ValueError(f"Ungültiger Loglevel Wert: {value}")

        return numeric_level

    @staticmethod
    def extract_ollama_think(value: str|None) -> bool|Literal["low", "medium", "high"]|None:

        if not value:
            return None

        value = value.lower().strip()

        match value.lower():
            case "low" | "medium" | "high":
                return value
            case "true":
                return True
            case "false":
                return False
            case "true":
                return True
            case _:
                raise Exception(f"Ungültiger Wert für Ollama Think Parameter: {value}")

    @staticmethod
    def extract_ollama_keep_alive(value: str|None) -> str|float|None:
        if not value:
            return None

        value = value.lower().strip()

        try:
            number = float(value)
            return number
        except ValueError:
            return value

    @staticmethod
    def extract_csv_tags(value: str | None) -> List[str]:
        if not value:
            return []
        return [tag.strip() for tag in value.split(",") if tag.strip()]



    LOGLEVEL: int = extract_loglevel(os.getenv("LOGLEVEL", "INFO"))
    DISCORD_TOKEN: str|None = os.getenv("DISCORD_TOKEN")
    MISTRAL_API_KEY: str|None = os.getenv("MISTRAL_API_KEY")
    MISTRAL_MODEL: str = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gemma3:4b")
    OLLAMA_MODEL_TEMPERATURE: float|None = float(value) if (value := os.getenv("OLLAMA_MODEL_TEMPERATURE")) else None
    OLLAMA_THINK: bool|Literal["low", "medium", "high"]|None = extract_ollama_think(os.getenv("OLLAMA_THINK"))
    OLLAMA_KEEP_ALIVE: str|float|None = os.getenv("OLLAMA_KEEP_ALIVE")
    OLLAMA_TIMEOUT: float|None = float(value) if (value := os.getenv("OLLAMA_TIMEOUT")) else None
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", 64000))
    AI: Literal["ollama", "mistral"] = os.getenv("AI", "mistral")
    TOOL_INTEGRATION: bool = os.getenv("TOOL_INTEGRATION", "").lower() == "true"
    IMAGE_MODEL: bool = os.getenv("IMAGE_MODEL", "").lower() == "true"
    IMAGE_MODEL_TYPES: List[str] = extract_csv_tags(os.getenv("IMAGE_MODEL_TYPES", "image/jpeg,image/png"))
    MCP_SERVER_URL: str|None = os.getenv("MCP_SERVER_URL")
    MAX_MESSAGE_COUNT: int = int(os.getenv("MAX_MESSAGE_COUNT", 3))
    TOTAL_MESSAGE_SEARCH_COUNT: int = int(os.getenv("TOTAL_MESSAGE_SEARCH_COUNT", 20))
    INSTRUCTIONS: str = os.getenv("INSTRUCTIONS", "")
    MAX_TOOL_CALLS: int = int(os.getenv("MAX_TOOL_CALLS", 30))
    DENY_RECURSIVE_TOOL_CALLING: bool = os.getenv("DENY_RECURSIVE_TOOL_CALLING", "").lower() == "true"
    NAME: str = os.getenv("NAME", "Bot")
    LANGUAGE: Literal["de", "en"] = os.getenv("LANGUAGE", "de")
    DISCORD_ID: str|None = os.getenv("DISCORD_ID")
    USERNAMES_CSV_FILE_PATH: str|None = os.getenv("USERNAMES_PATH")
    HELP_DISCORD_ID: str|None = os.getenv("HELP_DISCORD_ID")
    MCP_TOOL_TAGS: List[str] = extract_csv_tags(os.getenv("MCP_TOOL_TAGS"))
    HISTORY_RESET_TEXT: str = os.getenv("HISTORY_RESET_TEXT", " --- ")


