from typing import TypedDict, Literal, Optional, List
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain_aws import ChatBedrock
import boto3 
import os
import json
import logging
from datetime import datetime
import subprocess

import pdfkit 
import markdown as md

from prompts import analyze_query_prompt,direct_answer_prompt,plan_steps_prompt,match_tools_prompt,code_generation_prompt,debug_code_prompt,result_analysis_prompt
from base_model import AnalyzeQueryOutput,PlanOutput,ToolsOutput

class AgentConfig(TypedDict):
    query : str
    env_path : str = "./hack_env"
    result_path: str = "./result"
    query_path : Literal["clarification", "direct_answer", "complex_task"]
    plan : str
    tools_list : List[str]
    tool_completion :int = 0
    code : str
    result: Optional[List[str]]
    debug_info: Optional[str]
    report: Optional[str]
    error_msg : Optional[str]

class Agent:
    def __init__(self):
        print(os.chdir("/home/ubuntu/prasanna/internal_hackathon/git_proj"))
        from dotenv import load_dotenv
        load_dotenv()
        self.llm = ChatOpenAI(model_name="gpt-4o-mini")
        self.bedrock_client = boto3.client(
                                'bedrock-runtime', 
                                region_name="us-east-1", 
                                aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"], 
                                aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"]
                                
                            )
        self.code_llm = ChatBedrock(
                model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
                model_kwargs=dict(temperature=0),
                client=self.bedrock_client
            )
        self.tool_space = self.load_tool_space(path = "tool_space.json")
    
    def load_tool_space(self,path):
        with open(path, 'r') as file:
            data = json.load(file)

        return data


    def _analyze_query(self, state: AgentConfig) -> AgentConfig:
        """
        Analyze the query to determine if it requires clarification, a direct answer, or a complex task.
        """
        prompt = analyze_query_prompt(state['query'])
        llm = self.llm.with_structured_output(AnalyzeQueryOutput)
        response = llm.invoke([HumanMessage(content=prompt)])
        state['query_path'] = response.query_path
        return state
    
    def should_continue(self, state: AgentConfig) -> bool:
        """
        Check if the query requires further processing based on the analysis.
        """
        if state['query_path'] == "clarification":
            state['result'].append("Query should relate to mRNA optimization or RNA structure prediction.")
            return "vauge"
        elif state["query_path"] == "direct_answer":
            return "direct_answer"
        else:
            return "complex_task"
    
    def _direct_answer(self, state: AgentConfig) -> AgentConfig:
        """
        Handle direct answer queries.
        """
        prompt = direct_answer_prompt(state['query'])
        response = self.llm.invoke([HumanMessage(content=prompt)])
        state['result'] = response.content
        return state
    
    def _generate_plan(self, state: AgentConfig) -> AgentConfig:
        """
        Generate a plan for complex tasks based on the query.
        """
        prompt = plan_steps_prompt(state["query"])
        llm = self.llm.with_structured_output(PlanOutput)
        plan = llm.invoke([HumanMessage(content=prompt)])
        state['plan'] = plan
        return state
    
    def _match_tools(self, state:AgentConfig) -> AgentConfig:
        """
        Match the tools for each step based on the plan.
        """
        prompt = match_tools_prompt(state["plan"],self.tool_space)
        llm = self.llm.with_structured_output(ToolsOutput)
        tools_list = llm.invoke([HumanMessage(content=prompt)])
        state["tools_list"] = tools_list.tools
        return state
    
    def _code_generation(self, state:AgentConfig) -> AgentConfig:
        """
        Generate the python code for the given tool
        """
        tool = state["tools_list"][state["tool_completion"]]
        tool_info = self.tool_space[state["tool_completion"]]
        tools_path="/home/ubuntu/prasanna/internal_hackathon/git_proj/tools"
        if state["error_msg"]==None:
            prompt = code_generation_prompt(state["query"],tool,tool_info,tools_path,state["result_path"])
            code = self.code_llm.invoke(prompt)
            generated_code = code.content.strip()
            if generated_code.startswith("```python"):
                generated_code = generated_code.replace("```python", "").replace("```", "").strip()
            state["code"] = generated_code
        else:
            prompt = code_generation_prompt(tool_info,tools_path,state["result_path"],state["error_msg"],state["debug_info"])
            code = self.code_llm.invoke(prompt)
            generated_code = code.content.strip()
            if generated_code.startswith("```python"):
                generated_code = generated_code.replace("```python", "").replace("```", "").strip()
            state["code"] = generated_code
        return state
    
    def _code_execution(self,state:AgentConfig) -> AgentConfig:
        """
        Execute and run the generated code
        """
        try:
            code_path = "main_code.py"
            with open(code_path, "w") as f:
                f.write(state["code"])
            
            result = subprocess.run(
                ["python", code_path],
                capture_output=True,
                text=True,
                timeout=120,
                cwd = "/home/ubuntu/prasanna/internal_hackathon/git_proj"
            )
            output = result.stdout
            error = result.stderr
            if result.returncode == 0:
                state["result"].append(output if output else "Code executed successfully with no output.")
            else:
                state["result"].append(f"Execution failed:\nSTDOUT: {output}\nSTDERR: {error}")
                state["error_msg"] = error
            print(f"Exit Code: {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
            state["tool_completion"] = state["tool_completion"]+1
            return state

        except subprocess.TimeoutExpired:
            print("ERROR: Test execution timed out (30 seconds)")
            return state
        except Exception as e:
            print(f"ERROR: Failed to run tests: {str(e)}")
            return state
        finally:
            try:
                if os.path.exists("main_code.py"):
                    # os.remove("main_code.py")
                    pass
                if os.path.exists("test_main.py"):
                    # os.remove("test_main.py")
                    pass
            except:
                pass
        return state
    
    def _update_tools(self, state :AgentConfig,) -> AgentConfig:
        if len(state["tools_list"])==state["tool_completion"]:
            return state,END
        elif state["error_msg"]!=None:
            return state,"debug_code"
        else:
            return state,"another_tool"
    
    def check_completion(self, state:AgentConfig) -> AgentConfig:
        """
        Check whether the all the tools are generated or not
        """
        state, result = self._update_tools(state)
        print("Updating tool to : ",state["tool_completion"])
        return result
    
    def _debug_code(self,state:AgentConfig) -> AgentConfig:
        """
        Debug and check the code that was facing facing error
        """
        prompt = debug_code_prompt(state["code"],state["error_msg"])
        response = self.llm.invoke([HumanMessage(content=prompt)])
        error_analysis = response.content.strip()
        state["debug_info"] = error_analysis
        return state
    
    def _result_analysis(self,state: AgentConfig) -> AgentConfig:
        """
        Analyze the results and generate the report out of it
        """
        prompt = result_analysis_prompt(state["result"],state["result_path"])
        report = self.llm.invoke([HumanMessage(content=prompt)])
        state["final_report"]= report.content
        report_filename = f"biological_target_definition_report"
        markdown_path = os.path.join(state["result_path"], f"{report_filename}.md")
        pdf_path = os.path.join(state["result_path"], f"{report_filename}.pdf")
        markdown_content =report.content
        
        # Save Markdown file
        with open(markdown_path, "w", encoding="utf-8") as md_file:
            md_file.write(markdown_content)

        # Convert Markdown to HTML
        # html_content = md.markdown(markdown_content)

        # # Save PDF from HTML
        # pdfkit.from_string(html_content, pdf_path)

        print(f"Markdown saved to {markdown_path}")
        # print(f"PDF saved to {pdf_path}")
        return state

    
    def _workflow(self):
        workflow = StateGraph(AgentConfig)
        # Add nodes
        workflow.add_node("analyze_query", self._analyze_query)
        workflow.add_node("direct_answer", self._direct_answer)
        workflow.add_node("generate_plan", self._generate_plan)
        workflow.add_node("tool_mapping", self._match_tools)
        workflow.add_node("generate_code", self._code_generation)
        workflow.add_node("execute_code", self._code_execution)
        workflow.add_node("debug", self._debug_code)
        workflow.add_node("result_analysis", self._result_analysis)

        # Add edges
        workflow.add_edge(START,"analyze_query")
        workflow.add_conditional_edges(
            "analyze_query",
            self.should_continue,
            {
                "vauge": "result_analysis",
                "direct_answer" :  "direct_answer",
                "complex_task" : "generate_plan"
            }
        )
        workflow.add_edge("direct_answer", "result_analysis")
        workflow.add_edge("generate_plan","tool_mapping")
        workflow.add_edge("tool_mapping","generate_code")
        workflow.add_edge("generate_code","execute_code")
        workflow.add_conditional_edges(
            "execute_code",
            self.check_completion,
            {
                END : "result_analysis",
                "debug_code" : "debug",
                "another_tool" : "generate_code"
            }
        )
        workflow.add_edge("debug","generate_code")
        workflow.add_edge("result_analysis",END)

        # Compile the agent
        agent = workflow.compile()

        return agent

if __name__ == "__main__":
    state_input = {
            # "query" : "analyze mRNA Vaccine Synthesis using Agents and Machine Learning: A Case Study for COVID-19Design the MRNA Synthesis ",
            # "query" : "What is MRNA, explain breif abuot it",
            # "query" : "Who is prime minister of USA",
            # "query" : "Hello, Hpow are you what are your capabilities",
            "query" : "Synthesize mrna human papillomavirus 16,L1 without any optimization techniques.",
            "env_path" : "./hack_env",
            "result_path":  "./results",
            "query_path" : "",
            "plan" : "",
            "tools_list" :[],
            "tool_completion" : 0,
            "code" : "",
            "result": [],
            "debug_info": "",
            "report": "",
            "error_msg" : None,
            }
    graph = Agent()
    agents = graph._workflow()
    result = agents.invoke(state_input)
    print(result)

    
       

    
        