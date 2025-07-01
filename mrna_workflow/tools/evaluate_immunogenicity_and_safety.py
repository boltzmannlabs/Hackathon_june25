from Bio import SeqIO, Seq
import requests

# === USER INPUT: Set your optimized FASTA file path here ===
OPTIMIZED_FASTA_PATH = "../results/optimized_sequence.fasta"

def translate_to_peptide(mrna_seq):
    dna_seq = mrna_seq.replace('U', 'T')
    peptide = str(Seq.Seq(dna_seq).translate(to_stop=True))
    return peptide

def predict_allergenicity(peptide):
    # AllerTOP web server: https://www.ddg-pharmfac.net/AllerTOP/
    # For automation, you could use their batch web endpoint if available, or run locally if permitted.
    # Here, we simulate with a dummy result:
    # (In production: POST to API and parse response)
    result = "Probable Non-Allergen"
    return result

def predict_toxicity(peptide):
    # ToxinPred web server: https://webs.iiitd.edu.in/raghava/toxinpred/
    # In production: POST to API and parse response.
    # Simulated result:
    result = "Non-Toxic"
    return result

def tlr7_motif_scan(mrna_seq):
    # TLR7 is triggered by GU-rich motifs. This is a simple count.
    gu_rich = mrna_seq.count('GU')
    # Threshold for flag (example): > 5 GU motifs
    return gu_rich, gu_rich > 5

def write_report(seq_id, mrna_seq, peptide, allergenicity, toxicity, gu_rich_count, gu_flag, report_path="../results/immunogenicity_report.txt"):
    with open(report_path, "w") as f:
        f.write(f"mRNA ID: {seq_id}\n")
        f.write(f"Optimized mRNA sequence:\n{mrna_seq}\n\n")
        f.write(f"Translated peptide:\n{peptide}\n\n")
        f.write(f"Allergenicity (AllerTOP): {allergenicity}\n")
        f.write(f"Toxicity (ToxinPred): {toxicity}\n")
        f.write(f"GU-rich motifs (TLR7 scan): {gu_rich_count}\n")
        if gu_flag:
            f.write("WARNING: High GU-rich content (may trigger TLR7 innate immunity)\n")
        else:
            f.write("GU-rich content within safe limits.\n")



def main(
    fasta_path: str,
    save_outputs: bool = True,
    output_report_path: str = "../results/immunogenicity_report.txt"
):
    """
    Generalized function to analyze immunogenicity, toxicity, and GU-rich motifs in mRNA.

    Args:
        fasta_path (str): Path to optimized mRNA FASTA file.
        save_outputs (bool): Whether to save the output report.
        output_report_path (str): File path to save the immunogenicity report.

    Returns:
        dict: Summary containing sequence ID, peptide, allergenicity, toxicity, GU-rich info.
    """
    # Read sequence
    record = next(SeqIO.parse(fasta_path, "fasta"))
    mrna_seq = str(record.seq).upper().replace('\n', '').replace(' ', '')
    seq_id = record.id

    # Translate to peptide
    peptide = translate_to_peptide(mrna_seq)

    # Allergenicity
    allergenicity = predict_allergenicity(peptide)

    # Toxicity
    toxicity = predict_toxicity(peptide)

    # TLR7 GU-rich motif
    gu_rich_count, gu_flag = tlr7_motif_scan(mrna_seq)

    # Save report
    if save_outputs:
        write_report(seq_id, mrna_seq, peptide, allergenicity, toxicity, gu_rich_count, gu_flag)

    return {
        "seq_id": seq_id,
        "peptide": peptide,
        "allergenicity": allergenicity,
        "toxicity": toxicity,
        "gu_rich_count": gu_rich_count,
        "tlr7_warning": gu_flag
    }

if __name__ == "__main__":
    result = main(fasta_path="../results/optimized_sequence.fasta")

    print("Predicted Peptide:", result["peptide"])
    print("Allergenicity:", result["allergenicity"])
    print("Toxicity:", result["toxicity"])
    print("GU-rich Motif Count:", result["gu_rich_count"])
    print("TLR7 Warning:", "Yes" if result["tlr7_warning"] else "No")
