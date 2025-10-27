from mcp_server.mcp_instance import mcp

import logging

from dotenv import load_dotenv

from mcp_server.tools import audio, image, control_generation, gameserver, web, default

logging.basicConfig(filename="server.log", level=logging.INFO)

load_dotenv()

# Server erstellen und starten
if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8001
    )
