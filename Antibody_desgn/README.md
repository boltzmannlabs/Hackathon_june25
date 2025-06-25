# 🧬 Antibody Designer Agent 

This repository implements an end-to-end pipeline for designing improved antibodies from existing candidates. It leverages tools such as RF Antibody prediction, preprocessing modules, AlphaFold structure modeling, MegaDock docking, and Prodigy scoring to evaluate binding affinities and rank top candidates based on negative binding energy. An intelligent agent dynamically constructs the workflow according to user prompts, and the results—such as the highest-scoring PDB models—are presented via both a CLI and an interactive Gradio web interface.

## ⚙️ Setup Instructions

### 1️⃣ Clone the Repository

```
git clone https://github.com/boltzmannlabs/Hackathon_june25.git
cd Antibody_design
```
### 2️⃣ Create the Conda Environment

```
conda env create -f environment.yaml
conda activate antibody_design
```

### 3️⃣ Install the tools Package
```
pip install -e .
```

## 🔑 AWS Credentials
Some parts of the pipeline may access AWS-hosted model weights or services. Be sure to export your AWS , MONGO and MODEL_ID credentials before running:
```
export MONGO_URI=your_access_key
export DB_NAME=your_DB_name
export GCP_BUCKET_NAME=your_GCP_buckert_name
export DEFAULT_BEDROCK_MODEL_ID=your_model_id
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
```

## 🌐 Launching Gradio App
To use the browser-based GUI:
```
python gradio_app.py
```