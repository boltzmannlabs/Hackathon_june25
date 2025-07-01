import subprocess
from Bio import SeqIO
import os

# === USER INPUT: Set your optimized FASTA file path here ===
OPTIMIZED_FASTA_PATH = "../results/optimized_sequence.fasta"

def run_rnafold_and_plot(seq, seq_id):
    """Runs RNAfold and saves the structure plot as a PNG."""
    seq = seq.upper().replace("T", "U")  # Ensure RNA, not DNA
    ps_file = f"../results/{seq_id}_ss.ps"
    png_file = f"../results/{seq_id}_ss.png"
    # Run RNAfold, which will make a .ps file by default
    p = subprocess.Popen(
        ['RNAfold', '--noPS'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    stdout, stderr = p.communicate(input=f">{seq_id}\n{seq}\n".encode())
    out_lines = stdout.decode().splitlines()
    dot_bracket, mfe = "", 0.0
    for line in out_lines:
        if '(' in line and ')' in line:
            dot_bracket, mfe = line.split(' ', 1)
            mfe = float(mfe.strip('() ').replace('kcal/mol', ''))
    # Now re-run RNAfold without --noPS to get the .ps file
    os.makedirs("../results", exist_ok=True)
    with open(f"../results/{seq_id}.fa", "w") as f:
        f.write(f">{seq_id}\n{seq}\n")
    subprocess.run(['RNAfold', f"{seq_id}.fa"], cwd="../results")
    # .ps file will be named "{seq_id}_ss.ps"
    # Convert .ps to .png
    try:
        if os.path.exists(ps_file):
            subprocess.run([
                "gs",
                "-dNOPAUSE", "-dBATCH", "-sDEVICE=pngalpha",
                f"-sOutputFile={png_file}",
                "-r200",
                ps_file
            ])
        else:
            print("Warning: RNAfold did not produce a .ps file.")
    except:
        pass
    return dot_bracket, mfe, png_file

# # def run_rnafold_and_plot(seq, seq_id):
#     """Runs RNAfold and saves the structure plot as a PNG."""
#     # Ensure results directory exists
#     os.makedirs("../results", exist_ok=True)

#     seq = seq.upper().replace("T", "U")  # Ensure RNA, not DNA
#     fa_file = f"../results/{seq_id}.fa"
#     ps_file = f"../results/{seq_id}_ss.ps"
#     png_file = f"../results/{seq_id}_ss.png"

#     # Run RNAfold, get dot-bracket and mfe from output (no PS file this run)
#     p = subprocess.Popen(
#         ['RNAfold', ],
#         stdin=subprocess.PIPE,
#         stdout=subprocess.PIPE,
#         stderr=subprocess.PIPE
#     )
#     stdout, stderr = p.communicate(input=f">{seq_id}\n{seq}\n".encode())
#     out_lines = stdout.decode().splitlines()
#     dot_bracket, mfe = "", 0.0
#     for line in out_lines:
#         if '(' in line and ')' in line:
#             parts = line.rsplit(' ', 1)
#             if len(parts) == 2:
#                 dot_bracket = parts[0].strip()
#                 mfe_str = parts[1].strip('() ').replace('kcal/mol', '')
#                 try:
#                     mfe = float(mfe_str)
#                 except ValueError:
#                     mfe = None

#     # Write input fasta for RNAfold to produce structure plot (.ps)
#     with open(fa_file, "w") as f:
#         f.write(f">{seq_id}\n{seq}\n")

#     subprocess.run(['RNAfold', fa_file], cwd="../results")

#     # The .ps file will be named "{seq_id}_ss.ps" in ./results
#     # Convert .ps to .png if .ps was produced
#     if os.path.exists(ps_file):
#         subprocess.run([
#             "gs",
#             "-dNOPAUSE", "-dBATCH", "-sDEVICE=pngalpha",
#             f"-sOutputFile={png_file}",
#             "-r200",
#             ps_file
#         ])
#     else:
#         print("Warning: RNAfold did not produce a .ps file.")

#     return dot_bracket, mfe, png_file

def find_5utr_hairpin(dot_bracket, five_utr_length=30):
    utr = dot_bracket[:five_utr_length]
    return '(' in utr and ')' in utr

def write_structure_report(seq_id, seq, dot_bracket, mfe, has_5utr_hairpin, png_file, report_path="../results/structure_report.txt"):
    with open(report_path, "w") as f:
        f.write(f"mRNA ID: {seq_id}\n")
        f.write(f"Sequence:\n{seq}\n\n")
        f.write(f"Predicted secondary structure (dot-bracket):\n{dot_bracket}\n")
        f.write(f"Minimum Free Energy (MFE): {mfe:.2f} kcal/mol\n\n")
        if has_5utr_hairpin:
            f.write("WARNING: Hairpin structure detected in the first 30 bases (5' UTR region).\n")
        else:
            f.write("No strong hairpins detected in the 5' UTR region.\n")
        f.write(f"Structure visualization saved as: {png_file}\n")

def save_dot_bracket(dot_bracket, seq_id, filename="../results/structure.dbn"):
    with open(filename, "w") as f:
        f.write(f">{seq_id}\n{dot_bracket}\n")



def main(
    fasta_path: str,
    five_utr_length: int = 30,
    save_outputs: bool = True,
    output_report_path: str = "../results/structure_report.txt",
    output_dbn_path: str = "../results/structure.dbn"
):
    """
    Generalized function to analyze RNA secondary structure from an optimized FASTA.

    Args:
        fasta_path (str): Path to optimized mRNA FASTA file.
        five_utr_length (int): Length of 5' UTR region to check for hairpin.
        save_outputs (bool): Whether to save the structure report and dot-bracket notation.
        output_report_path (str): Path to save structure report.
        output_dbn_path (str): Path to save dot-bracket file.

    Returns:
        dict: Contains sequence ID, dot-bracket structure, MFE, hairpin presence, and structure image path.
    """
    # Read optimized mRNA sequence
    record = next(SeqIO.parse(fasta_path, "fasta"))
    seq = str(record.seq)
    seq_id = record.id

    # Predict secondary structure
    dot_bracket, mfe, png_file = run_rnafold_and_plot(seq, seq_id)

    # Analyze 5' UTR hairpin
    has_5utr_hairpin = find_5utr_hairpin(dot_bracket, five_utr_length=five_utr_length)

    # Save outputs
    if save_outputs:
        write_structure_report(seq_id, seq, dot_bracket, mfe, has_5utr_hairpin, png_file)
        save_dot_bracket(dot_bracket, seq_id, output_dbn_path)

    return {
        "seq_id": seq_id,
        "dot_bracket": dot_bracket,
        "mfe": mfe,
        "has_5utr_hairpin": has_5utr_hairpin,
        "structure_image": png_file
    }

if __name__ == "__main__":
    result = main(fasta_path="/home/ubuntu/prasanna/internal_hackathon/git_proj/results/optimized_mrna_sequence.fasta")

    print(f"MFE: {result['mfe']:.2f} kcal/mol")
    print("Hairpin in 5' UTR:", "Yes" if result["has_5utr_hairpin"] else "No")
    print(f"Structure image file: {result['structure_image']}")
