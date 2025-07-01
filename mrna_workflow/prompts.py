from typing import List
import os

def analyze_query_prompt(query: str) -> str:
    """
    Prompt to analyze the query and determine its type.
    
    Args:
        query (str): The user query to analyze.
        
    Returns:
        str: The type of query - "clarification", "direct_answer", or "complex_task".
    """
    return f"Analyze the following user query:\n\n"+f"{query}\n\n" +f"""Determine if this query requires clarification, a direct answer, or a complex task. "
        Respond with one of the following options: 'clarification', 'direct_answer', 'complex_task'.
        If query is any greeting messgaes respond with 'direct answer'
        NOTE : If the user query is not related to mRNA optimization or RNA structure prediction, respond with 'clarification'.
        Do not provide any additional information or explanations, just return the type of query."""

def direct_answer_prompt(query: str) -> str:
    """
    Prompt to provide a direct answer to the user query.
    
    Args:
        query (str): The user query to answer.
        
    Returns:
        str: The direct answer to the query.
    """
    return f"Provide answer to the following user query:\n\n{query}\n\n" + \
           """Ensure the answer is concise and directly addresses the user's question without additional explanations.
           If query related to any greeting messages, Respond politely
           If the query is not related to mRNA optimization or RNA structure prediction, respond with 'Query should relate to mRNA optimization or RNA structure prediction.'
           Provide a clear explanation if necessary, but keep it brief."""

def plan_steps_prompt(query: str) -> str:
    """
    Prompt to generate a plan for complex tasks based on the user query.
    
    Args:
        query (str): The user query to analyze.
        
    Returns:
        str: The plan for handling the complex task.
    """
    plan = """1.define_biological_target 2.predict_and_filter_epitopes 3.design_mrna_construct 4.optimize_codon_usage 5.predict_secondary_structure_and_stability 6.evaluate_immunogenicity_and_safety"""
    return f"Generate a detailed plan to address the following complex task:\n\n{query}\n\n" + \
           f"""Think about the query and break it down into clear, actionable steps.
           if user asks about synthesis of MRNA, Directly provide the below workflow."
           {plan}
           Each step should be specific and lead towards a solution.
           Ensure the plan is logical and feasible, considering the tools and resources available.
           Provide the plan in a structured format, with each step clearly numbered or bulleted.
           If the query is not related to mRNA optimization or RNA structure prediction, respond with 'Query should relate to mRNA optimization or RNA structure prediction.'
           """

def match_tools_prompt(plan_steps: str, tool_list: list) -> str:
    """
    Prompt for mapping each step in a plan to the most appropriate tool(s) from a list.

    Args:
        plan_steps (str): The step-by-step plan generated for the user query.
        tool_list (list): The list of available tools or functions (as names or brief descriptions).

    Returns:
        str: Instructions matching each step to the relevant tool(s), including reasoning.
    """
    return f"Given the following plan to address a user query:\n\n{plan_steps}\n\n" +f"And the list of available tools/functions:\n\n{tool_list}\n\n"+f"""For each step in the plan, specify which tool(s) or function(s) from the list should be used to accomplish that step.
        Explain briefly why each tool is chosen for each step. 
        If a step cannot be addressed by any tool in the list, state {None}
        Repond the list of tools in structured list."""


# def code_generation_prompt(state: dict, tool, tool_info: list) -> str:
#     """
#     Prompt for generating code to accomplish a task using specified tools.

#     Args:
#         state (dict): The current state, including the plan step or task description.
#         tool_info (list): Information about the tools/functions available for code generation.

#     Returns:
#         str: Instructions for generating code using the provided tools.
#     """
#     return (
#         f"You are given the following task or step to implement:\n\n"
#         f"The following tools/functions are available for use:\n\n"
#         f"{tool_info}\n\n"
#         "Write Python code to accomplish the task using the provided tools where appropriate. "
#         "Ensure the code is clear, well-structured, and uses the tools efficiently. "
#         "If multiple tools are needed, integrate them logically. "
#         "If the task cannot be accomplished with the available tools, respond with 'No suitable code can be generated with the current tools.' "
#         "Return only the code, without any explanations or comments."
#     )

