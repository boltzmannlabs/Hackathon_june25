import os
import requests
import pandas as pd
import numpy as np
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
import json
import time
from typing import List, Dict, Tuple, Optional
import subprocess
import tempfile
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EpitopeResult:
    """Data class to store epitope prediction results"""
    sequence: str
    protein_id: str
    epitope_type: str  # 'B-cell' or 'T-cell'
    start_pos: int
    end_pos: int
    peptide: str
    immunogenicity_score: float
    conservation_score: float
    toxicity_score: float
    allergenicity_score: float
    binding_affinity: Optional[float] = None
    hla_allele: Optional[str] = None
    prediction_method: str = ""

class EpitopePredictor:
    """
    Comprehensive epitope prediction system integrating multiple tools
    """
    
    def __init__(self, hla_alleles: Optional[List[str]] = None):
        """
        Initialize the epitope predictor
        
        Args:
            hla_alleles: List of HLA alleles for MHC binding prediction
        """
        self.hla_alleles = hla_alleles or [
            'HLA-A*02:01', 'HLA-A*01:01', 'HLA-B*07:02', 'HLA-B*08:01',
            'HLA-C*07:01', 'HLA-DRB1*01:01', 'HLA-DRB1*03:01', 'HLA-DQB1*02:01'
        ]
        self.iedb_url = "http://tools-cluster-interface.iedb.org/tools_api"
        self.results = []
        
    def load_fasta_sequences(self, fasta_file: str) -> Dict[str, str]:
        """
        Load protein sequences from FASTA file
        
        Args:
            fasta_file: Path to FASTA file
            
        Returns:
            Dictionary mapping protein IDs to sequences
        """
        sequences = {}
        try:
            for record in SeqIO.parse(fasta_file, "fasta"):
                sequences[record.id] = str(record.seq)
            logger.info(f"Loaded {len(sequences)} sequences from {fasta_file}")
        except Exception as e:
            logger.error(f"Error loading FASTA file: {e}")
            raise
        
        return sequences
    
    def predict_bcell_epitopes_bepipred(self, sequence: str, protein_id: str) -> List[EpitopeResult]:
        """
        Predict B-cell epitopes using BepiPred-like algorithm
        (Simplified implementation - replace with actual BepiPred API call)
        """
        epitopes = []
        window_size = 20
        threshold = 0.5
        
        # Simplified hydrophilicity-based prediction
        hydrophilicity_scale = {
            'A': -0.5, 'R': 3.0, 'N': 0.2, 'D': 3.0, 'C': -1.0,
            'Q': 0.2, 'E': 3.0, 'G': 0.0, 'H': -0.5, 'I': -1.8,
            'L': -1.8, 'K': 3.0, 'M': -1.3, 'F': -2.5, 'P': 0.0,
            'S': 0.3, 'T': -0.4, 'W': -3.4, 'Y': -2.3, 'V': -1.5
        }
        
        for i in range(len(sequence) - window_size + 1):
            peptide = sequence[i:i + window_size]
            
            # Calculate hydrophilicity score
            score = sum(hydrophilicity_scale.get(aa, 0) for aa in peptide) / len(peptide)
            
            if score > threshold:
                epitope = EpitopeResult(
                    sequence=sequence,
                    protein_id=protein_id,
                    epitope_type='B-cell',
                    start_pos=i + 1,
                    end_pos=i + window_size,
                    peptide=peptide,
                    immunogenicity_score=min(score / 3.0, 1.0),
                    conservation_score=self._calculate_conservation_score(peptide),
                    toxicity_score=self._calculate_toxicity_score(peptide),
                    allergenicity_score=self._calculate_allergenicity_score(peptide),
                    prediction_method="BepiPred-like"
                )
                epitopes.append(epitope)
        
        return epitopes
    
    def predict_tcell_epitopes_netmhcpan(self, sequence: str, protein_id: str) -> List[EpitopeResult]:
        """
        Predict T-cell epitopes using NetMHCpan-like algorithm
        (Simplified implementation - replace with actual NetMHCpan API call)
        """
        epitopes = []
        
        # Predict for different peptide lengths
        for length in [8, 9, 10, 11]:
            for i in range(len(sequence) - length + 1):
                peptide = sequence[i:i + length]
                
                # Simulate binding prediction for each HLA allele
                for hla in self.hla_alleles:
                    binding_score = self._simulate_mhc_binding(peptide, hla)
                    
                    if binding_score > 0.5:  # Threshold for strong binders
                        epitope = EpitopeResult(
                            sequence=sequence,
                            protein_id=protein_id,
                            epitope_type='T-cell',
                            start_pos=i + 1,
                            end_pos=i + length,
                            peptide=peptide,
                            immunogenicity_score=binding_score,
                            conservation_score=self._calculate_conservation_score(peptide),
                            toxicity_score=self._calculate_toxicity_score(peptide),
                            allergenicity_score=self._calculate_allergenicity_score(peptide),
                            binding_affinity=binding_score,
                            hla_allele=hla,
                            prediction_method="NetMHCpan-like"
                        )
                        epitopes.append(epitope)
        
        return epitopes
    
    def predict_epitopes_iedb_api(self, sequence: str, protein_id: str) -> List[EpitopeResult]:
        """
        Call IEDB API for epitope prediction
        (This is a template - actual IEDB API calls would need proper authentication)
        """
        epitopes = []
        
        try:
            # Example API call structure (modify based on actual IEDB API)
            # This is a simplified version - real implementation would need proper IEDB API integration
            
            # For demonstration, we'll simulate API response
            simulated_epitopes = self._simulate_iedb_prediction(sequence, protein_id)
            epitopes.extend(simulated_epitopes)
            
        except Exception as e:
            logger.warning(f"IEDB API call failed: {e}")
            # Fallback to local predictions
            epitopes.extend(self.predict_bcell_epitopes_bepipred(sequence, protein_id))
            epitopes.extend(self.predict_tcell_epitopes_netmhcpan(sequence, protein_id))
        
        return epitopes
    
    def _simulate_iedb_prediction(self, sequence: str, protein_id: str) -> List[EpitopeResult]:
        """Simulate IEDB prediction results"""
        epitopes = []
        
        # Simulate some B-cell epitopes
        for i in range(0, len(sequence) - 15, 30):
            if i + 15 < len(sequence):
                peptide = sequence[i:i + 15]
                epitope = EpitopeResult(
                    sequence=sequence,
                    protein_id=protein_id,
                    epitope_type='B-cell',
                    start_pos=i + 1,
                    end_pos=i + 15,
                    peptide=peptide,
                    immunogenicity_score=np.random.uniform(0.6, 0.9),
                    conservation_score=self._calculate_conservation_score(peptide),
                    toxicity_score=self._calculate_toxicity_score(peptide),
                    allergenicity_score=self._calculate_allergenicity_score(peptide),
                    prediction_method="IEDB"
                )
                epitopes.append(epitope)
        
        return epitopes
    
    def _simulate_mhc_binding(self, peptide: str, hla_allele: str) -> float:
        """
        Simulate MHC binding affinity calculation
        (Replace with actual NetMHCpan implementation)
        """
        # Simplified scoring based on amino acid properties
        score = 0.0
        for aa in peptide:
            if aa in ['F', 'W', 'Y', 'L', 'I', 'V']:  # Hydrophobic residues
                score += 0.1
            elif aa in ['K', 'R', 'H']:  # Positively charged
                score += 0.05
            elif aa in ['D', 'E']:  # Negatively charged
                score += 0.03
        
        # Add some randomness and normalize
        score += np.random.uniform(-0.2, 0.2)
        return max(0.0, min(1.0, score))
    
    def _calculate_conservation_score(self, peptide: str) -> float:
        """
        Calculate conservation score based on amino acid properties
        (In real implementation, this would use multiple sequence alignment)
        """
        # Simplified conservation scoring
        rare_aas = ['C', 'W', 'M', 'H']
        common_aas = ['A', 'L', 'S', 'G', 'V', 'E', 'K', 'I', 'D', 'T']
        
        score = 0.5  # Base score
        for aa in peptide:
            if aa in rare_aas:
                score += 0.02
            elif aa in common_aas:
                score += 0.01
        
        return min(1.0, score)
    
    def _calculate_toxicity_score(self, peptide: str) -> float:
        """
        Calculate toxicity score (lower is better)
        (Simplified implementation - real version would use toxicity databases)
        """
        # Check for potentially toxic motifs
        toxic_motifs = ['CC', 'WW', 'FF', 'KKK', 'RRR']
        toxicity = 0.0
        
        for motif in toxic_motifs:
            if motif in peptide:
                toxicity += 0.2
        
        # Add random component
        toxicity += np.random.uniform(0.0, 0.1)
        
        return min(1.0, toxicity)
    
    def _calculate_allergenicity_score(self, peptide: str) -> float:
        """
        Calculate allergenicity score (lower is better)
        (Simplified implementation - real version would use AllerTOP/AlgPred)
        """
        # Simplified allergenicity scoring
        allergenic_patterns = ['DDDDD', 'FFFFF', 'WWWW', 'YYYY']
        allergenicity = 0.0
        
        for pattern in allergenic_patterns:
            if pattern in peptide:
                allergenicity += 0.3
        
        # Add random component
        allergenicity += np.random.uniform(0.0, 0.15)
        
        return min(1.0, allergenicity)
    
    def filter_epitopes(self, epitopes: List[EpitopeResult], 
                       min_immunogenicity: float = 0.5,
                       max_toxicity: float = 0.3,
                       max_allergenicity: float = 0.3,
                       min_conservation: float = 0.4) -> List[EpitopeResult]:
        """
        Filter epitopes based on scoring criteria
        
        Args:
            epitopes: List of epitope results
            min_immunogenicity: Minimum immunogenicity score
            max_toxicity: Maximum toxicity score
            max_allergenicity: Maximum allergenicity score
            min_conservation: Minimum conservation score
            
        Returns:
            Filtered list of epitopes
        """
        filtered = []
        
        for epitope in epitopes:
            if (epitope.immunogenicity_score >= min_immunogenicity and
                epitope.toxicity_score <= max_toxicity and
                epitope.allergenicity_score <= max_allergenicity and
                epitope.conservation_score >= min_conservation):
                filtered.append(epitope)
        
        logger.info(f"Filtered {len(filtered)} epitopes from {len(epitopes)} candidates")
        return filtered
    
    def rank_epitopes(self, epitopes: List[EpitopeResult]) -> List[EpitopeResult]:
        """
        Rank epitopes by composite score
        
        Args:
            epitopes: List of epitope results
            
        Returns:
            Ranked list of epitopes
        """
        for epitope in epitopes:
            # Calculate composite score
            composite_score = (
                epitope.immunogenicity_score * 0.4 +
                epitope.conservation_score * 0.3 +
                (1 - epitope.toxicity_score) * 0.15 +
                (1 - epitope.allergenicity_score) * 0.15
            )
            epitope.composite_score = composite_score
        
        # Sort by composite score (descending)
        ranked = sorted(epitopes, key=lambda x: x.composite_score, reverse=True)
        
        return ranked
    
    def process_fasta_file(self, fasta_file: str, output_file: str = None) -> pd.DataFrame:
        """
        Process all sequences in a FASTA file and predict epitopes
        
        Args:
            fasta_file: Path to input FASTA file
            output_file: Path to output CSV file (optional)
            
        Returns:
            DataFrame with epitope predictions
        """
        sequences = self.load_fasta_sequences(fasta_file)
        all_epitopes = []
        
        logger.info(f"Processing {len(sequences)} protein sequences...")
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_protein = {}
            
            for protein_id, sequence in sequences.items():
                future = executor.submit(self._process_single_sequence, sequence, protein_id)
                future_to_protein[future] = protein_id
            
            for future in as_completed(future_to_protein):
                protein_id = future_to_protein[future]
                try:
                    epitopes = future.result()
                    all_epitopes.extend(epitopes)
                    logger.info(f"Processed {protein_id}: {len(epitopes)} epitopes found")
                except Exception as e:
                    logger.error(f"Error processing {protein_id}: {e}")
        
        # Filter and rank all epitopes
        filtered_epitopes = self.filter_epitopes(all_epitopes)
        ranked_epitopes = self.rank_epitopes(filtered_epitopes)
        
        # Convert to DataFrame
        df = self._epitopes_to_dataframe(ranked_epitopes)
        
        if output_file:
            df.to_csv(output_file, index=False)
            logger.info(f"Results saved to {output_file}")
        
        return df
    
    def _process_single_sequence(self, sequence: str, protein_id: str) -> List[EpitopeResult]:
        """Process a single protein sequence"""
        epitopes = []
        
        # Use IEDB API if available, otherwise use local predictions
        try:
            epitopes = self.predict_epitopes_iedb_api(sequence, protein_id)
        except:
            # Fallback to local predictions
            bcell_epitopes = self.predict_bcell_epitopes_bepipred(sequence, protein_id)
            tcell_epitopes = self.predict_tcell_epitopes_netmhcpan(sequence, protein_id)
            epitopes = bcell_epitopes + tcell_epitopes
        
        return epitopes
    
    def _epitopes_to_dataframe(self, epitopes: List[EpitopeResult]) -> pd.DataFrame:
        """Convert epitope results to pandas DataFrame"""
        data = []
        
        for epitope in epitopes:
            row = {
                'protein_id': epitope.protein_id,
                'epitope_type': epitope.epitope_type,
                'start_pos': epitope.start_pos,
                'end_pos': epitope.end_pos,
                'peptide': epitope.peptide,
                'length': len(epitope.peptide),
                'immunogenicity_score': epitope.immunogenicity_score,
                'conservation_score': epitope.conservation_score,
                'toxicity_score': epitope.toxicity_score,
                'allergenicity_score': epitope.allergenicity_score,
                'binding_affinity': epitope.binding_affinity,
                'hla_allele': epitope.hla_allele,
                'prediction_method': epitope.prediction_method,
                'composite_score': getattr(epitope, 'composite_score', 0.0)
            }
            data.append(row)
        
        return pd.DataFrame(data)


