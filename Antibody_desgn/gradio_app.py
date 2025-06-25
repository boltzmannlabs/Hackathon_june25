# # import os
# # import json
# # import logging
# # import boto3
# # import gradio as gr

# # from bson import ObjectId
# # from langchain import hub
# # from langchain_aws import ChatBedrock
# # from langchain.agents import create_structured_chat_agent, AgentExecutor
# # from langchain_core.tools import tool

# # # Import your real tools
# # from app.tools.rf_antibody import rf_antibody_tool
# # from app.tools.preprocessing import preprocessing_tool
# # from app.tools.alphafold import alphafold_tool
# # from app.tools.prodigy import prodigy_tool
# # from app.tools.megadock import megadock_tool

# # # Setup logging
# # logger = logging.getLogger(__name__)

# # # === LangChain Agent Setup ===
# # tools = [
# #     rf_antibody_tool,
# #     preprocessing_tool,
# #     alphafold_tool,
# #     megadock_tool,
# #     prodigy_tool,
# # ]

# # client = boto3.client("bedrock-runtime", region_name="us-east-1")
# # llm = ChatBedrock(
# #     model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
# #     model_kwargs={"temperature": 0},
# #     client=client,
# # )

# # prompt = hub.pull("hwchase17/structured-chat-agent")
# # agent = create_structured_chat_agent(llm=llm, tools=tools, prompt=prompt)
# # agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)


# # # === Handle Inputs and Run Agent ===
# # def run_pipeline(antibody_pdb, antigen_pdb, user_input):
# #     os.makedirs("./uploads", exist_ok=True)
# #     os.makedirs("./outputs", exist_ok=True)

# #     antibody_path = "./uploads/antibody.pdb"
# #     antigen_path = "./uploads/antigen.pdb"

# #     # Save the uploaded files
# #     with open(antibody_pdb.name, "rb") as infile, open(antibody_path, "wb") as outfile:
# #         outfile.write(infile.read())

# #     with open(antigen_pdb.name, "rb") as infile, open(antigen_path, "wb") as outfile:
# #         outfile.write(infile.read())

# #     # Construct the input prompt
# #     user_prompt = (
# #         f"{user_input.strip()} "
# #         f"Antigen PDBs are at {antigen_path} and antibody pdb is {antibody_path}. "
# #         f"Return all tool inputs as JSON dictionaries matching the schema fields. "
# #         f"Return top 5 final ranked complexes and their scores as a downloadable JSON."
# #     )

# #     try:
# #         result = agent_executor.invoke({"input": user_prompt})

# #         output_path = "./outputs/top5_output.json"
# #         with open(output_path, "w") as f:
# #             json.dump(result, f, indent=2)

# #         return f"Pipeline executed successfully. Download below.", output_path

# #     except Exception as e:
# #         logger.exception("Agent execution failed.")
# #         return f"Error during execution: {str(e)}", None


# # # === Gradio UI ===
# # with gr.Blocks(title="AbGen: Antibody Design Agent") as demo:
# #     gr.Markdown("# 🧬 AbGen: Structure-Aware Antibody Designer")
# #     gr.Markdown("Upload antibody & antigen PDB files and describe your goal (e.g., improve binding, generate novel antibodies).")

# #     with gr.Row():
# #         antibody_input = gr.File(label="Upload Antibody PDB", file_types=[".pdb"])
# #         antigen_input = gr.File(label="Upload Antigen PDB", file_types=[".pdb"])

# #     user_text = gr.Textbox(label="User Goal", placeholder="e.g., Design improved antibody for better binding affinity...")

# #     submit_btn = gr.Button("Run Antibody Design Agent")
# #     status_text = gr.Textbox(label="Status", interactive=False)
# #     download_file = gr.File(label="Download Output", visible=False)

# #     def on_submit(antibody, antigen, user_text):
# #         message, filepath = run_pipeline(antibody, antigen, user_text)
# #         if filepath:
# #             return message, filepath
# #         return message, None

# #     submit_btn.click(
# #         fn=on_submit,
# #         inputs=[antibody_input, antigen_input, user_text],
# #         outputs=[status_text, download_file],
# #     )

# # demo.launch(share=True,server_port=7860)




# # # import gradio as gr
# # # import os

# # # # === Function to handle inputs and save files ===
# # # def handle_inputs(antibody_pdb, antigen_pdb, user_input):
# # #     os.makedirs("./uploads", exist_ok=True)

# # #     antibody_path = None
# # #     antigen_path = None

# # #     # Save antibody file
# # #     if antibody_pdb is not None:
# # #         antibody_path = "./uploads/antibody.pdb"
# # #         with open(antibody_pdb.name, "rb") as infile, open(antibody_path, "wb") as outfile:
# # #             outfile.write(infile.read())

