import os

# ===== GCP settings =====
GCP_BUCKET_NAME = "BUCKET_NAME"  # Deprecated: using AWS S3 instead

# ===== MongoDB settings =====
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

# ===== AWS Bedrock (Claude) settings =====
AWS_REGION = os.getenv("AWS_REGION")
DEFAULT_BEDROCK_MODEL_ID = os.getenv(
    "CLAUDE_MODEL_ID",
)

# ===== Tool endpoints =====
TOOL_API_MAP = {
    "rf_antibody":   "RF_Antibody tool",
    "alphafold":     "AlphaFold tool",
    "prodigy":       "Prodigy tool",
    "megadock":       "Megadock tool"
}

# ===== Tool descriptions for planner =====
TOOL_DESCRIPTIONS = {
    "rf_antibody": (
        "Runs RF Antibody. Expects inputs:\n"
        "  - job_name (str)\n"
        "  - tokenid (str) as MongoDB user ID\n"
        "  - experiment_id (str)\n"
        "  - antibody_pdb_path (str): local path\n"
        "  - antigen_pdb_path (str): local path\n"
        "  - num_sequences (int)\n"
        "  - antibody_type (str)\n"
        "Additionally for tracking:\n"
        "  - collection (str), outputfield (str), set_uid (bool), Node (str), main_doc_exp_id (str)\n"
        "Outputs:\n"
        "  - rf_output_local_path (str)\n"
        "  - rf_output_s3_uri (str)\n"
    ),
    "preprocess_rf_output": (
        "Preprocesses the RF Antibody zip output for AlphaFold.\n"
        "Expects inputs:\n"
        "  - rf_output_local_path (str): Local zip path from RF Antibody tool\n"
        "  - experiment_id (str)\n"
        "Outputs:\n"
        "  - input_path (str): Combined and formatted CSV file path for AlphaFold\n"
    ),
    "alphafold": (
        "Runs AlphaFold multimer. Expects inputs:\n"
        "  - job_name (str)\n"
        "  - experiment_id (str)\n"
        "  - tokenid (str) as MongoDB user ID\n"
        "  - input_path (str): local CSV path (from RF preprocessing)\n"
        "Additionally for tracking:\n"
        "  - collection (str), outputfield (str), set_uid (bool), Node (str), main_doc_exp_id (str)\n"
        "Outputs:\n"
        "  - complex_local_path (str): ZIP path with PDBs\n"
        "  - complex_s3_uri (str)\n"
    ),
    "megadock": (
        "Runs Megadock. Expects inputs:\n"
        "Expects inputs:\n"
        "  - complex_s3_uri (str): zip path from megadock tool\n"
        "  - experiment_id (str)\n"
        "  - tokenid (str) as MongoDB user ID\n"
        "Outputs:\n"
        "  - outputFolderPath (str): Folder contains pdb's to pass to prodigy\n"
        "  -outputFilePath (str): Contains text file for visualization"
    ),
    "prodigy": (
        "Runs Prodigy binding affinity prediction. Expects inputs:\n"
        "  - job_name (str)\n"
        "  - experiment_id (str)\n"
        "  - tokenid (str) as MongoDB user ID\n"
        "  - input_zip_path (str): local ZIP file from AlphaFold\n"
        "  - input_csv_path (str): local AlphaFold CSV path\n"
        "  - top_n (int): number of top binders to retain\n"
        "Additionally for tracking:\n"
        "  - collection (str), outputfield (str), set_uid (bool), Node (str), main_doc_exp_id (str)\n"
        "Outputs:\n"
        "  - prodigy_report_s3_uri (str): Full Prodigy CSV\n"
        "  - top_zip_s3_uri (str): ZIP with top PDBs\n"
        "  - top_csv_s3_uri (str): CSV with top PDB scores\n"
    ),
}
