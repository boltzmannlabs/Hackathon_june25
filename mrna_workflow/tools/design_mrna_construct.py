import pandas as pd
import numpy as np
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio import SeqIO
from Bio.SeqUtils import gc_fraction as GC
from Bio.SeqUtils import molecular_weight
import json
import re
from typing import List, Dict, Tuple, Optional, Union
from dataclasses import dataclass, field
import logging
from itertools import combinations
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class mRNAConstruct:
    """Data class to store mRNA construct information"""
    construct_id: str
    epitopes: List[str]
    protein_ids: List[str]
    epitope_types: List[str]
    
    # mRNA components
    five_cap: str = "m7G"
    five_utr: str = ""
    kozak_sequence: str = ""
    signal_peptide: str = ""
    start_codon: str = "ATG"
    coding_sequence: str = ""
    stop_codon: str = "TAA"
    three_utr: str = ""
    poly_a_tail: str = ""
    
    # Optimization scores
    translation_efficiency: float = 0.0
    stability_score: float = 0.0
    gc_content: float = 0.0
    codon_adaptation_index: float = 0.0
    
    # Full sequences
    full_mrna_sequence: str = ""
    protein_sequence: str = ""
    
    def __post_init__(self):
        """Calculate derived properties after initialization"""
        if self.full_mrna_sequence:
            self.gc_content = GC(self.full_mrna_sequence)

