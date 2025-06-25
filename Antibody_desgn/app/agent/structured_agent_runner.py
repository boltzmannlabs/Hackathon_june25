# app/agent/structured_agent_runner.py
import os
import boto3
import logging
from bson import ObjectId
from langchain import hub
from langchain_aws import ChatBedrock
from langchain.agents import create_structured_chat_agent, AgentExecutor
from langchain_core.tools import tool
from app.tools.tool_waiter import await_async_tool
from langchain.agents import Tool


logger = logging.getLogger(__name__)

# ── 1) Wrap your real tools with @tool decorators ───────────────────────────────


from app.tools.rf_antibody import rf_antibody_tool
from app.tools.preprocessing import preprocessing_tool
from app.tools.alphafold import alphafold_tool
from app.tools.prodigy import prodigy_tool
from app.tools.megadock import megadock_tool

tools = [
    rf_antibody_tool,
    preprocessing_tool,
    alphafold_tool,
    megadock_tool,
    prodigy_tool,
]


# ── 2) Setup Bedrock LLM ────────────────────────────────────────────────────────

client = boto3.client("bedrock-runtime", region_name="us-east-1")
llm = ChatBedrock(
    model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
    model_kwargs={"temperature": 0},
    client=client,
)

# ── 3) Create structured chat agent ──────────────────────────────────────────────

prompt = hub.pull("hwchase17/structured-chat-agent")

agent = create_structured_chat_agent(llm=llm, tools=tools, prompt=prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# ── 4) Run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = agent_executor.invoke({
        "input": (
            "Design better antibodies for given using RF Antibody, "
            "then run AlphaFold structure prediction next megadock and rank them using Prodigy. "
            "Antigen PDBs are at /home/ubuntu/Antibody_design/app/CD47.pdb. and antibody pdb is /home/ubuntu/Antibody_design/app/lemzoparlimab (3).pdb "
            "so finally return top 5."
            "Return all tool inputs as JSON dictionaries matching the schema fields."

        ),
    })
    print(result)
