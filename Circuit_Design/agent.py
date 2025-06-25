import os
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict
from langchain_aws import ChatBedrock
import boto3
from dotenv import load_dotenv
import subprocess

load_dotenv()

client = boto3.client(
    'bedrock-runtime', 
    region_name="us-east-1", 
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"], 
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"]
)

sonnet_4 = ChatBedrock(
    model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
    model_kwargs=dict(temperature=0),
    client=client
)

class WorkflowState(TypedDict):
    """State definition for the workflow"""
    user_query: str
    plan: str
    selected_tools: List[str]  
    generated_code: str
    execution_result: str
    final_netlist: str
    error_messages: List[str]
    iteration_count: int
    status: str

def planning_node(state: WorkflowState) -> WorkflowState:
    """
    Planning node that analyzes the user query and creates a design plan
    with tool selection
    """
    print("Planning Phase: Analyzing user requirements...")
    
    planning_prompt = f"""
    You are an expert analog circuit design planner. Analyze the following user query and create a detailed design plan.

    User Query: {state['user_query']}

    Available tools from tools.py:
    1. input_validation(input: str) -> str: Validates whether a design specification is complete and logically consistent for both structured field-based and block-based formats
    2. netlist_generator(input: str) -> str: Generates SPICE netlist using analog subcircuit library based on design specifications
    3. output_validation(input: str) -> str: Validates analog circuit netlist against design rules and connectivity requirements

    Your task is to:
    1. Create a comprehensive design plan
    2. Select the appropriate tools needed to fulfill the user requirements

    ANALYSIS FRAMEWORK:

    **Design Plan Requirements:**
    1. Circuit topology identification (single-stage vs multi-stage)
    2. Input/output signal types (differential/single-ended) 
    3. Required transistor types and bias configurations
    4. Load and current mirror requirements
    5. Connection strategy between components
    6. Validation checkpoints for the design
    7. Expected circuit behavior and performance

    **Tool Selection Logic:**
    - Always use input_validation if the user provides design specifications that need validation
    - Always use netlist_generator if the user wants a SPICE netlist generated
    - Always use output_validation if a netlist needs to be verified for correctness
    - Consider the workflow: input_validation → netlist_generator → output_validation

    **User Query Analysis:**
    - Does the user provide design specifications? → input_validation needed
    - Does the user want netlist generation? → netlist_generator needed  
    - Does the user want validation of results? → output_validation needed
    - Is this a complete design flow? → all three tools needed

    Return your response in this exact format:

    DESIGN PLAN:
    [Detailed design plan covering all 7 requirements above]

    SELECTED TOOLS:
    [List only the tool names that are needed, one per line:
    - input_validation
    - netlist_generator  
    - output_validation]

    TOOL USAGE STRATEGY:
    [Explain how each selected tool will be used and in what sequence]
    """
    
    try:
        plan_response = sonnet_4.invoke(planning_prompt)
        response_content = plan_response.content

        lines = response_content.split('\n')

        plan_start = False
        tools_start = False
        strategy_start = False
        
        plan_lines = []
        tools_lines = []
        strategy_lines = []
        
        for line in lines:
            if line.strip().startswith('DESIGN PLAN:'):
                plan_start = True
                tools_start = False
                strategy_start = False
                continue
            elif line.strip().startswith('SELECTED TOOLS:'):
                plan_start = False
                tools_start = True
                strategy_start = False
                continue
            elif line.strip().startswith('TOOL USAGE STRATEGY:'):
                plan_start = False
                tools_start = False
                strategy_start = True
                continue
            
            if plan_start and not line.strip().startswith('SELECTED TOOLS:'):
                plan_lines.append(line)
            elif tools_start and not line.strip().startswith('TOOL USAGE STRATEGY:'):
                if line.strip().startswith('- '):
                    tools_lines.append(line.strip()[2:])  
            elif strategy_start:
                strategy_lines.append(line)
        
        full_plan = '\n'.join(plan_lines).strip() + '\n\nTOOL USAGE STRATEGY:\n' + '\n'.join(strategy_lines).strip()

        selected_tools = [tool.strip() for tool in tools_lines if tool.strip()]

        available_tools = ['input_validation', 'netlist_generator', 'output_validation']
        valid_tools = [tool for tool in selected_tools if tool in available_tools]
        
        state['plan'] = full_plan
        state['selected_tools'] = valid_tools
        state['status'] = 'planned'
        
        print("Planning completed successfully")
        print(f"Selected tools: {valid_tools}")
        
    except Exception as e:
        state['error_messages'].append(f"Planning error: {str(e)}")
        state['status'] = 'error'
        print(f"Planning failed: {str(e)}")
    
    return state

