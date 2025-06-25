import os
import zipfile
import tempfile
import pandas as pd
from collections import defaultdict
from app.config import TOOL_API_MAP
from commons.s3_upload import upload_to_s3, download_from_s3, bucket_name as S3_BUCKET
from pydantic import BaseModel , Field
from langchain_core.tools import tool
from app.tools.tool_waiter import await_async_tool
from langchain_core.tools import StructuredTool



async def preprocess_rf_output_for_alphafold(rf_output_local_path: str, experiment_id: str, tokenid: str, **kwargs) -> dict:
    temp_dir = tempfile.mkdtemp(prefix="af_csv_")
    with zipfile.ZipFile(rf_output_local_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    combined = defaultdict(lambda: {"seq_id": "", "light_chain": "", "heavy_chain": "", "score": None})

    for file in os.listdir(temp_dir):
        if file.endswith(".csv"):
            df = pd.read_csv(os.path.join(temp_dir, file))
            for _, row in df.iterrows():
                tag = row["tag"]
                sequence = row["sequence"]
                chain = row["chain"].lower()
                score = row.get("score", None)

                # Strip _H or _L from tag to get base tag
                if tag.endswith("_H") or tag.endswith("_L"):
                    tag_base = tag.rsplit("_", 1)[0]
                else:
                    tag_base = tag

                group_key = f"{tag_base}_{score}"
                combined[group_key]["seq_id"] = tag_base
                combined[group_key]["score"] = score

                if "light" in chain:
                    combined[group_key]["light_chain"] = sequence
                elif "heavy" in chain:
                    combined[group_key]["heavy_chain"] = sequence

    final_df = pd.DataFrame(combined.values())

    out_dir = os.path.join(tempfile.gettempdir(), "antibody_workflow", experiment_id, "processed_csv")
    os.makedirs(out_dir, exist_ok=True)
    output_csv = os.path.join(out_dir, "alphafold_input.csv")
    selected_cols = ["seq_id", "light_chain", "heavy_chain", "score"]

    # Slice top 4 rows and filter required columns
    filtered_df = final_df[selected_cols].head(1)
    #withoutslicing 
    # filtered_df = final_df[selected_cols]

    # Save version with score (for logging/debugging if needed)
    scored_csv = os.path.join(out_dir, "alphafold_input_scored.csv")
    filtered_df.to_csv(scored_csv, index=False)

    # Drop score column for AlphaFold input
    filtered_df = filtered_df.drop(columns=["score"])

    # Save AlphaFold input CSV
    output_csv = os.path.join(out_dir, "alphafold_input.csv")
    filtered_df.to_csv(output_csv, index=False)

    # Upload to S3
    alphafold_input = f"alphafold_input/{experiment_id}/alphafold_input.csv"
    upload_to_s3(output_csv, alphafold_input, bucket_name=S3_BUCKET)

    return {"input_path": alphafold_input, "experiment_id": experiment_id, "tokenid": tokenid}



# 1) Define minimal Pydantic input schema for the StructuredTool:
class PreprocessingInput(BaseModel):
    rf_output_local_path: str = Field(..., description="Local path to RF Antibody output ZIP")
    experiment_id: str = Field(..., description="Experiment ID from RF Antibody step")
    tokenid: str = Field(..., description="token ID for S3 ")

# 2) Define a synchronous wrapper that calls the async function via await_async_tool:
def _preprocessing_fn(
    rf_output_local_path: str,
    experiment_id: str,
    tokenid: str
) -> dict:
    """
    Preprocess RF Antibody ZIP output for AlphaFold input formatting.
    Uses the async preprocess_rf_output_for_alphafold under the hood.
    """
    # Call the async function and wait for completion
    result = await_async_tool(preprocess_rf_output_for_alphafold)(
        rf_output_local_path=rf_output_local_path,
        experiment_id=experiment_id,
        tokenid=tokenid
    )
    # Propagate experiment_id so downstream tools see it in context
    result.update({"experiment_id": experiment_id, "tokenid": tokenid})
    return result

# 3) Register as StructuredTool:
preprocessing_tool = StructuredTool.from_function(
    name="preprocess_rf_output",
    description="Preprocess RF Antibody output ZIP for AlphaFold input. Requires rf_output_local_path and experiment_id. and tokenid.",
    func=_preprocessing_fn,
    args_schema=PreprocessingInput
)
