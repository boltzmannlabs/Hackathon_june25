import os
import sys

tools_path = "/home/ubuntu/prasanna/internal_hackathon/git_proj/tools"
sys.path.append(tools_path)

from predict_and_filter_epitopes import main as predict_and_filter_epitopes

results_dir = "/home/ubuntu/prasanna/internal_hackathon/git_proj/results"

fasta_files = [f for f in os.listdir(results_dir) if f.endswith('.fasta')]

if fasta_files:
    fasta_file = os.path.join(results_dir, fasta_files[0])
    output_file = os.path.join(results_dir, "epitope_predictions.csv")
    
    predict_and_filter_epitopes(fasta_file=fasta_file, output_file=output_file)
else:
    print("No FASTA file found in results directory")