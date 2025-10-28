import logging


def filter_response(response: str, model: str) -> str:

    if model.startswith("gemma3"):
        return response.replace("<start_of_image>", "")

    logging.debug(f"Kein Filter für {model} gefunden")

    return response