def code_generation_prompt(user_query,tool,tool_info: list, tools_path :str, results_path :str, error : str = None, debug_msg : str = None) -> str:
    """
    Prompt for generating code to accomplish a task using specified tools.

    Args:
        state (dict): The current state, including the plan step or task description.
        tool_info (list): Information about the tools/functions available for code generation.

    Returns:
        str: Instructions for generating code using the provided tools.
    """

    tool_files = os.listdir(tools_path)
    dir_info = os.listdir(results_path)

    if error:
        return f"""You are a skilled Python developer. Your task is to generate Python code to accomplish a specific step using the tools and data provided.
        For the given tool : {tool} generate code using the below information
        You have access to the following tools/functions (with their input formats):

    {tool_info}

    Available tool implementations are located in the folder: {tools_path}  
    Tool files available for import: {tool_files}

    Data required for the operation is located in the results folder: {results_path}  
    Directory contents: {dir_info}

    If the previous attempt failed with an error, consider the following message and revise the code accordingly:\n\nError message:\n{error}\n\nCarefully debug and fix the issue in your new code.\n
    You are also provided with debug message : {debug_msg}

    Instructions:
    1. Import the correct tools/functions from the provided tool files.
    2. From tool import main function and proceed the process. example : "from tool_name import main as tool_name"
    3. Make sure to give the report for all the outputs that are captured.
    4. Prepare the required inputs based on the directory contents.
    5. Call the tool(s) using the correct input format and execute the task.

    Rules:
    - For every tool make to generate and save the report in results folder.
    - If multiple tools are needed, use them in the appropriate sequence.
    - If no suitable code can be generated using the available tools and data, return exactly:
    'No suitable code can be generated with the current tools.'
    - Return only the Python code. Do not include any explanations or comments.
    """
    
    else:
        return f"""You are a skilled Python developer. Your task is to generate Python code that performs the following action using the available tools/functions.
    For the given tool : {tool} generate code using the below information
    You have access to the following tools/functions (along with their expected input formats):

    {tool_info}

    The available tool implementations (i.e., importable Python files) are located in the folder: {tools_path}
    Tool files available for import: {tool_files}, Ensure the necessary files should be imported from tools_path given.

    Use these to:
    1. Import the correct tool(s)/function(s) from the tools_path folder.
    3. Identify the required inputs from the user query {user_query} if and only if it needed for the tools.(Donot assume or create inputs of your own.)
    2. Identify the required inputs/files from the following results directory:
    - Results Folder: {results_path}
    - Directory Contents: {dir_info}

    3. Generate valid Python code that:
    - Imports the relevant tools/functions.
    - Loads or constructs the required inputs from the directory structure.   
    - Import the correct tools/functions from the provided tool files.
    - From tool import main function and proceed the process. example : **from tool_name import main as tool_name**
    - Make sure to give the report and save the report in {results_path} folder for all the outputs that are captured.
    - Prepare the required inputs based on the directory contents.
    - Call the tool(s) using the correct input format and execute the task.

    Guidelines:
    - If multiple tools are required, integrate them logically.
    - If no suitable code can be generated with the available tools and inputs, return exactly:
    'No suitable code can be generated with the current tools.'

    Important:
    - Return only the final Python code. Do not include explanations or comments.
    """

def debug_code_prompt(code : str, error : str):
    debug_prompt = f"""You are a senior debugging expert. Analyze the test failure and identify the issues:
    CODE:
    ```python
    {code}
    ```
    Error facing : {error}
    Analyze the failure and provide a clear error message explaining:
    1. What went wrong
    2. Why it failed
    3. What needs to be fixed

    Be specific and actionable in your response.
    """
    return debug_prompt

def result_analysis_prompt(results: List[str], results_path: str) -> str:
    """
    Prompt for analyzing all intermediate results and generating a final summary report.

    Args:
        results (List[str]): List of result file names or result summaries.
        results_path (str): Path to the directory containing result files.

    Returns:
        str: Prompt for the LLM to analyze and summarize the results.
    """
    dir_res = os.listdir(results_path)
    return f"""You are an expert scientific analyst. Your task is to carefully review all the intermediate reports and result files generated during the workflow and should make a report out of it.

Results directory: {dir_res}
Files to analyze: {results}

Instructions:
1. Analyze and give each result file in the directory.
2. Analyze the content of each file, noting key findings, important data, and any issues or errors.
3. Synthesize the information from all files into a single, clear, and concise final report.
4. Highlight the main outcomes, insights, and any recommendations for next steps.
5. If any step failed or produced errors, clearly mention them and suggest possible resolutions.
6. You can give the results directory information that what files are generated.

Return only the final summary report. Do not include code or anything.
"""


