#!/usr/bin/env python3
"""
Biological Target Definition Module for Vaccine Design Pipeline
Fetches and processes protein/gene sequences from public databases

Compatible with Biopython 1.78+ (removes deprecated alphabet usage)
"""

import requests
import re
from typing import Optional, Dict, List, Tuple
from Bio import SeqIO, Entrez
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
import xml.etree.ElementTree as ET
from urllib.parse import quote
import time,os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BiologicalTargetDefiner:
    """
    Class to define and fetch biological targets for vaccine design
    """
    
    def __init__(self, email: str = "your.email@example.com"):
        """
        Initialize the target definer
        
        Args:
            email: Email for NCBI Entrez (required for API access)
        """
        self.email = email
        Entrez.email = email
        self.session = requests.Session()
        
    def fetch_ncbi_sequence(self, accession_id: str, database: str = "protein") -> Optional[SeqRecord]:
        """
        Fetch sequence from NCBI using accession ID
        
        Args:
            accession_id: NCBI accession ID (e.g., 'YP_009724390.1')
            database: NCBI database ('protein', 'nucleotide')
            
        Returns:
            SeqRecord object or None if not found
        """
        try:
            logger.info(f"Fetching {accession_id} from NCBI {database} database")
            
            # Search for the sequence
            Entrez.email = "your.email@example.com"
            handle = Entrez.esearch(db=database, term=accession_id, retmax=1)
            search_results = Entrez.read(handle)
            handle.close()
            
            if not search_results['IdList']:
                logger.error(f"No results found for {accession_id}")
                return None
            
            # Fetch the sequence
            seq_id = search_results['IdList'][0]
            handle = Entrez.efetch(db=database, id=seq_id, rettype="fasta", retmode="text")
            sequence = SeqIO.read(handle, "fasta")
            handle.close()
            
            logger.info(f"Successfully fetched sequence: {len(sequence.seq)} residues")
            return sequence
            
        except Exception as e:
            logger.error(f"Error fetching from NCBI: {e}")
            return None
    
    def fetch_uniprot_sequence(self, uniprot_id: str) -> Optional[SeqRecord]:
        """
        Fetch sequence from UniProt using UniProt ID
        
        Args:
            uniprot_id: UniProt ID (e.g., 'P0DTC2')
            
        Returns:
            SeqRecord object or None if not found
        """
        try:
            logger.info(f"Fetching {uniprot_id} from UniProt")
            
            url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.fasta"
            response = self.session.get(url)
            
            if response.status_code == 200:
                # Parse FASTA content
                fasta_content = response.text
                from io import StringIO
                sequence = SeqIO.read(StringIO(fasta_content), "fasta")
                
                logger.info(f"Successfully fetched sequence: {len(sequence.seq)} residues")
                return sequence
            else:
                logger.error(f"Failed to fetch from UniProt: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching from UniProt: {e}")
            return None
    
    def search_virus_proteins(self, virus_name: str, protein_name: str = "") -> List[Dict]:
        """
        Search for virus proteins in NCBI
        
        Args:
            virus_name: Name of virus (e.g., 'SARS-CoV-2')
            protein_name: Specific protein name (e.g., 'spike protein')
            
        Returns:
            List of dictionaries with search results
        """
        try:
            search_term = f"{virus_name}"
            if protein_name:
                search_term += f" {protein_name}"
            
            logger.info(f"Searching for: {search_term}")
            
            handle = Entrez.esearch(db="protein", term=search_term, retmax=20)
            search_results = Entrez.read(handle)
            handle.close()
            
            results = []
            if search_results['IdList']:
                # Get details for each result
                ids = ','.join(search_results['IdList'][:10])  # Limit to first 10
                handle = Entrez.esummary(db="protein", id=ids)
                summaries = Entrez.read(handle)
                handle.close()
                
                for summary in summaries:
                    results.append({
                        'id': summary['Id'],
                        'accession': summary['AccessionVersion'],
                        'title': summary['Title'],
                        'length': summary['Length'],
                        'organism': summary.get('Organism', 'Unknown')
                    })
            
            logger.info(f"Found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error searching NCBI: {e}")
            return []
    
    def clean_sequence(self, sequence: SeqRecord, remove_signal_peptide: bool = True) -> SeqRecord:
        """
        Clean and process the fetched sequence
        
        Args:
            sequence: Input SeqRecord
            remove_signal_peptide: Whether to attempt signal peptide removal
            
        Returns:
            Cleaned SeqRecord
        """
        logger.info("Cleaning sequence...")
        
        # Convert to string for processing
        seq_str = str(sequence.seq)
        
        # Remove any ambiguous characters for protein sequences
        # Check for common ambiguous amino acid codes
        ambiguous_chars = ['X', 'B', 'Z', 'J']  # X=any, B=Asn/Asp, Z=Gln/Glu, J=Leu/Ile
        original_length = len(seq_str)
        
        for char in ambiguous_chars:
            if char in seq_str:
                count = seq_str.count(char)
                if count > 0:
                    logger.info(f"Removing {count} ambiguous '{char}' residues")
                    seq_str = seq_str.replace(char, '')
        
        if len(seq_str) != original_length:
            logger.info(f"Removed {original_length - len(seq_str)} ambiguous residues total")
        
        # Remove stop codons if present
        if seq_str.endswith('*'):
            logger.info("Removing terminal stop codon")
            seq_str = seq_str[:-1]
        
        # Basic signal peptide removal (simple heuristic - first 20-30 hydrophobic residues)
        if remove_signal_peptide and len(seq_str) > 50:
            hydrophobic = set('AILMFWYV')
            start_region = seq_str[:30]
            if start_region:  # Make sure we have sequence to analyze
                hydrophobic_count = sum(1 for aa in start_region if aa in hydrophobic)
                
                if hydrophobic_count / len(start_region) > 0.6:  # >60% hydrophobic
                    logger.info("Potential signal peptide detected, removing first 20 residues")
                    seq_str = seq_str[20:]
        
        # Create new SeqRecord with cleaned sequence
        cleaned_seq = SeqRecord(
            Seq(seq_str),
            id=sequence.id,
            description=f"Cleaned {sequence.description}",
            annotations=sequence.annotations.copy()
        )
        
        logger.info(f"Sequence cleaned: {len(sequence.seq)} -> {len(cleaned_seq.seq)} residues")
        return cleaned_seq
    
    def get_target_domains(self, sequence: SeqRecord, target_domain: str = "") -> Dict[str, Tuple[int, int]]:
        """
        Identify target domains within the sequence (basic implementation)
        
        Args:
            sequence: Input sequence
            target_domain: Specific domain to look for
            
        Returns:
            Dictionary of domain names and their positions (start, end)
        """
        domains = {}
        seq_str = str(sequence.seq)
        
        # Predefined domain patterns for common viral proteins
        domain_patterns = {
            # SARS-CoV-2 and SARS-CoV spike protein domains
            'RBD': {  # Receptor Binding Domain patterns
                'SARS-CoV-2': (319, 541),
                'SARS-CoV': (306, 527)
            },
            'NTD': {  # N-terminal Domain
                'SARS-CoV-2': (14, 305),
                'SARS-CoV': (14, 292)
            },
            'S1': {  # S1 subunit
                'SARS-CoV-2': (14, 685),
                'SARS-CoV': (14, 667)
            },
            'S2': {  # S2 subunit
                'SARS-CoV-2': (686, 1273),
                'SARS-CoV': (668, 1255)
            },
            
            # Influenza virus domains
            'HA1': {  # Hemagglutinin subunit 1
                'H1N1': (1, 328),
                'H3N2': (1, 328),
                'H5N1': (1, 340)
            },
            'HA2': {  # Hemagglutinin subunit 2
                'H1N1': (329, 566),
                'H3N2': (329, 566),
                'H5N1': (341, 568)
            },
            'RBS': {  # Receptor Binding Site (within HA1)
                'H1N1': (130, 220),
                'H3N2': (135, 225)
            },
            
            # RSV protein domains
            'RSV_F': {  # Fusion protein
                'RSV': (1, 574)
            },
            'RSV_G': {  # Attachment glycoprotein
                'RSV': (1, 298)
            },
            'RSV_F_PREFUSION': {  # Prefusion F protein antigenic sites
                'RSV': (62, 210)  # Site II region
            },
            
            # HPV protein domains
            'L1': {  # Major capsid protein
                'HPV16': (1, 504),
                'HPV18': (1, 505)
            },
            'L2': {  # Minor capsid protein
                'HPV16': (1, 473),
                'HPV18': (1, 460)
            },
            
            # Hepatitis B domains
            'HBsAg': {  # Surface antigen
                'HBV': (1, 226)
            },
            'PreS1': {  # Pre-S1 domain
                'HBV': (1, 119)
            },
            'PreS2': {  # Pre-S2 domain
                'HBV': (120, 174)
            },
            
            # Zika virus domains
            'E_DIII': {  # Envelope protein domain III
                'ZIKV': (301, 401)
            },
            'prM': {  # Precursor membrane protein
                'ZIKV': (1, 166)
            }
        }
        
        # Check sequence description for virus type
        description = sequence.description.lower()
        virus_type = None
        
        # Extended virus type detection
        if 'sars-cov-2' in description or 'covid' in description or '2019-ncov' in description:
            virus_type = 'SARS-CoV-2'
        elif 'sars-cov' in description or 'sars coronavirus' in description:
            virus_type = 'SARS-CoV'
        elif 'influenza' in description or 'h1n1' in description:
            if 'h1n1' in description:
                virus_type = 'H1N1'
            elif 'h3n2' in description:
                virus_type = 'H3N2'
            elif 'h5n1' in description:
                virus_type = 'H5N1'
            else:
                virus_type = 'H1N1'  # Default to H1N1
        elif 'respiratory syncytial' in description or 'rsv' in description:
            virus_type = 'RSV'
        elif 'human papillomavirus' in description or 'hpv' in description:
            if 'hpv16' in description or 'type 16' in description:
                virus_type = 'HPV16'
            elif 'hpv18' in description or 'type 18' in description:
                virus_type = 'HPV18'
            else:
                virus_type = 'HPV16'  # Default to HPV16
        elif 'hepatitis b' in description or 'hbv' in description:
            virus_type = 'HBV'
        elif 'zika' in description or 'zikv' in description:
            virus_type = 'ZIKV'
        
        if virus_type and target_domain.upper() in domain_patterns:
            if virus_type in domain_patterns[target_domain.upper()]:
                start, end = domain_patterns[target_domain.upper()][virus_type]
                if end <= len(seq_str):
                    domains[target_domain.upper()] = (start, end)
                    logger.info(f"Identified {target_domain.upper()} domain: positions {start}-{end}")
        
        return domains
    
    def extract_domain(self, sequence: SeqRecord, domain_name: str, start: int, end: int) -> SeqRecord:
        """
        Extract a specific domain from the sequence
        
        Args:
            sequence: Input sequence
            domain_name: Name of the domain
            start: Start position (1-based)
            end: End position (1-based)
            
        Returns:
            SeqRecord with extracted domain
        """
        # Convert to 0-based indexing
        domain_seq = sequence.seq[start-1:end]
        
        domain_record = SeqRecord(
            domain_seq,
            id=f"{sequence.id}_{domain_name}",
            description=f"{domain_name} domain from {sequence.description} (positions {start}-{end})",
            annotations=sequence.annotations.copy()
        )
        
        logger.info(f"Extracted {domain_name} domain: {len(domain_seq)} residues")
        return domain_record
    
    def save_sequence(self, sequence: SeqRecord, filename: str, format: str = "fasta"):
        """
        Save sequence to file
        
        Args:
            sequence: SeqRecord to save
            filename: Output filename
            format: File format ('fasta', 'genbank', etc.)
        """
        filepath = f"./results/{filename}"

        # Ensure the directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        try:
            with open(filepath, 'w') as f:
                # Wrap sequence in list if it's a single record
                if isinstance(sequence, list):
                    SeqIO.write(sequence, f, format)
                else:
                    SeqIO.write([sequence], f, format)
            logger.info(f"Sequence saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving sequence: {e}")

