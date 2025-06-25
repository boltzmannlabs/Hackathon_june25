
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the tools from tools.py
from tools import input_validation, netlist_generator, output_validation

# User query for the tools
user_query = '''Design a single-stage differential amplifier circuit. The input and output signals should both be differential. 
    Use NMOS as the input transistor type. The amplifier should follow a telescopic topology with a wide-swing 
    current mirror as the load and a simple current mirror as the tail bias. No compensation or feedback is required.'''

from tools import input_validation, netlist_generator, output_validation

def main():
    user_query = """Design a single-stage differential amplifier circuit. The input and output signals should both be differential. 
    Use NMOS as the input transistor type. The amplifier should follow a telescopic topology with a wide-swing 
    current mirror as the load and a simple current mirror as the tail bias. No compensation or feedback is required."""
    
    print("=== Single-Stage Telescopic Differential Amplifier Design ===\n")
    
    # Step 1: Input Validation
    print("Step 1: Validating design specifications...")
    try:
        validation_result = input_validation(user_query)
        print("✓ Input validation completed")
        print(f"Validation result: {validation_result.content}\n")
    except Exception as e:
        print(f"✗ Input validation failed: {e}")
        return
    
    # Step 2: Netlist Generation
    print("Step 2: Generating SPICE netlist...")
    try:
        netlist_result = netlist_generator(user_query)
        print("✓ Netlist generation completed")
        print("Generated netlist:")
        print(netlist_result.content)
        print()
    except Exception as e:
        print(f"✗ Netlist generation failed: {e}")
        return
    
    # Step 3: Output Validation
    print("Step 3: Validating generated netlist...")
    try:
        output_validation_result = output_validation(netlist_result.content)
        print("✓ Output validation completed")
        print(f"Validation result: {output_validation_result.content}\n")
    except Exception as e:
        print(f"✗ Output validation failed: {e}")
        return
    
    print("=== Design Process Completed Successfully ===")

if __name__ == "__main__":
    main()
