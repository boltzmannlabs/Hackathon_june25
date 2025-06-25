import os
import uuid
import tempfile
import logging
from typing import Dict, Any
from bson import ObjectId
from langchain_core.tools import StructuredTool
from app.tools.tool_waiter import await_async_tool
from commons.s3_upload import upload_to_s3, download_from_s3, bucket_name as S3_BUCKET
from app.config import TOOL_API_MAP
from app.utils.api_utils import post_api_request_async, fetch_collections_data
from pydantic import BaseModel, Field
import httpx

class RFAntibodyError(Exception):
    pass

async def run_rf_antibody(
    job_name: str,
    tokenid: str,
    experiment_id: str,
    antibody_pdb_path: str,
    antigen_pdb_path: str,
    antibody_type: str,
    num_sequences: int,
    collection: str = None,
    outputfield: str = None,
    set_uid: bool = True,
    main_doc_exp_id: str = None,
    Node: str = "rf_node",
    timeout: float = 1800.0
) -> Dict[str, Any]:
    """
    Async RF Antibody wrapper using S3 and single-request pipeline.
    """
    url = TOOL_API_MAP.get("rf_antibody")
    if not url:
        raise RFAntibodyError("RF Antibody API URL not configured")

    if collection is None:
        collection = "rf_antibody"
    if outputfield is None:
        outputfield = "rf_output_s3_uri"
    if main_doc_exp_id is None:
        main_doc_exp_id = experiment_id

    def ensure_s3_uri(local_or_uri: str) -> str:
        if local_or_uri.startswith("s3://"):
            return local_or_uri
        if not os.path.exists(local_or_uri):
            raise RFAntibodyError(f"Local PDB file not found: {local_or_uri}")
        suffix = os.path.basename(local_or_uri)
        key = f"{tokenid}/{experiment_id}/rf_antibody/{uuid.uuid4().hex}_{suffix}"
        try:
            upload_to_s3(local_or_uri, key, S3_BUCKET)
        except Exception as e:
            logging.error(f"Uploading to S3 failed: {e}")
            raise RFAntibodyError(f"S3 upload failed: {e}")
        return f"{key}"

    try:
        ab_s3 = ensure_s3_uri(antibody_pdb_path)
        ag_s3 = ensure_s3_uri(antigen_pdb_path)
    except Exception as e:
        raise RFAntibodyError(f"S3 upload failed: {e}")

    payload = {
        "job_name": job_name,
        "tokenid": tokenid,
        "experiment_id": experiment_id,
        "user_id": tokenid,
        "antibody_pdb_path": ab_s3,
        "antigen_pdb_path": ag_s3,
        "num_sequences": num_sequences,
        "antibody_type": antibody_type
    }

    api_args = (
        payload,
        url,
        tokenid,
        collection,
        experiment_id,
        outputfield,
        set_uid,
        Node,
        main_doc_exp_id
    )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            print(f"Posting RF Antibody request to {url} with args: {api_args}")
            json_response, _, _, _, _ = await post_api_request_async(client, api_args)
            print("Full post_api_request_async response:", json_response)
            import pprint
            logging.info(f"RF API full response:\n{pprint.pformat(json_response)}")
            initial_status = json_response.get("status", "completed").lower()
    except KeyboardInterrupt:
        logging.warning("RF Antibody execution interrupted by user.")
        raise RFAntibodyError("RF Antibody execution interrupted by user.")
    except Exception as e:
        logging.error(f"RF Antibody API call failed: {e}")
        raise RFAntibodyError(f"RF Antibody API call failed: {e}")

    if initial_status == "error":
        logging.warning(f"RF Antibody returned 'error' status. Full response: {json_response}")
        raise RFAntibodyError(f"RF Antibody failed with status: {initial_status}")
    elif initial_status in ("completed", "success"):
        status = initial_status
        res = json_response
    else:
        # Wait using change stream
        logging.info(f"Initial RF status = {initial_status}. Waiting on Mongo status...")
        # from app.utils.mongo_utils import fetch_collections_data
        try:
            status, res = await fetch_collections_data(
                collection=collection,
                experiment_id=main_doc_exp_id,
                outfield="output.datainfo.output_path",  # ✅ directly extract from nested structure
                timeout=timeout
            )
        except KeyboardInterrupt:
            logging.warning("RF Antibody monitoring interrupted by user during change stream.")
            raise RFAntibodyError("RF Antibody monitoring interrupted by user.")

        print(f"Final RF status = {status}")
        print(f"Final RF response = {res}")

    if status not in ("completed", "success"):
        raise RFAntibodyError(f"RF Antibody failed with status: {status}")

    rf_s3_uri = None

    if isinstance(res, dict):
        # Handle nested `output.datainfo.output_path`
        datainfo = res.get("datainfo") or res.get("output", {}).get("datainfo", {})
        rf_s3_uri = datainfo.get("output_path") or res.get(outputfield)
    elif isinstance(res, str):
        rf_s3_uri = res

    # Final fallback check
    if not rf_s3_uri:
        raise RFAntibodyError(f"Missing output_path in Mongo response: {res!r}")

    # Normalize S3 path (handle both full URI and relative path)
    if rf_s3_uri.startswith("s3://"):
        s3_key = rf_s3_uri.partition(f"s3://{S3_BUCKET}/")[2]
    else:
        s3_key = rf_s3_uri  # relative path like "users/.../results.zip"

    local_dir = os.path.join(tempfile.gettempdir(), "antibody_workflow", experiment_id, "rf_antibody")
    os.makedirs(local_dir, exist_ok=True)

    filename = os.path.basename(s3_key)
    local_path = os.path.join(local_dir, filename)

    print(f"S3 path to download: {s3_key}")
    print(f"Local download path: {local_path}")

    try:
        download_from_s3(s3_key, local_path, bucket_name=S3_BUCKET)
    except Exception as e:
        raise RFAntibodyError(f"S3 download failed: {e}")

    return {
        "rf_output_local_path": local_path,
        "rf_output_s3_uri": rf_s3_uri,
        "experiment_id": experiment_id,
        "tokenid": tokenid,
        "antigen_pdb_path":ag_s3
    }



