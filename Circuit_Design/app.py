import gradio as gr
from agent import run_circuit_design_workflow  

def process_circuit_query(user_query: str):
    if not user_query.strip():
        return "❗ Please enter a valid circuit design query.", "", ""

    try:
        result = run_circuit_design_workflow(user_query)

        status = f"✅ Status: {result['status'].upper()}"
        plan_summary = f"""📝 PLAN:
        {result['plan'][:800]}{'...' if len(result['plan']) > 800 else ''}

        🔧 Tools:
        {chr(10).join(result['selected_tools']) if result['selected_tools'] else 'None'}

        🧪 Execution:
        {result['execution_result'][:1000]}{'...' if len(result['execution_result']) > 1000 else ''}

        ⚠️ Errors:
        {chr(10).join(result['error_messages']) if result['error_messages'] else 'No errors'}"""

        netlist = result['final_netlist'] if result['final_netlist'] else "⚠️ No netlist generated."

        return status, plan_summary, netlist

    except Exception as e:
        return f"❌ ERROR: {str(e)}", "", ""

def launch_gradio():
    with gr.Blocks(title="Analog Circuit Workflow") as demo:
        gr.Markdown("# 🧠 Analog Circuit Design Agent")
        gr.Markdown("Submit your analog circuit design requirements and get a validated SPICE netlist!")

        with gr.Row():
            input_box = gr.Textbox(
                label="📝 Design Query",
                placeholder="e.g. Design a telescopic amplifier using NMOS with differential input/output...",
                lines=6
            )
            submit_btn = gr.Button("🚀 Run Workflow")

        with gr.Row():
            status_output = gr.Textbox(label="Status", interactive=False)
        
        with gr.Row():
            summary_output = gr.Textbox(label="Workflow Summary", interactive=False, lines=12, show_copy_button=True)
            netlist_output = gr.Textbox(label="SPICE Netlist", interactive=False, lines=12, show_copy_button=True)

        submit_btn.click(
            fn=process_circuit_query,
            inputs=[input_box],
            outputs=[status_output, summary_output, netlist_output]
        )

    demo.launch(server_name="0.0.0.0", server_port=7865, share=False)

if __name__ == "__main__":
    launch_gradio()
