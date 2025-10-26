def filter_response(response: str, model: str) -> str:

    if model.startswith("gemma3"):
        return response.replace("<start_of_image>", "")