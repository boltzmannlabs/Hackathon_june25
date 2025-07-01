from Bio import SeqIO
from Bio.Seq import Seq

# === USER INPUT: Set your FASTA file path here ===
INPUT_FASTA_PATH = "./results/mrna_constructs.fasta"  # <-- Change this to your FASTA filename

# Example codon usage table for Homo sapiens (most frequent codons per amino acid)
HUMAN_CODON_TABLE = {
    'F': 'TTT',  # Phenylalanine
    'L': 'CTG',  # Leucine
    'I': 'ATT',  # Isoleucine
    'M': 'ATG',  # Methionine
    'V': 'GTG',  # Valine
    'S': 'AGC',  # Serine
    'P': 'CCC',  # Proline
    'T': 'ACC',  # Threonine
    'A': 'GCC',  # Alanine
    'Y': 'TAC',  # Tyrosine
    '*': 'TAA',  # Stop codon
    'H': 'CAC',  # Histidine
    'Q': 'CAG',  # Glutamine
    'N': 'AAC',  # Asparagine
    'K': 'AAG',  # Lysine
    'D': 'GAC',  # Aspartic Acid
    'E': 'GAG',  # Glutamic Acid
    'C': 'TGC',  # Cysteine
    'W': 'TGG',  # Tryptophan
    'R': 'CGC',  # Arginine
    'G': 'GGC',  # Glycine
}

def translate_mrna(mrna_seq):
    dna_seq = mrna_seq.replace('U', 'T')
    seq_obj = Seq(dna_seq)
    return str(seq_obj.translate(to_stop=False))

def codon_optimize(amino_acid_seq, codon_table):
    optimized_seq = ''
    for aa in amino_acid_seq:
        codon = codon_table.get(aa, 'NNN')
        optimized_seq += codon
    return optimized_seq

def gc_content(seq):
    gc = sum(1 for base in seq if base in 'GC')
    return gc / len(seq) * 100 if seq else 0.0

def calculate_cai(seq, reference_table):
    from collections import Counter
    codons = [seq[i:i+3] for i in range(0, len(seq), 3)]
    weights = []
    for codon in codons:
        if len(codon) != 3:
            continue
        aa = Seq(codon).translate()
        ref_codon = reference_table.get(str(aa), None)
        weight = 1.0 if ref_codon and codon == ref_codon else 0.5
        weights.append(weight)
    import math
    if not weights:
        return 0.0
    return math.exp(sum(map(lambda x: math.log(x), weights)) / len(weights))

def read_fasta_mrna(filepath):
    for record in SeqIO.parse(filepath, "fasta"):
        return str(record.seq).upper().replace('\n', '').replace(' ', ''), record.id
    raise ValueError("No sequence found in FASTA file.")

def write_fasta(seq, seq_id, filename, line_width=70):
    with open(filename, "w") as f:
        f.write(f">{seq_id}_human_codon_optimized\n")
        for i in range(0, len(seq), line_width):
            f.write(seq[i:i+line_width] + "\n")

def write_report(report_path, mrna_seq, aa_seq, optimized_dna, gc, cai):
    with open(report_path, "w") as f:
        f.write("Codon Optimization Report\n")
        f.write("========================\n")
        f.write(f"Input mRNA sequence:\n{mrna_seq}\n\n")
        f.write(f"Translated amino acid sequence:\n{aa_seq}\n\n")
        f.write(f"Codon-optimized DNA sequence:\n{optimized_dna}\n\n")
        f.write(f"GC-content: {gc:.2f}%\n")
        f.write(f"CAI (Codon Adaptation Index): {cai:.2f}\n")


def main(
    fasta_file_path: str,
    output_fasta_path: str = "./results/optimized_sequence.fasta",
    output_report_path: str = "./results/optimization_report.txt",
    save_outputs: bool = True
):
    """
    Generalized function to process and optimize an mRNA sequence.

    Args:
        fasta_file_path (str): Path to input FASTA file containing mRNA sequence.
        codon_table (dict): Codon usage table for optimization (e.g., HUMAN_CODON_TABLE).
        output_fasta_path (str): Path to save optimized FASTA sequence.
        output_report_path (str): Path to save optimization report.
        save_outputs (bool): Whether to save output files.

    Returns:
        dict: Dictionary containing original mRNA, amino acid sequence, optimized DNA, GC content, and CAI.
    """
    codon_table=HUMAN_CODON_TABLE
    # Read mRNA sequence
    mrna_seq, seq_id = read_fasta_mrna(fasta_file_path)

    # Translate to amino acids
    aa_seq = translate_mrna(mrna_seq)

    # Codon optimize
    optimized_dna = codon_optimize(aa_seq, codon_table)

    # GC content
    gc = gc_content(optimized_dna)

    # CAI
    cai = calculate_cai(optimized_dna, codon_table)

    # Save outputs
    if save_outputs:
        write_fasta(optimized_dna, seq_id, output_fasta_path)
        write_report(output_report_path, mrna_seq, aa_seq, optimized_dna, gc, cai)

    return {
        "seq_id": seq_id,
        "original_mrna": mrna_seq,
        "amino_acid_sequence": aa_seq,
        "optimized_dna": optimized_dna,
        "gc_content": gc,
        "cai": cai
    }

if __name__ == "__main__":
    # from codon_utils import HUMAN_CODON_TABLE  # assuming import or your own defined table

    result = main(
        fasta_file_path="./results/output_mrna.fasta",
        
    )

    print("Optimization Complete!")
    print("GC Content: {:.2f}%".format(result["gc_content"]))
    print("CAI Score: {:.2f}".format(result["cai"]))