def main(definer, source: str, identifier: str, description: str, domains: list = None):
    """
    Generalized function to fetch, clean, and optionally extract domains from a viral protein sequence.

    Parameters:
        definer: Instance of BiologicalTargetDefiner
        source (str): 'ncbi' or 'uniprot'
        identifier (str): 'Virus,Protein name' for NCBI or UniProt ID
        description (str): Used in output filenames
        domains (list): List of domain names to extract (optional)

    Returns:
        bool: True if sequence was processed, False otherwise
    """
    print(f"\n=== Processing: {description} ===")

    if source == "ncbi":
        try:
            virus, protein = [s.strip() for s in identifier.split(',')]
        except ValueError:
            print("Identifier for NCBI must be in 'Virus,Protein' format.")
            return "Identifier for NCBI must be in 'Virus,Protein' format."

        results = definer.search_virus_proteins(virus, protein)
        if not results:
            print(f"No results found for {virus} {protein}")
            return f"No results found for {virus} {protein}"

        sequence = definer.fetch_ncbi_sequence(results[0]['accession'])

    elif source == "uniprot":
        sequence = definer.fetch_uniprot_sequence(identifier)
    
    else:
        print("Source must be either 'ncbi' or 'uniprot'.")
        return "Source must be either 'ncbi' or 'uniprot'."

    if not sequence:
        print(f"Failed to fetch sequence for {identifier}")
        return f"Failed to fetch sequence for {identifier}"

    cleaned_seq = sequence

    if not domains:
        filename = f"{description.lower().replace(' ', '_')}.fasta"
        definer.save_sequence(cleaned_seq, filename)
        return filename

    success = ""
    for domain in domains:
        domain_data = definer.get_target_domains(cleaned_seq, domain)
        if domain_data:
            for domain_name, (start, end) in domain_data.items():
                domain_seq = definer.extract_domain(cleaned_seq, domain_name, start, end)
                filename = f"{description.lower().replace(' ', '_')}_{domain_name.lower()}.fasta"
                definer.save_sequence(domain_seq, filename)
                success = filename
        else:
            filename = f"{description.lower().replace(' ', '_')}.fasta"
            definer.save_sequence(sequence, filename)
            success = filename

    return success

if __name__ == "__main__":
    # Initialize the target definer
    definer = BiologicalTargetDefiner(email="your.email@example.com")

    # SARS-CoV-2 Spike RBD
    main(definer, "ncbi", "SARS-CoV-2,spike protein", "SARS-CoV-2 Spike", domains=["RBD"])

    # # H1N1 Hemagglutinin
    # main(definer, "ncbi", "Influenza H1N1,hemagglutinin", "H1N1 Hemagglutinin", domains=["HA1", "RBS"])

    # # HPV16 L1 full protein
    # main(definer, "ncbi", "human papillomavirus 16,L1", "HPV16 L1 Capsid")

    # # UniProt example
    # main(definer, "uniprot", "P0DTC2", "SARS-CoV-2 Spike UniProt")
