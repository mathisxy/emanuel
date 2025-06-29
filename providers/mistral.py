import os
from typing import List, Dict
from mistralai import Mistral
from mistralai.extra.mcp.sse import MCPClientSSE, SSEServerParams
from mistralai.extra.run.context import RunContext

api_key = os.getenv("API_KEY")
model = os.getenv("MISTRAL_MODEL")
mcp_server_url = os.getenv("MCP_SERVER_URL")
client = Mistral(api_key=api_key)

async def call_ai(history: List[Dict], instructions: str) -> str:
    mcp_client = MCPClientSSE(sse_params=SSEServerParams(url=mcp_server_url, timeout=100))

    async with RunContext(model=model) as run_ctx:
        await run_ctx.register_mcp_client(mcp_client=mcp_client)
        run_results = await client.beta.conversations.run_async(
            run_ctx=run_ctx,
            inputs=history,
            description="Manuel, ein Discord Bot",
            instructions=instructions
        )
        return run_results.output_as_text