def code_generation_node(state: WorkflowState) -> WorkflowState:
    """
    Code generation node using Claude Sonnet 4 to generate Python code that uses the selected tools
    """
    print("Code Generation Phase: Creating Python implementation...")
    
    code_generation_prompt = f"""
    You are an expert Python developer specializing in analog circuit design automation.
    
    User Query: {state['user_query']}
    Design Plan: {state['plan']}
    Selected Tools: {state['selected_tools']}
    
    Generate a complete Python script that uses ONLY the selected tools from tools.py to fulfill the user requirement.
    
    Available tools and their signatures:
    - input_validation(input: str) -> str: Validates design specifications
    - netlist_generator(input: str) -> str: Generates SPICE netlist using subcircuit library  
    - output_validation(input: str) -> str: Validates generated netlist for correctness
    
    CRITICAL: Do NOT extract or parse the netlist from the netlist_generator response!
    - Pass the ENTIRE netlist_generator response directly to output_validation
    - The output_validation tool is designed to handle the complete response format
    - No need to extract content between ***NetlistStart*** and ***NetlistEnd*** markers
    
    The script should:
    1. Import only the selected tools: `from tools import {', '.join(state['selected_tools'])}`
    2. Use the tools in the logical sequence determined by the plan
    3. Handle the tool responses properly (they return LangChain message objects with .content)
    4. For netlist_generator: Display the complete response as-is
    5. For output_validation: Pass the COMPLETE netlist_generator response content directly
    6. Print clear status messages and results for each tool used
    7. Include proper error handling for each tool call
    8. Pass the user query appropriately to each tool
    
    Important implementation notes:
    - The tools return LangChain message objects, so use `.content` to get the actual text
    - Simple workflow: input_validation(user_query) → netlist_generator(user_query) → output_validation(netlist_generator_response.content)
    - DO NOT attempt to extract or parse the netlist - use the complete response
    - Only use the tools that were selected in the planning phase
    - Handle cases where not all tools are needed
    
    Generate ONLY the Python code, no explanations or markdown:
    """
    
    try:
        code_response = sonnet_4.invoke(code_generation_prompt)
        state['generated_code'] = code_response.content
        state['status'] = 'code_generated'
        print("Code generation completed successfully")
    except Exception as e:
        state['error_messages'].append(f"Code generation error: {str(e)}")
        state['status'] = 'error'
        print(f"Code generation failed: {str(e)}")
    
    return state

def code_execution_node(state: WorkflowState) -> WorkflowState:
    """
    Code execution node that runs the generated Python code in the specified conda environment.
    """
    print("Code Execution Phase: Running generated code...")
    
    try:
        generated_code = state['generated_code']
    
        cleaned_code = generated_code

        if cleaned_code.strip().startswith('```'):
            parts = cleaned_code.strip().split('```')
            if len(parts) >= 3:
                cleaned_code = parts[1]
            else:
                cleaned_code = parts[-1]

        if cleaned_code.strip().startswith('python'):
            cleaned_code = '\n'.join(cleaned_code.strip().split('\n')[1:])
        full_code = f"""
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))

        {cleaned_code}
        """     
        debug_code_path = os.path.join(os.path.dirname(__file__), "generated_code.py")
        print("Full Code------:\n", full_code)
        with open(debug_code_path, 'w') as debug_file:
            debug_file.write(full_code)

        conda_env_path = '/home/ubuntu/anaconda3/envs/analogxpert-env'
        python_executable = os.path.join(conda_env_path, 'bin', 'python')
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        result = subprocess.run(
            [python_executable, debug_code_path], 
            capture_output=True, 
            text=True, 
            timeout=180, 
            cwd=script_dir
        )
        
        if result.returncode == 0:
            state['execution_result'] = result.stdout
            state['status'] = 'executed'
            print("Code execution completed successfully")
        else:
            state['error_messages'].append(f"Execution error: {result.stderr}")
            state['execution_result'] = f"Error: {result.stderr}"
            state['status'] = 'execution_error'
            print(f"Code execution failed: {result.stderr}")
        
    except subprocess.TimeoutExpired:
        state['error_messages'].append("Code execution timed out")
        state['status'] = 'timeout'
        print("Code execution timed out")
    except Exception as e:
        state['error_messages'].append(f"Execution setup error: {str(e)}")
        state['status'] = 'error'
        print(f"Code execution setup failed: {str(e)}")
    
    return state

