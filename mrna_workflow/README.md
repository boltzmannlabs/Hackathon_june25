# 🧬 mRNA Workflow Automation

This project automates an end-to-end scientific workflow for **mRNA design and discovery** using modular tools, prompt-based agents, and AI-assisted execution.

---

## 📁 Project Structure

```
mrna_workflow/
├── agent.py                           # Main file to run the workflow
├── base_model.py                      # Shared base model or utilities
├── biological_target_definition_report.md  # Sample report output
├── logs/                              # Log files
├── main_code.py                       # Core processing logic or orchestration
├── prompts.py                         # Reusable prompt templates
├── prompts/                           # Prompt library (organized)
├── requirements.txt                   # Python dependencies
├── results/                           # Output files and intermediate results
├── tool_space.json                    # Tool configuration (agent definitions)
└── tools/                             # Custom tools used in workflows
```

---

## 🚀 How to Run

1. **Clone and navigate to the repo**
   ```bash
   git clone <your_repo_url>
   cd mrna_workflow
   ```

2. **Set up a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the workflow**
   ```bash
   python agent.py
   ```

---

## 🧠 What It Does

This agent-based system:

- Defines a **biological target** (e.g., from UniProt or NCBI)
- Generates mRNA sequences or optimization steps using **prompt-driven AI agents**
- Executes workflows with **modular tools** defined in `tools/` and configured in `tool_space.json`
- Logs outputs and intermediate steps
- Stores final results in the `results/` directory

---

## 🛠️ Key Components

- `agent.py` – Entry point; orchestrates the entire workflow.
- `base_model.py` – Core logic shared across agents or tools.
- `main_code.py` – Business logic and task orchestration.
- `tools/` – Domain-specific modules or external integrations.
- `tool_space.json` – Describes available tools and their I/O interfaces.
- `prompts.py` / `prompts/` – Prompt templates for AI agents.
- `results/` – Contains final output of the workflow.

---

## 🧪 Example Use Case

Define a target protein like `"SARS-CoV-2, Spike glycoprotein"` from NCBI, run the workflow, and get:

- Annotated biological target data
- Candidate mRNA sequences
- Optimization reports (e.g., codon usage, GC content)
- Logs and a markdown report

---

## 📓 Sample Output

See: `biological_target_definition_report.md` and files in the `results/` directory.