# # #     # Save antigen file
# # #     if antigen_pdb is not None:
# # #         antigen_path = "./uploads/antigen.pdb"
# # #         with open(antigen_pdb.name, "rb") as infile, open(antigen_path, "wb") as outfile:
# # #             outfile.write(infile.read())

# # #     # Log (optional)
# # #     print(f"[INFO] Antibody Path: {antibody_path}")
# # #     print(f"[INFO] Antigen Path: {antigen_path}")
# # #     print(f"[INFO] User Input: {user_input}")

# # #     # Return paths and user input for use in downstream pipeline
# # #     return {
# # #         "antibody_path": antibody_path,
# # #         "antigen_path": antigen_path,
# # #         "user_input": user_input
# # #     }



# # # # === Gradio UI ===
# # # with gr.Blocks(title="Antibody Design") as demo:
# # #     gr.Markdown("# 🧬 Antibody Design")
# # #     gr.Markdown("Upload Antibody and Antigen PDB files and provide any design instructions.")

# # #     with gr.Row():
# # #         antibody_input = gr.File(label="Upload Antibody PDB", file_types=[".pdb"])
# # #         antigen_input = gr.File(label="Upload Antigen PDB", file_types=[".pdb"])

# # #     user_text = gr.Textbox(label="User Input", placeholder="Enter design instructions...")

# # #     submit_btn = gr.Button("Submit")
# # #     output = gr.Textbox(label="", visible=False)  # Hidden output just to trigger function

# # #     submit_btn.click(
# # #         fn=handle_inputs,
# # #         inputs=[antibody_input, antigen_input, user_text],
# # #         outputs=output  # not shown
# # #     )

# # # # === Launch App ===
# # # demo.launch()


# import os
# import json
# import logging
# import boto3
# import gradio as gr

# from langchain import hub
# from langchain_aws import ChatBedrock
# from langchain.agents import create_structured_chat_agent, AgentExecutor

# # Real tools
# from app.tools.rf_antibody import rf_antibody_tool
# from app.tools.preprocessing import preprocessing_tool
# from app.tools.alphafold import alphafold_tool
# from app.tools.prodigy import prodigy_tool
# from app.tools.megadock import megadock_tool

# # === Logging ===
# logger = logging.getLogger(__name__)

# # === Tools & Agent Setup ===
# tools = [
#     rf_antibody_tool,
#     preprocessing_tool,
#     alphafold_tool,
#     prodigy_tool,
#     megadock_tool,
# ]

# client = boto3.client("bedrock-runtime", region_name="us-east-1")
# llm = ChatBedrock(
#     model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
#     model_kwargs={"temperature": 0},
#     client=client,
# )

# prompt = hub.pull("hwchase17/structured-chat-agent")
# agent = create_structured_chat_agent(llm=llm, tools=tools, prompt=prompt)
# agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# # === Core Pipeline Runner ===
# def run_pipeline(antibody_pdb, antigen_pdb, user_input):
#     os.makedirs("./uploads", exist_ok=True)
#     os.makedirs("./outputs", exist_ok=True)

#     antibody_path = antigen_path = None

#     if antibody_pdb is not None:
#         antibody_path = "./uploads/antibody.pdb"
#         with open(antibody_pdb.name, "rb") as infile, open(antibody_path, "wb") as outfile:
#             outfile.write(infile.read())

#     if antigen_pdb is not None:
#         antigen_path = "./uploads/antigen.pdb"
#         with open(antigen_pdb.name, "rb") as infile, open(antigen_path, "wb") as outfile:
#             outfile.write(infile.read())

#     user_prompt = user_input.strip()
#     if antibody_path:
#         user_prompt += f"\nAntibody PDB path: {antibody_path}."
#     if antigen_path:
#         user_prompt += f"\nAntigen PDB path: {antigen_path}."

#     try:
#         result = agent_executor.invoke({"input": user_prompt})

#         # Extract info from result
#         result_message = result.get("output", "Agent completed successfully.")
#         zip_path = result.get("final_zip_path") or result.get("zip_path")  # Allow for varied naming

#         if zip_path and os.path.exists(zip_path):
#             return result_message, zip_path
#         else:
#             return result_message + " (No downloadable result was found.)", None

#     except Exception as e:
#         logger.exception("Agent execution failed.")
#         return f"Error during execution: {str(e)}", None

# # === Gradio UI ===
# with gr.Blocks(title="AbGen: Antibody Design Agent") as demo:
#     gr.Markdown("# 🧬 AbGen: Structure-Aware Antibody Designer")
#     gr.Markdown(
#         "Upload optional PDB files and describe your antibody design goal. "
#         "The AI agent will plan and execute the design pipeline."
#     )

#     with gr.Row():
#         antibody_input = gr.File(label="Upload Antibody PDB (Optional)", file_types=[".pdb"])
#         antigen_input = gr.File(label="Upload Antigen PDB (Optional)", file_types=[".pdb"])