def main(fasta_file: str, output_file: str = "./results/epitope_predictions.csv"):
    """
    General function to run epitope prediction from a given FASTA file and HLA allele list.

    Parameters:
        fasta_file (str): Path to the input FASTA file.
        hla_alleles (list): List of HLA alleles to consider.
        output_file (str): Path to save the prediction results.

    Returns:
        pd.DataFrame: The prediction results.
    """
    print(f"\n=== Running Epitope Prediction on: {fasta_file} ===")
    hla_alleles = [
        'HLA-A*02:01', 'HLA-A*01:01', 'HLA-A*03:01',
        'HLA-B*07:02', 'HLA-B*08:01', 'HLA-B*44:02',
        'HLA-C*07:01', 'HLA-C*07:02',
        'HLA-DRB1*01:01', 'HLA-DRB1*03:01', 'HLA-DRB1*04:01',
        'HLA-DQB1*02:01', 'HLA-DQB1*03:01'
    ]
    predictor = EpitopePredictor(hla_alleles=hla_alleles)
    
    try:
        results_df = predictor.process_fasta_file(fasta_file, output_file)
        
        print(f"\nTotal epitopes predicted: {len(results_df)}")
        print(f"B-cell epitopes: {len(results_df[results_df['epitope_type'] == 'B-cell'])}")
        print(f"T-cell epitopes: {len(results_df[results_df['epitope_type'] == 'T-cell'])}")
        
        print("\nTop 10 Epitopes:")
        print(results_df.head(10)[['protein_id', 'epitope_type', 'peptide',
                                   'immunogenicity_score', 'composite_score']])
        
        return results_df

    except FileNotFoundError:
        print(f"Error: FASTA file '{fasta_file}' not found.")
    except Exception as e:
        print(f"Error during prediction: {e}")
    
    return None

if __name__ == "__main__":
    # HLA alleles for a diverse population
    hla_alleles = [
        'HLA-A*02:01', 'HLA-A*01:01', 'HLA-A*03:01',
        'HLA-B*07:02', 'HLA-B*08:01', 'HLA-B*44:02',
        'HLA-C*07:01', 'HLA-C*07:02',
        'HLA-DRB1*01:01', 'HLA-DRB1*03:01', 'HLA-DRB1*04:01',
        'HLA-DQB1*02:01', 'HLA-DQB1*03:01'
    ]

    # Path to your FASTA file
    fasta_path = "./results/sars-cov-2_spike_uniprot.fasta"

    # Run prediction
    main(fasta_file=fasta_path)