
# 🔌 **Analog Circuit Design Workflow**

An intelligent, AI-driven pipeline for **automated analog circuit design** — built using **LangGraph** and **Claude Sonnet 4**. It transforms natural language circuit specifications into **validated SPICE netlists** via a multi-stage workflow featuring tool selection, code generation, execution, and result extraction.

---

## 📁 **Project Structure**

```
.
├── agent.py            # Main logic: planning, code generation, execution, results
├── workflow.py         # Generates a Mermaid-style diagram (pipeline.png) visualizing the LangGraph workflow
├── app.py              # Gradio UI for interactive design
├── tools.py            # Design tools used by the workflow
├── generated_code.py   # Auto-generated script during execution
├── README.md
└── requirements.txt    # (Optional) for pip installs
```

---

## ⚙️ **Setup Instructions**

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/boltzmannlabs/Hackathon_june25.git
cd Hackathon_june25/Circuit_Design
```

### 2️⃣ Create and Activate Conda Environment

```bash
conda create -n analogxpert_env python=3.10 -y
conda activate analogxpert_env
```

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 🔑 **API Configuration**

Set up your **AWS Bedrock credentials** using Claude Sonnet 4:

```bash
# .env file or environment variables
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

If you're using `anthropic` directly:
```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

---

## 🚀 **Run the Workflow Programmatically**

```python
from agent import run_circuit_design_workflow

result = run_circuit_design_workflow(
    "Design a single-stage differential amplifier with NMOS input transistors"
)

print(result['final_netlist'])
```

---

## 🖼️ **Gradio Web Interface**

Launch an interactive UI from `app.py`:

```bash
python app.py
```

- Input: Natural language circuit specification  
- Output: Design plan, tool execution summary, SPICE netlist  
- Accessible at `http://localhost:7865`

---

## 🏗️ **Workflow Architecture**

```
User Query
    ↓
[Planning Node] → Analyze query, generate design plan, select tools
    ↓
[Code Generation Node] → Generate executable Python code
    ↓
[Execution Node] → Run generated code using selected tools
    ↓
[Results Node] → Extract and format SPICE netlist
```

### 📦 Available Tools

| Tool               | Description                                        |
|--------------------|----------------------------------------------------|
| `input_validation` | Validates structured analog specs                  |
| `netlist_generator`| Generates SPICE netlists using subcircuit models  |
| `output_validation`| Validates netlists against design rules            |

---

## 💡 **Prompt Examples**

#### ✔️ Basic Differential Amplifier

```python
"Design a single-stage differential amplifier with differential inputs and NMOS input transistors"
```

#### ✔️ Multi-Stage Operational Amplifier

```python
"Design a two-stage op-amp with PMOS differential pair, NMOS mirror load, and Miller compensation"
```

#### ✔️ Current Mirror

```python
"Create a wide-swing cascode current mirror using NMOS transistors with 10uA reference current"
```

#### ✔️ Bandgap Reference

```python
"Design a bandgap voltage reference circuit with startup and temperature compensation"
```

---

## 📊 **Output Structure**

```python
{
    'final_netlist': str,         # Generated SPICE netlist
    'plan': str,                  # Full AI-generated design plan
    'execution_result': str,      # Full tool output log
    'status': str,                # Workflow status: completed, error, etc.
    'error_messages': List[str]   # Any error messages during flow
}
```

---

## 🔧 **Configuration Options**

### ✅ Execution Timeout

Located in `code_execution_node` inside `agent.py`:

```python
# Default timeout: 180 seconds
subprocess.run(..., timeout=180)
```

### ✅ Conda Environment Path

Update if needed:
```python
conda_env_path = '/path/to/anaconda3/envs/analogxpert_env'
```

---

## 🐛 **Troubleshooting**

| Issue                   | Solution                                        |
|-------------------------|-------------------------------------------------|
| Tool import error       | Ensure `tools.py` exists and is in the root    |
| Missing environment     | Verify conda environment path is correct       |
| Timeout error           | Increase timeout for complex circuits          |
| API limit exceeded      | Slow down requests or check usage              |

🔍 **Debugging Tip**: The system generates `generated_code.py` to inspect the generated script when issues occur.

---

## ✅ **Supported Circuit Types**

- ✔️ Differential Amplifiers (single-stage, multi-stage)
- ✔️ Operational Amplifiers (Miller, telescopic, folded cascode)
- ✔️ Current Mirrors (simple, cascode, wide-swing)
- ✔️ Biasing Circuits (bandgap, voltage references)
- ✔️ Active Filters (LPF/HPF/BPF with op-amps)
- ✔️ Oscillators (ring, relaxation, LC)

---

## 🤖 **AI-Powered Features**

- 🔍 **Context-Aware Planning**  
- 🛠️ **Automatic Tool Selection**  
- 🧠 **Code Generation via Claude Sonnet 4**  
- ✅ **Tool Execution with Validation**  
- 🧪 **Error Recovery and Debug Logs**

---

## 🧪 Example Result Summary

```
ANALOG CIRCUIT DESIGN WORKFLOW RESULTS
==========================================
Original Query: Design a differential amplifier...

Design Plan:
1. Use telescopic topology...
2. Apply wide-swing current mirror load...

Tool Execution Output:
Tool 1 (input_validation): Passed
Tool 2 (netlist_generator): Success
Tool 3 (output_validation): All checks passed ✅

Final Netlist:
*** SPICE Code ***
...
```

---

**Built for next-generation circuit design automation**