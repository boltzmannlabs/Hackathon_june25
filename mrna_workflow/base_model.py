from pydantic import BaseModel, Field
from typing import Optional, List, Literal

class AnalyzeQueryOutput(BaseModel):
    query_path : Literal["clarification", "direct_answer", "complex_task"] = Field(description="Type of query determined by analysis: 'clarification', 'direct_answer', or 'complex_task'.")

class plan_step(BaseModel):
    step : str = Field(description="Ensure to provide the step with well defined explanation")

class PlanOutput(BaseModel):
    steps : List[str] = Field(description="Returns the list of steps that are clearly defined.")

class ToolsOutput(BaseModel):
    tools : List[str] = Field(description="It should return the List of tools with the tool name.")