class RFUserInput(BaseModel):
    antibody_pdb_path: str = Field(..., description="Local path or S3 URI to antibody PDB file")
    antigen_pdb_path: str = Field(..., description="Local path or S3 URI to antigen PDB file")
    # You could allow user to optionally override num_sequences or antibody_type:
    num_sequences: int = Field(default=5, description="Number of sequences to generate (default 5)")
    antibody_type: str = Field(default="antibody", description="Type of antibody to design")


# Define your sync wrapper (tool entrypoint)
def rf_antibody_tool_fn(
    antibody_pdb_path: str,
    antigen_pdb_path: str,
    num_sequences: int = 5,
    antibody_type: str = "antibody"
) -> Dict[str, Any]:
    """
    Wrapper for RF Antibody design. Generates experiment_id, tokenid, job_name internally.
    User only provides antibody_pdb_path and antigen_pdb_path (plus optional num_sequences and antibody_type).
    """
    # Generate experiment_id and tokenid (as hex string from ObjectId)
    experiment_oid = ObjectId()
    experiment_id = str(experiment_oid)
    tokenid = str(ObjectId())  # or fetch from real user context if available
    job_name = f"rf_{experiment_id}"

    # Call the async run_rf_antibody via await_async_tool
    result = await_async_tool(run_rf_antibody)(
        job_name=job_name,
        tokenid=tokenid,
        experiment_id=experiment_id,
        antibody_pdb_path=antibody_pdb_path,
        antigen_pdb_path=antigen_pdb_path,
        antibody_type=antibody_type,
        num_sequences=num_sequences,

    )
    # You may want to include experiment_id/tokenid in the returned dict so downstream tools know them:
    # e.g., augment result:
    result.update({
        "experiment_id": experiment_id,
        "tokenid": tokenid,
        "job_name": job_name
    })
    return result

# Register StructuredTool from function:
rf_antibody_tool = StructuredTool.from_function(
    name="rf_antibody",
    description=(
        "Design antibodies using RF Antibody. "
        "User must supply: antibody_pdb_path, antigen_pdb_path. "
        "Optionally: num_sequences, antibody_type. "
        "Internally generates experiment_id, tokenid, job_name."
    ),
    func=rf_antibody_tool_fn,
    args_schema=RFUserInput
)
