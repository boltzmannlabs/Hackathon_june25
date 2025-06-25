from agent import create_workflow
from IPython.display import Image, display

graph = create_workflow()
mermaid_graph = graph.get_graph().draw_mermaid_png()
with open("pipeline.png", "wb") as f:
    f.write(mermaid_graph)
print("Workflow diagram saved as pipeline.png")