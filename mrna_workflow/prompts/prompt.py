import json

def load_prompt(query,tool_space):
    task_prompt = (
            "You are an expert in mRNA synthesis and therapeutics design. The user has provided a complex query that requires computational planning.\n"
            f"Please analyze the query and outline a step-by-step computational plan to address it.\n"
            f"if user asks about synthesis of MRNA, Directly provide the below workflow."
            f"1.define_biological_target 2.predict_and_filter_epitopes 3.design_mrna_construct 4.optimize_codon_usage 5.predict_secondary_structure_and_stability 6.evaluate_immunogenicity_and_safety"
            f"Query: {query}\n"
            f"If tools are available, specify their names and input/output. If a tool is not available, provide reasoning for what should be done.\n"
            f"Tool list: {json.dumps(tool_space)}\n"
            "Provide a detailed plan that includes the steps to be taken, any necessary tools, and how they will be used.\n"
            "At the end, provide a 'Tool list to execute:' section with the python-callable tool names and their required arguments as a list of dicts, e.g.:\n"
            "[{'name': 'tool1', 'args': {...}}, {'name': 'tool2', 'args': {...}}]"
        )
    return task_prompt
        