def results_node(state: WorkflowState) -> WorkflowState:
    """
    Results node that processes and formats the final results
    """
    print("Results Phase: Processing and formatting results...")
    
    try:
        execution_output = state['execution_result']

        if '***NetlistStart***' in execution_output and '***NetlistEnd***' in execution_output:
            start_marker = '***NetlistStart***'
            end_marker = '***NetlistEnd***'
            start_index = execution_output.find(start_marker) + len(start_marker)
            end_index = execution_output.find(end_marker)
            state['final_netlist'] = execution_output[start_index:end_index].strip()
        else:

            lines = execution_output.split('\n')
            netlist_lines = []
            in_netlist = False
            
            for line in lines:
                if any(keyword in line.lower() for keyword in ['spice', 'netlist', '.subckt', '.model']):
                    in_netlist = True
                if in_netlist and (line.strip().startswith(('.', '*')) or 'M' in line or 'V' in line or 'I' in line):
                    netlist_lines.append(line)
                elif in_netlist and line.strip() == '':
                    continue
                elif in_netlist and not line.strip().startswith(('.', '*', 'M', 'V', 'I')):
                    if len(netlist_lines) > 3:  
                        break
            
            if netlist_lines:
                state['final_netlist'] = '\n'.join(netlist_lines)
        results_summary = f"""
        ANALOG CIRCUIT DESIGN WORKFLOW RESULTS
        ==========================================

        Original Query: {state['user_query']}

        Workflow Status: {state['status'].upper()}

        Design Plan:
        {state['plan'][:800]}{'...' if len(state['plan']) > 800 else ''}

        Generated Code:
        {state['generated_code'][:600]}{'...' if len(state['generated_code']) > 600 else ''}

        Tool Execution Output:
        {state['execution_result'][:1200]}{'...' if len(state['execution_result']) > 1200 else ''}

        Final Netlist:
        {state['final_netlist'] if state['final_netlist'] else 'No netlist extracted'}

        Errors: {len(state['error_messages'])} error(s)
        {chr(10).join(state['error_messages']) if state['error_messages'] else 'No errors'}

        Summary:
        {'Netlist generated and validated successfully!' if state['final_netlist'] and state['status'] == 'executed' else 'Workflow completed with issues. Check error messages above.'}
        """
        
        print(results_summary)
        state['status'] = 'completed'
        
    except Exception as e:
        state['error_messages'].append(f"Results processing error: {str(e)}")
        state['status'] = 'error'
        print(f"Results processing failed: {str(e)}")
    
    return state

def should_continue(state: WorkflowState) -> str:
    """
    Conditional edge function to determine workflow continuation
    """
    if state['status'] == 'error':
        return 'results'
    elif state['status'] == 'planned':
        return 'code_generation'
    elif state['status'] == 'code_generated':
        return 'code_execution'
    elif state['status'] in ['executed', 'execution_error', 'timeout']:
        return 'results'
    else:
        return END

def create_workflow() -> StateGraph:
    """
    Create and configure the LangGraph workflow with exactly 4 nodes
    """
    workflow = StateGraph(WorkflowState)

    workflow.add_node("planning", planning_node)
    workflow.add_node("code_generation", code_generation_node)
    workflow.add_node("code_execution", code_execution_node)
    workflow.add_node("results", results_node)

    workflow.set_entry_point("planning")
    workflow.add_conditional_edges(
        "planning",
        should_continue,
        {
            "code_generation": "code_generation",
            "results": "results"
        }
    )
    workflow.add_conditional_edges(
        "code_generation",
        should_continue,
        {
            "code_execution": "code_execution",
            "results": "results"
        }
    )
    workflow.add_conditional_edges(
        "code_execution",
        should_continue,
        {
            "results": "results"
        }
    )
    workflow.add_edge("results", END)
    
    return workflow.compile()

def run_circuit_design_workflow(user_query: str) -> Dict[str, Any]:
    """
    Main function to run the complete circuit design workflow
    """
    print("Starting Analog Circuit Design Workflow...")
    print(f"User Query: {user_query}")
    print("=" * 60)

    initial_state = WorkflowState(
        user_query=user_query,
        plan="",
        selected_tools=[],
        generated_code="",
        execution_result="",
        final_netlist="",
        error_messages=[],
        iteration_count=0,
        status="initialized"
    )
    
    workflow = create_workflow()
    final_state = workflow.invoke(initial_state)
    
    print("=" * 60)
    print("Workflow completed!")
    
    return final_state

if __name__ == "__main__":

    test_query = """Design a single-stage differential amplifier circuit. The input and output signals should both be differential. 
    Use NMOS as the input transistor type. The amplifier should follow a telescopic topology with a wide-swing 
    current mirror as the load and a simple current mirror as the tail bias. No compensation or feedback is required."""
    
    result = run_circuit_design_workflow(test_query)
    
    print("\nFINAL WORKFLOW SUMMARY:")
    print(f"Status: {result['status']}")
    print(f"Errors: {len(result['error_messages'])}")
    if result['final_netlist']:
        print("Netlist generated successfully")
        print(f"Netlist length: {len(result['final_netlist'])} characters")
    else:
        print("No netlist generated")