#     user_text = gr.Textbox(
#         label="Your Design Objective",
#         placeholder="e.g., Improve binding of antibody to antigen X",
#         lines=3
#     )

#     submit_btn = gr.Button("🧠 Run Antibody Design Agent")
#     status_text = gr.Textbox(label="Agent Response", interactive=False)
#     download_file = gr.File(label="Download ZIP Results", visible=False)

#     def on_submit(antibody, antigen, user_text):
#         message, filepath = run_pipeline(antibody, antigen, user_text)
#         if filepath:
#             return message, filepath
#         return message, None

#     submit_btn.click(
#         fn=on_submit,
#         inputs=[antibody_input, antigen_input, user_text],
#         outputs=[status_text, download_file],
#     )

# # Launch app
# if __name__ == "__main__":
#     demo.launch(share=True,server_port=7860)

import os
import json
import logging
import boto3
import gradio as gr

from langchain import hub
from langchain_aws import ChatBedrock
from langchain.agents import create_structured_chat_agent, AgentExecutor

# Real tools
from app.tools.rf_antibody import rf_antibody_tool
from app.tools.preprocessing import preprocessing_tool
from app.tools.alphafold import alphafold_tool
from app.tools.prodigy import prodigy_tool
from app.tools.megadock import megadock_tool

# === Logging ===
logger = logging.getLogger(__name__)

# === Tools & Agent Setup ===
tools = [
    rf_antibody_tool,
    preprocessing_tool,
    alphafold_tool,
    prodigy_tool,
    megadock_tool,
]

client = boto3.client("bedrock-runtime", region_name="us-east-1")
llm = ChatBedrock(
    model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
    model_kwargs={"temperature": 0},
    client=client,
)

prompt = hub.pull("hwchase17/structured-chat-agent")
agent = create_structured_chat_agent(llm=llm, tools=tools, prompt=prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)


# === Core Pipeline Runner ===
def run_pipeline(antibody_pdb, antigen_pdb, user_input):
    os.makedirs("./uploads", exist_ok=True)
    os.makedirs("./outputs", exist_ok=True)

    antibody_path = antigen_path = None

    if antibody_pdb is not None:
        antibody_path = "./uploads/antibody.pdb"
        with open(antibody_pdb.name, "rb") as infile, open(antibody_path, "wb") as outfile:
            outfile.write(infile.read())

    if antigen_pdb is not None:
        antigen_path = "./uploads/antigen.pdb"
        with open(antigen_pdb.name, "rb") as infile, open(antigen_path, "wb") as outfile:
            outfile.write(infile.read())

    user_prompt = user_input.strip()
    if antibody_path:
        user_prompt += f"\nAntibody PDB path: {antibody_path}."
    if antigen_path:
        user_prompt += f"\nAntigen PDB path: {antigen_path}."

    try:
        result = agent_executor.invoke({"input": user_prompt})

        # Extract info from result
        result_message = result.get("output", "Agent completed successfully.")
        zip_path = result.get("final_zip_path") or result.get("zip_path")

        if zip_path and os.path.exists(zip_path):
            return result_message, zip_path
        else:
            return result_message + " (No downloadable result was found.)", None

    except Exception as e:
        logger.exception("Agent execution failed.")
        return f"Error during execution: {str(e)}", None


# === Gradio UI ===
with gr.Blocks(title="AbGen: Antibody Design Agent") as demo:
    gr.Markdown("# 🧬 AbGen: Antibody Designer")
    gr.Markdown(
        "Upload optional PDB files and describe your antibody design goal. "
        "The AI agent will plan and execute the design pipeline."
    )

    with gr.Row():
        antibody_input = gr.File(label="Upload Antibody PDB (Optional)", file_types=[".pdb"])
        antigen_input = gr.File(label="Upload Antigen PDB (Optional)", file_types=[".pdb"])

    user_text = gr.Textbox(
        label="Your Design Objective",
        placeholder="e.g., Improve binding of antibody to antigen X",
        lines=3
    )

    submit_btn = gr.Button("🧠 Run Antibody Design Agent")

    # === Result Section ===
    gr.Markdown("### 🧾 Agent Response")
    status_text = gr.Textbox(
        label="Agent Message",
        interactive=False,
        lines=5,
        max_lines=10,
        show_copy_button=True
    )

    gr.Markdown("### 📦 Download Results")
    download_file = gr.File(label="Download Final ZIP", visible=False, interactive=False)

    def on_submit(antibody, antigen, user_text):
        message, filepath = run_pipeline(antibody, antigen, user_text)
        if filepath:
            return message, filepath, gr.update(visible=True)
        return message, None, gr.update(visible=False)

    submit_btn.click(
        fn=on_submit,
        inputs=[antibody_input, antigen_input, user_text],
        outputs=[status_text, download_file, download_file],
    )

# Launch app
if __name__ == "__main__":
    demo.launch(share=True,server_port=7860)