class mRNAConstructDesigner:
    """
    Comprehensive mRNA construct design system
    """
    
    def __init__(self, species: str = "human", optimize_for: str = "expression"):
        """
        Initialize the mRNA construct designer
        
        Args:
            species: Target species for codon optimization ("human", "mouse", etc.)
            optimize_for: Optimization target ("expression", "stability", "both")
        """
        self.species = species
        self.optimize_for = optimize_for
        
        # Load codon usage tables and optimization parameters
        self.codon_table = self._load_codon_table()
        self.optimal_codons = self._load_optimal_codons()
        self.utr_library = self._load_utr_library()
        self.kozak_sequences = self._load_kozak_sequences()
        self.signal_peptides = self._load_signal_peptides()
        
        # mRNA design parameters
        self.max_epitopes_per_construct = 10
        self.linker_sequences = {
            'flexible': 'GGGGS',  # Flexible linker
            'rigid': 'EAAAK',     # Rigid alpha-helical linker
            'short': 'GS',        # Short linker
            'long': 'GGGGSGGGGS'  # Long flexible linker
        }
        
    def load_epitopes_from_csv(self, csv_file: str, 
                              min_score: float = 0.6,
                              max_epitopes: int = 50) -> pd.DataFrame:
        """
        Load and filter epitopes from CSV file
        
        Args:
            csv_file: Path to CSV file with epitope predictions
            min_score: Minimum composite score threshold
            max_epitopes: Maximum number of epitopes to select
            
        Returns:
            Filtered DataFrame of epitopes
        """
        try:
            df = pd.read_csv(csv_file)
            logger.info(f"Loaded {len(df)} epitopes from {csv_file}")
            
            # Filter by score if available
            if 'composite_score' in df.columns:
                df = df[df['composite_score'] >= min_score]
                df = df.sort_values('composite_score', ascending=False)
            elif 'immunogenicity_score' in df.columns:
                df = df[df['immunogenicity_score'] >= min_score]
                df = df.sort_values('immunogenicity_score', ascending=False)
            
            # Limit number of epitopes
            df = df.head(max_epitopes)
            
            logger.info(f"Selected {len(df)} epitopes for construct design")
            return df
            
        except Exception as e:
            logger.error(f"Error loading epitopes from CSV: {e}")
            raise
    
    def design_single_epitope_constructs(self, epitopes_df: pd.DataFrame) -> List[mRNAConstruct]:
        """
        Design individual mRNA constructs for each epitope
        
        Args:
            epitopes_df: DataFrame with epitope information
            
        Returns:
            List of mRNA constructs
        """
        constructs = []
        
        for idx, row in epitopes_df.iterrows():
            construct_id = f"single_epitope_{idx}"
            epitope_seq = row['peptide']
            protein_id = row['protein_id']
            epitope_type = row['epitope_type']
            
            # Design construct for single epitope
            construct = self._design_construct(
                construct_id=construct_id,
                epitopes=[epitope_seq],
                protein_ids=[protein_id],
                epitope_types=[epitope_type]
            )
            
            constructs.append(construct)
        
        logger.info(f"Designed {len(constructs)} single-epitope constructs")
        return constructs
    
    def design_multi_epitope_constructs(self, epitopes_df: pd.DataFrame,
                                       strategy: str = "mixed") -> List[mRNAConstruct]:
        """
        Design multi-epitope mRNA constructs
        
        Args:
            epitopes_df: DataFrame with epitope information
            strategy: Design strategy ("mixed", "bcell_only", "tcell_only", "protein_grouped")
            
        Returns:
            List of multi-epitope mRNA constructs
        """
        constructs = []
        
        if strategy == "mixed":
            constructs.extend(self._design_mixed_constructs(epitopes_df))
        elif strategy == "bcell_only":
            bcell_df = epitopes_df[epitopes_df['epitope_type'] == 'B-cell']
            constructs.extend(self._design_type_specific_constructs(bcell_df, "bcell"))
        elif strategy == "tcell_only":
            tcell_df = epitopes_df[epitopes_df['epitope_type'] == 'T-cell']
            constructs.extend(self._design_type_specific_constructs(tcell_df, "tcell"))
        elif strategy == "protein_grouped":
            constructs.extend(self._design_protein_grouped_constructs(epitopes_df))
        
        logger.info(f"Designed {len(constructs)} multi-epitope constructs using {strategy} strategy")
        return constructs
    
    def _design_mixed_constructs(self, epitopes_df: pd.DataFrame) -> List[mRNAConstruct]:
        """Design constructs mixing B-cell and T-cell epitopes"""
        constructs = []
        
        # Group epitopes by type
        bcell_epitopes = epitopes_df[epitopes_df['epitope_type'] == 'B-cell']
        tcell_epitopes = epitopes_df[epitopes_df['epitope_type'] == 'T-cell']
        
        # Create balanced constructs
        num_constructs = min(3, max(len(bcell_epitopes)//3, len(tcell_epitopes)//3))
        
        for i in range(num_constructs):
            construct_id = f"mixed_construct_{i+1}"
            
            # Select epitopes for this construct
            bcell_subset = bcell_epitopes.iloc[i*3:(i+1)*3]
            tcell_subset = tcell_epitopes.iloc[i*3:(i+1)*3]
            
            combined_df = pd.concat([bcell_subset, tcell_subset])
            
            epitopes = combined_df['peptide'].tolist()
            protein_ids = combined_df['protein_id'].tolist()
            epitope_types = combined_df['epitope_type'].tolist()
            
            if epitopes:  # Only create construct if epitopes exist
                construct = self._design_construct(
                    construct_id=construct_id,
                    epitopes=epitopes,
                    protein_ids=protein_ids,
                    epitope_types=epitope_types
                )
                constructs.append(construct)
        
        return constructs
    
    def _design_type_specific_constructs(self, epitopes_df: pd.DataFrame, 
                                        construct_type: str) -> List[mRNAConstruct]:
        """Design constructs for specific epitope types"""
        constructs = []
        
        # Split epitopes into groups
        epitope_groups = [epitopes_df.iloc[i:i+self.max_epitopes_per_construct] 
                         for i in range(0, len(epitopes_df), self.max_epitopes_per_construct)]
        
        for i, group in enumerate(epitope_groups):
            construct_id = f"{construct_type}_construct_{i+1}"
            
            epitopes = group['peptide'].tolist()
            protein_ids = group['protein_id'].tolist()
            epitope_types = group['epitope_type'].tolist()
            
            construct = self._design_construct(
                construct_id=construct_id,
                epitopes=epitopes,
                protein_ids=protein_ids,
                epitope_types=epitope_types
            )
            constructs.append(construct)
        
        return constructs
    
    def _design_protein_grouped_constructs(self, epitopes_df: pd.DataFrame) -> List[mRNAConstruct]:
        """Design constructs grouped by source protein"""
        constructs = []
        
        # Group by protein ID
        protein_groups = epitopes_df.groupby('protein_id')
        
        for protein_id, group in protein_groups:
            # Limit epitopes per protein
            group = group.head(self.max_epitopes_per_construct)
            
            construct_id = f"protein_{protein_id}_construct"
            
            epitopes = group['peptide'].tolist()
            protein_ids = group['protein_id'].tolist()
            epitope_types = group['epitope_type'].tolist()
            
            construct = self._design_construct(
                construct_id=construct_id,
                epitopes=epitopes,
                protein_ids=protein_ids,
                epitope_types=epitope_types
            )
            constructs.append(construct)
        
        return constructs
    
    def _design_construct(self, construct_id: str, epitopes: List[str],
                         protein_ids: List[str], epitope_types: List[str]) -> mRNAConstruct:
        """
        Design a complete mRNA construct for given epitopes
        """
        # Initialize construct
        construct = mRNAConstruct(
            construct_id=construct_id,
            epitopes=epitopes,
            protein_ids=protein_ids,
            epitope_types=epitope_types
        )
        
        # Design coding sequence
        construct.coding_sequence = self._create_coding_sequence(epitopes, epitope_types)
        construct.protein_sequence = str(Seq(construct.coding_sequence).translate())
        
        # Select optimal components
        construct.five_utr = self._select_optimal_5utr()
        construct.kozak_sequence = self._select_optimal_kozak()
        construct.three_utr = self._select_optimal_3utr()
        construct.poly_a_tail = self._generate_poly_a_tail()
        
        # Add signal peptide if needed
        if any(epi_type == 'B-cell' for epi_type in epitope_types):
            construct.signal_peptide = self._select_signal_peptide()
        
        # Optimize coding sequence
        construct.coding_sequence = self._optimize_codons(construct.coding_sequence)
        
        # Assemble full mRNA sequence
        construct.full_mrna_sequence = self._assemble_mrna(construct)
        
        # Calculate optimization scores
        construct.translation_efficiency = self._calculate_translation_efficiency(construct)
        construct.stability_score = self._calculate_stability_score(construct)
        construct.codon_adaptation_index = self._calculate_cai(construct.coding_sequence)
        construct.gc_content = GC(construct.full_mrna_sequence)
        
        return construct
    
    def _create_coding_sequence(self, epitopes: List[str], epitope_types: List[str]) -> str:
        """
        Create coding sequence from epitopes with appropriate linkers
        """
        coding_seq = ""
        
        for i, (epitope, epi_type) in enumerate(zip(epitopes, epitope_types)):
            # Convert peptide to DNA sequence
            epitope_dna = self._peptide_to_dna(epitope)
            coding_seq += epitope_dna
            
            # Add linker between epitopes (except for the last one)
            if i < len(epitopes) - 1:
                linker_type = self._select_linker_type(epi_type, epitope_types[i+1])
                linker_dna = self._peptide_to_dna(self.linker_sequences[linker_type])
                coding_seq += linker_dna
        
        return coding_seq
    
    def _peptide_to_dna(self, peptide: str) -> str:
        """Convert peptide sequence to DNA using optimal codons"""
        dna_seq = ""
        for aa in peptide:
            if aa in self.optimal_codons:
                dna_seq += self.optimal_codons[aa]
            else:
                # Fallback to first codon in standard genetic code
                dna_seq += self._get_codon_for_aa(aa)
        return dna_seq
    
    def _get_codon_for_aa(self, aa: str) -> str:
        """Get a codon for amino acid (fallback method)"""
        aa_to_codon = {
            'A': 'GCT', 'R': 'CGT', 'N': 'AAT', 'D': 'GAT', 'C': 'TGT',
            'Q': 'CAG', 'E': 'GAG', 'G': 'GGT', 'H': 'CAT', 'I': 'ATT',
            'L': 'CTG', 'K': 'AAG', 'M': 'ATG', 'F': 'TTT', 'P': 'CCT',
            'S': 'TCT', 'T': 'ACT', 'W': 'TGG', 'Y': 'TAT', 'V': 'GTT'
        }
        return aa_to_codon.get(aa, 'NNN')
    
    def _select_linker_type(self, current_type: str, next_type: str) -> str:
        """Select appropriate linker type based on epitope types"""
        if current_type == 'B-cell' and next_type == 'B-cell':
            return 'flexible'
        elif current_type == 'T-cell' and next_type == 'T-cell':
            return 'short'
        else:  # Mixed types
            return 'flexible'
    
    def _select_optimal_5utr(self) -> str:
        """Select optimal 5' UTR sequence"""
        # High-efficiency 5' UTRs
        utrs = self.utr_library['5_utr']
        return max(utrs.items(), key=lambda x: x[1]['efficiency'])[0]
    
    def _select_optimal_kozak(self) -> str:
        """Select optimal Kozak sequence"""
        kozak_seqs = self.kozak_sequences
        return max(kozak_seqs.items(), key=lambda x: x[1]['strength'])[0]
    
    def _select_optimal_3utr(self) -> str:
        """Select optimal 3' UTR sequence"""
        utrs = self.utr_library['3_utr']
        return max(utrs.items(), key=lambda x: x[1]['stability'])[0]
    
    def _generate_poly_a_tail(self, length: int = 120) -> str:
        """Generate poly-A tail of specified length"""
        return 'A' * length
    
    def _select_signal_peptide(self) -> str:
        """Select appropriate signal peptide"""
        signal_peptides = self.signal_peptides
        return max(signal_peptides.items(), key=lambda x: x[1]['efficiency'])[0]
    
    def _optimize_codons(self, coding_seq: str) -> str:
        """Optimize codon usage for expression"""
        # Convert to amino acids and back with optimal codons
        try:
            protein_seq = str(Seq(coding_seq).translate())
            optimized_seq = ""
            
            for aa in protein_seq:
                if aa == '*':  # Stop codon
                    break
                if aa in self.optimal_codons:
                    optimized_seq += self.optimal_codons[aa]
                else:
                    optimized_seq += self._get_codon_for_aa(aa)
            
            return optimized_seq
        except:
            return coding_seq  # Return original if optimization fails
    
    def _assemble_mrna(self, construct: mRNAConstruct) -> str:
        """Assemble complete mRNA sequence"""
        # Note: 5' cap is added post-transcriptionally, not included in sequence
        sequence_parts = []
        
        # 5' UTR
        if construct.five_utr:
            sequence_parts.append(construct.five_utr)
        
        # Kozak sequence
        if construct.kozak_sequence:
            sequence_parts.append(construct.kozak_sequence)
        
        # Start codon
        sequence_parts.append(construct.start_codon)
        
        # Signal peptide (if present)
        if construct.signal_peptide:
            signal_dna = self._peptide_to_dna(construct.signal_peptide)
            sequence_parts.append(signal_dna)
        
        # Coding sequence
        sequence_parts.append(construct.coding_sequence)
        
        # Stop codon
        sequence_parts.append(construct.stop_codon)
        
        # 3' UTR
        if construct.three_utr:
            sequence_parts.append(construct.three_utr)
        
        # Poly-A tail
        if construct.poly_a_tail:
            sequence_parts.append(construct.poly_a_tail)
        
        return ''.join(sequence_parts)
    
    def _calculate_translation_efficiency(self, construct: mRNAConstruct) -> float:
        """Calculate predicted translation efficiency"""
        score = 0.0
        
        # Kozak strength contribution
        kozak_strength = self.kozak_sequences.get(construct.kozak_sequence, {}).get('strength', 0.5)
        score += kozak_strength * 0.3
        
        # 5' UTR efficiency contribution
        utr_efficiency = self.utr_library['5_utr'].get(construct.five_utr, {}).get('efficiency', 0.5)
        score += utr_efficiency * 0.3
        
        # GC content contribution (optimal around 50-60%)
        gc_content = GC(construct.coding_sequence)
        if 45 <= gc_content <= 65:
            gc_score = 1.0 - abs(gc_content - 55) / 10
        else:
            gc_score = max(0.0, 1.0 - abs(gc_content - 55) / 25)
        score += gc_score * 0.2
        
        # Codon optimization contribution
        score += construct.codon_adaptation_index * 0.2
        
        return min(1.0, score)
    
    def _calculate_stability_score(self, construct: mRNAConstruct) -> float:
        """Calculate mRNA stability score"""
        score = 0.0
        
        # 3' UTR stability contribution
        utr_stability = self.utr_library['3_utr'].get(construct.three_utr, {}).get('stability', 0.5)
        score += utr_stability * 0.4
        
        # Poly-A tail length contribution
        polya_length = len(construct.poly_a_tail)
        if 100 <= polya_length <= 150:
            polya_score = 1.0
        else:
            polya_score = max(0.0, 1.0 - abs(polya_length - 125) / 50)
        score += polya_score * 0.3
        
        # GC content stability
        gc_content = GC(construct.full_mrna_sequence)
        if 40 <= gc_content <= 60:
            gc_stability = 1.0 - abs(gc_content - 50) / 10
        else:
            gc_stability = max(0.0, 1.0 - abs(gc_content - 50) / 25)
        score += gc_stability * 0.3
        
        return min(1.0, score)
    
    def _calculate_cai(self, coding_seq: str) -> float:
        """Calculate Codon Adaptation Index (simplified)"""
        if len(coding_seq) % 3 != 0:
            return 0.0
        
        cai_sum = 0.0
        codon_count = 0
        
        for i in range(0, len(coding_seq), 3):
            codon = coding_seq[i:i+3]
            aa = str(Seq(codon).translate())
            
            if aa != '*' and aa in self.optimal_codons:
                if self.optimal_codons[aa] == codon:
                    cai_sum += 1.0
                else:
                    cai_sum += 0.5  # Suboptimal codon
                codon_count += 1
        
        return cai_sum / codon_count if codon_count > 0 else 0.0
    
    def _load_codon_table(self) -> Dict:
        """Load species-specific codon usage table"""
        # Simplified human codon usage frequencies
        return {
            'TTT': 0.45, 'TTC': 0.55, 'TTA': 0.07, 'TTG': 0.13,
            'TCT': 0.18, 'TCC': 0.22, 'TCA': 0.15, 'TCG': 0.06,
            'TAT': 0.43, 'TAC': 0.57, 'TAA': 0.28, 'TAG': 0.20,
            'TGT': 0.45, 'TGC': 0.55, 'TGA': 0.52, 'TGG': 1.00,
            'CTT': 0.13, 'CTC': 0.20, 'CTA': 0.07, 'CTG': 0.41,
            'CCT': 0.28, 'CCC': 0.33, 'CCA': 0.27, 'CCG': 0.11,
            'CAT': 0.41, 'CAC': 0.59, 'CAA': 0.25, 'CAG': 0.75,
            'CGT': 0.08, 'CGC': 0.19, 'CGA': 0.11, 'CGG': 0.21,
            'ATT': 0.36, 'ATC': 0.48, 'ATA': 0.16, 'ATG': 1.00,
            'ACT': 0.24, 'ACC': 0.36, 'ACA': 0.28, 'ACG': 0.12,
            'AAT': 0.46, 'AAC': 0.54, 'AAA': 0.42, 'AAG': 0.58,
            'AGT': 0.15, 'AGC': 0.24, 'AGA': 0.20, 'AGG': 0.20,
            'GTT': 0.18, 'GTC': 0.24, 'GTA': 0.11, 'GTG': 0.47,
            'GCT': 0.26, 'GCC': 0.40, 'GCA': 0.23, 'GCG': 0.11,
            'GAT': 0.46, 'GAC': 0.54, 'GAA': 0.42, 'GAG': 0.58,
            'GGT': 0.16, 'GGC': 0.34, 'GGA': 0.25, 'GGG': 0.25
        }
    
    def _load_optimal_codons(self) -> Dict:
        """Load optimal codons for each amino acid"""
        return {
            'A': 'GCC', 'R': 'CGC', 'N': 'AAC', 'D': 'GAC', 'C': 'TGC',
            'Q': 'CAG', 'E': 'GAG', 'G': 'GGC', 'H': 'CAC', 'I': 'ATC',
            'L': 'CTG', 'K': 'AAG', 'M': 'ATG', 'F': 'TTC', 'P': 'CCC',
            'S': 'AGC', 'T': 'ACC', 'W': 'TGG', 'Y': 'TAC', 'V': 'GTG'
        }
    
    def _load_utr_library(self) -> Dict:
        """Load UTR sequences with efficiency/stability scores"""
        return {
            '5_utr': {
                'GGGAAATAAGAGAGAAAAGAAGAGTAAGAAGAAATATAAGAGCCACC': {'efficiency': 0.9, 'name': 'high_efficiency_1'},
                'GGAAATAAGAGAGAAAAGAAGAGTAAGAAGAAATATAAGAGCC': {'efficiency': 0.8, 'name': 'high_efficiency_2'},
                'GGGAAATAAGAGAGAAAAGAAGAGTAAGAAG': {'efficiency': 0.7, 'name': 'medium_efficiency'}
            },
            '3_utr': {
                'AATAAAAGATCAGGTACAAACTGGAATGTATGTCGCCCCTAGTCAGCTGTTAATCACTT': {'stability': 0.9, 'name': 'high_stability_1'},
                'AATAAAAGATCAGGTACAAACTGGAATGTATGTCGCCCCTAG': {'stability': 0.8, 'name': 'high_stability_2'},
                'AATAAAAGATCAGGTACAAACTGGAA': {'stability': 0.6, 'name': 'medium_stability'}
            }
        }
    
    def _load_kozak_sequences(self) -> Dict:
        """Load Kozak sequences with strength scores"""
        return {
            'GCCACCATGG': {'strength': 1.0, 'name': 'optimal_kozak'},
            'GCCATGG': {'strength': 0.8, 'name': 'strong_kozak'},
            'ACCATGG': {'strength': 0.6, 'name': 'medium_kozak'},
            'ATGG': {'strength': 0.4, 'name': 'weak_kozak'}
        }
    
    def _load_signal_peptides(self) -> Dict:
        """Load signal peptide sequences"""
        return {
            'MKHLWFFLLLVAAPRWVLS': {'efficiency': 0.9, 'name': 'tPA_signal'},
            'MDSKGSSQKGSRLLLLLVVSNLLLCQGVVS': {'efficiency': 0.8, 'name': 'IgG_signal'},
            'MKWVTFISLLFLFSSAYS': {'efficiency': 0.7, 'name': 'albumin_signal'}
        }
    
    def export_constructs_to_fasta(self, constructs: List[mRNAConstruct], 
                                  output_file: str, sequence_type: str = "mrna"):
        """
        Export mRNA constructs to FASTA format
        
        Args:
            constructs: List of mRNA constructs
            output_file: Output FASTA file path
            sequence_type: Type of sequence to export ("mrna", "cds", "protein")
        """
        records = []
        
        for construct in constructs:
            if sequence_type == "mrna":
                seq = construct.full_mrna_sequence
                desc = f"mRNA construct | Epitopes: {len(construct.epitopes)} | GC: {construct.gc_content:.1f}% | Translation: {construct.translation_efficiency:.2f}"
            elif sequence_type == "cds":
                seq = construct.start_codon + construct.coding_sequence + construct.stop_codon
                desc = f"CDS | Epitopes: {len(construct.epitopes)} | CAI: {construct.codon_adaptation_index:.2f}"
            elif sequence_type == "protein":
                seq = construct.protein_sequence
                desc = f"Protein | Epitopes: {len(construct.epitopes)} | MW: {molecular_weight(seq, 'protein'):.1f} Da"
            else:
                continue
            
            record = SeqRecord(
                Seq(seq),
                id=construct.construct_id,
                description=desc
            )
            records.append(record)
        
        SeqIO.write(records, output_file, "fasta")
        logger.info(f"Exported {len(records)} constructs to {output_file}")
    
    def export_constructs_to_csv(self, constructs: List[mRNAConstruct], output_file: str):
        """Export construct details to CSV"""
        data = []
        
        for construct in constructs:
            row = {
                'construct_id': construct.construct_id,
                'num_epitopes': len(construct.epitopes),
                'epitope_types': '|'.join(set(construct.epitope_types)),
                'protein_ids': '|'.join(set(construct.protein_ids)),
                'epitopes': '|'.join(construct.epitopes),
                'mrna_length': len(construct.full_mrna_sequence),
                'protein_length': len(construct.protein_sequence),
                'gc_content': construct.gc_content,
                'translation_efficiency': construct.translation_efficiency,
                'stability_score': construct.stability_score,
                'codon_adaptation_index': construct.codon_adaptation_index,
                'five_utr': construct.five_utr,
                'kozak_sequence': construct.kozak_sequence,
                'three_utr': construct.three_utr,
                'poly_a_length': len(construct.poly_a_tail),
                'signal_peptide': construct.signal_peptide,
                'molecular_weight': molecular_weight(construct.protein_sequence, 'protein') if construct.protein_sequence else 0,
                'full_mrna_sequence': construct.full_mrna_sequence,
                'protein_sequence': construct.protein_sequence
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        df.to_csv(output_file, index=False)
        logger.info(f"Exported construct details to {output_file}")
    
    def generate_construct_report(self, constructs: List[mRNAConstruct], output_file: str):
        """Generate comprehensive analysis report"""
        with open(output_file, 'w') as f:
            f.write("mRNA Vaccine Construct Design Report\n")
            f.write("=" * 40 + "\n\n")
            
            # Summary statistics
            f.write(f"Total constructs designed: {len(constructs)}\n")
            f.write(f"Average epitopes per construct: {np.mean([len(c.epitopes) for c in constructs]):.1f}\n")
            f.write(f"Average mRNA length: {np.mean([len(c.full_mrna_sequence) for c in constructs]):.0f} bp\n")
            f.write(f"Average GC content: {np.mean([c.gc_content for c in constructs]):.1f}%\n")
            f.write(f"Average translation efficiency: {np.mean([c.translation_efficiency for c in constructs]):.2f}\n")
            f.write(f"Average stability score: {np.mean([c.stability_score for c in constructs]):.2f}\n\n")
            
            # Top constructs
            sorted_constructs = sorted(constructs, 
                                     key=lambda x: (x.translation_efficiency + x.stability_score)/2, 
                                     reverse=True)
            
            f.write("Top 5 Constructs (by combined score):\n")
            f.write("-" * 35 + "\n")
            for i, construct in enumerate(sorted_constructs[:5]):
                combined_score = (construct.translation_efficiency + construct.stability_score) / 2
                f.write(f"{i+1}. {construct.construct_id}\n")
                f.write(f"   Epitopes: {len(construct.epitopes)}\n")
                f.write(f"   Combined Score: {combined_score:.3f}\n")
                f.write(f"   Translation Efficiency: {construct.translation_efficiency:.3f}\n")
                f.write(f"   Stability Score: {construct.stability_score:.3f}\n")
                f.write(f"   GC Content: {construct.gc_content:.1f}%\n\n")
        
        logger.info(f"Generated construct report: {output_file}")
    
    def optimize_construct_portfolio(self, constructs: List[mRNAConstruct], 
                                   max_constructs: int = 5) -> List[mRNAConstruct]:
        """
        Select optimal portfolio of constructs for maximum coverage
        """
        if len(constructs) <= max_constructs:
            return constructs
        
        # Calculate diversity scores
        construct_scores = []
        for construct in constructs:
            # Combined performance score
            perf_score = (construct.translation_efficiency + construct.stability_score) / 2
            
            # Epitope diversity (unique epitopes)
            epitope_diversity = len(set(construct.epitopes))
            
            # Type diversity (B-cell vs T-cell)
            type_diversity = len(set(construct.epitope_types))
            
            # Protein diversity
            protein_diversity = len(set(construct.protein_ids))
            
            total_score = (perf_score * 0.4 + 
                          epitope_diversity * 0.3 + 
                          type_diversity * 0.2 + 
                          protein_diversity * 0.1)
            
            construct_scores.append((construct, total_score))
        
        # Sort by total score and select top constructs
        construct_scores.sort(key=lambda x: x[1], reverse=True)
        selected_constructs = [cs[0] for cs in construct_scores[:max_constructs]]
        
        logger.info(f"Selected {len(selected_constructs)} constructs from portfolio optimization")
        return selected_constructs
    
    def validate_constructs(self, constructs: List[mRNAConstruct]) -> Dict[str, List[str]]:
        """
        Validate constructs for potential issues
        """
        issues = {
            'warnings': [],
            'errors': [],
            'recommendations': []
        }
        
        for construct in constructs:
            construct_id = construct.construct_id
            
            # Check sequence length
            if len(construct.full_mrna_sequence) > 5000:
                issues['warnings'].append(f"{construct_id}: Long mRNA sequence ({len(construct.full_mrna_sequence)} bp)")
            
            # Check GC content
            if construct.gc_content < 30 or construct.gc_content > 70:
                issues['warnings'].append(f"{construct_id}: Extreme GC content ({construct.gc_content:.1f}%)")
            
            # Check for stop codons in coding sequence
            if 'TAA' in construct.coding_sequence[:-3] or 'TAG' in construct.coding_sequence[:-3] or 'TGA' in construct.coding_sequence[:-3]:
                issues['errors'].append(f"{construct_id}: Premature stop codon detected")
            
            # Check translation efficiency
            if construct.translation_efficiency < 0.5:
                issues['recommendations'].append(f"{construct_id}: Low translation efficiency - consider optimizing UTRs")
            
            # Check stability
            if construct.stability_score < 0.5:
                issues['recommendations'].append(f"{construct_id}: Low stability - consider optimizing 3' UTR")
            
            # Check epitope diversity
            if len(set(construct.epitope_types)) == 1 and len(construct.epitopes) > 3:
                issues['recommendations'].append(f"{construct_id}: Consider mixing epitope types for better immunity")
        
        return issues

class mRNAConstructAnalyzer:
    """
    Additional analysis tools for mRNA constructs
    """
    
    def __init__(self):
        self.analysis_results = {}
    
    def analyze_construct_diversity(self, constructs: List[mRNAConstruct]) -> Dict:
        """Analyze epitope and protein diversity across constructs"""
        all_epitopes = set()
        all_proteins = set()
        epitope_types = []
        
        for construct in constructs:
            all_epitopes.update(construct.epitopes)
            all_proteins.update(construct.protein_ids)
            epitope_types.extend(construct.epitope_types)
        
        type_counts = pd.Series(epitope_types).value_counts()
        
        return {
            'total_unique_epitopes': len(all_epitopes),
            'total_unique_proteins': len(all_proteins),
            'epitope_type_distribution': type_counts.to_dict(),
            'average_epitopes_per_construct': np.mean([len(c.epitopes) for c in constructs])
        }
    
    def compare_optimization_strategies(self, constructs_dict: Dict[str, List[mRNAConstruct]]) -> pd.DataFrame:
        """Compare different optimization strategies"""
        comparison_data = []
        
        for strategy, constructs in constructs_dict.items():
            avg_translation = np.mean([c.translation_efficiency for c in constructs])
            avg_stability = np.mean([c.stability_score for c in constructs])
            avg_gc = np.mean([c.gc_content for c in constructs])
            avg_cai = np.mean([c.codon_adaptation_index for c in constructs])
            avg_length = np.mean([len(c.full_mrna_sequence) for c in constructs])
            
            comparison_data.append({
                'strategy': strategy,
                'num_constructs': len(constructs),
                'avg_translation_efficiency': avg_translation,
                'avg_stability_score': avg_stability,
                'avg_gc_content': avg_gc,
                'avg_cai': avg_cai,
                'avg_mrna_length': avg_length,
                'combined_score': (avg_translation + avg_stability) / 2
            })
        
        return pd.DataFrame(comparison_data).sort_values('combined_score', ascending=False)
    
    def predict_immunogenicity_potential(self, constructs: List[mRNAConstruct]) -> Dict:
        """Predict relative immunogenicity potential"""
        predictions = {}
        
        for construct in constructs:
            # Simple scoring based on epitope types and diversity
            tcell_count = construct.epitope_types.count('T-cell')
            bcell_count = construct.epitope_types.count('B-cell')
            
            # Balance score
            balance_score = min(tcell_count, bcell_count) / max(tcell_count, bcell_count) if max(tcell_count, bcell_count) > 0 else 0
            
            # Diversity score
            diversity_score = len(set(construct.protein_ids)) / len(construct.protein_ids)
            
            # Translation efficiency contribution
            expression_score = construct.translation_efficiency
            
            # Combined immunogenicity potential
            immuno_score = (balance_score * 0.4 + diversity_score * 0.3 + expression_score * 0.3)
            
            predictions[construct.construct_id] = {
                'immunogenicity_score': immuno_score,
                'tcell_epitopes': tcell_count,
                'bcell_epitopes': bcell_count,
                'balance_score': balance_score,
                'diversity_score': diversity_score
            }
        
        return predictions


def main(
    epitope_csv_path: str,
    species: str = "human",
    optimize_for: str = "both",
    min_score: float = 0.7,
    max_epitopes: int = 30,
    max_constructs: int = 10,
    output_prefix: str = "output",
    use_example_on_failure: bool = False
):
    """
    Generalized mRNA construct design function.

    Args:
        epitope_csv_path (str): Path to the epitope CSV file.
        species (str): Species to design for (default: 'human').
        optimize_for (str): Optimization target ('mrna', 'protein', 'both').
        min_score (float): Minimum epitope composite score.
        max_epitopes (int): Maximum number of epitopes to load.
        max_constructs (int): Maximum number of constructs to retain after optimization.
        output_prefix (str): Prefix for output file names.
        use_example_on_failure (bool): Whether to generate example constructs if CSV not found.

    Returns:
        Tuple:
            - optimal_constructs (List[Dict])
            - validation_results (Dict)
    """
    from pathlib import Path
    import pandas as pd

    designer = mRNAConstructDesigner(species=species, optimize_for=optimize_for)

    try:
        epitopes_df = designer.load_epitopes_from_csv(
            epitope_csv_path, min_score=min_score, max_epitopes=max_epitopes
        )

    except FileNotFoundError:
        if not use_example_on_failure:
            raise FileNotFoundError(f"Epitope CSV not found: {epitope_csv_path}")

        epitopes_df = pd.DataFrame({
            'peptide': ['FIAGLIAIV', 'GILGFVFTL', 'KTWGQYWQV', 'RLQSLQTYV'],
            'protein_id': ['spike', 'spike', 'nucleocapsid', 'nucleocapsid'],
            'epitope_type': ['T-cell', 'T-cell', 'B-cell', 'T-cell'],
            'composite_score': [0.85, 0.78, 0.92, 0.71]
        })

    # Design constructs
    single_constructs = designer.design_single_epitope_constructs(epitopes_df)
    mixed_constructs = designer.design_multi_epitope_constructs(epitopes_df, strategy="mixed")
    protein_constructs = designer.design_multi_epitope_constructs(epitopes_df, strategy="protein_grouped")

    all_constructs = single_constructs + mixed_constructs + protein_constructs
    optimal_constructs = designer.optimize_construct_portfolio(all_constructs, max_constructs=max_constructs)
    validation_results = designer.validate_constructs(optimal_constructs)

    # Export outputs
    designer.export_constructs_to_fasta(optimal_constructs, f"{output_prefix}_mrna.fasta", "mrna")
    designer.export_constructs_to_fasta(optimal_constructs, f"{output_prefix}_protein.fasta", "protein")
    designer.export_constructs_to_csv(optimal_constructs, f"{output_prefix}_constructs.csv")
    designer.generate_construct_report(optimal_constructs, f"{output_prefix}_report.txt")

    return optimal_constructs, validation_results

if __name__ == "__main__":
    constructs, results = main(
        epitope_csv_path="./results/epitope_predictions.csv",
        use_example_on_failure=True
    )

    print(f"Generated {len(constructs)} constructs.")
    print("Validation Summary:")
    for key, items in results.items():
        print(f"{key.title()}: {len(items)}")
