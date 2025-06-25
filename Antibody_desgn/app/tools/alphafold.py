# app/tools/alphafold.py

import os
import uuid
import tempfile
import logging
from typing import Dict, Any
import httpx
import certifi
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel, Field
from langchain_core.tools import tool

from app.config import TOOL_API_MAP
from app.utils.api_utils import post_api_request_async,fetch_collections_data,create_document,set_input_params,set_owner_uid
from app.tools.tool_waiter import await_async_tool
from commons.s3_upload import upload_to_s3, download_from_s3, bucket_name as S3_BUCKET

class AlphaFoldError(Exception):
    pass

async def run_alphafold_multimer(
    job_name: str,
    tokenid: str,
    experiment_id: str,
    input_path: str,
    collection: str = None,
    outputfield: str = None,
    set_uid: bool = True,
    main_doc_exp_id: str = None,
    Node: str = "af_node",
    timeout: float = 1800000.0
) -> Dict[str, Any]:
    """
    Async AlphaFold multimer wrapper using S3 and single-request pipeline.
    Ensures:
      - The Mongo document is created/initialized before submitting the API request,
      - Payload uses the exact schema fields:
          job_name, tokenid, property_name, experiment_name,
          experiment_id, user_id, input_csv.
    """
    url = TOOL_API_MAP.get("alphafold")
    if not url:
        raise AlphaFoldError("AlphaFold API URL not configured")

    # Defaults
    if collection is None:
        collection = "multimer_structure_prediction"
    if outputfield is None:
        outputfield = "complex_s3_uri"
    # Use the given experiment_id; if None, you might generate one here, but normally plan supplies it
    if main_doc_exp_id is None:
        main_doc_exp_id = experiment_id

    # === 1) Initialize Mongo document up front ===
    # Prepare initial contents
    created_at = datetime.utcnow().isoformat()
    init_contents = {
        "status": "pending",
        "inputparams": {
            "job_name": job_name,
            "tokenid": tokenid,
            "input_path": input_path,
            "experiment_id": experiment_id,
        },
        "createdAt": created_at,
    }
    try:
        oid = create_document(collection, experiment_id, init_contents)
    except Exception as e:
        logging.error(f"[run_alphafold_multimer] Could not create/init Mongo document for experiment {experiment_id}: {e}")
        raise AlphaFoldError(f"Mongo init failed: {e}")
    # Tag owner UID
    if set_uid and tokenid:
        set_owner_uid(str(oid), collection, tokenid)

    # === 2) Upload local CSV to S3 (or accept existing s3://) ===
    def ensure_s3_uri(local_or_uri: str) -> str:
        if local_or_uri.startswith("s3://"):
            return local_or_uri
        if not os.path.exists(local_or_uri):
            raise AlphaFoldError(f"Local file not found: {local_or_uri}")
        suffix = os.path.basename(local_or_uri)
        key = f"{tokenid}/{experiment_id}/alphafold/{uuid.uuid4().hex}_{suffix}"
        try:
            logging.info(f"Uploading to S3: {local_or_uri} -> bucket={S3_BUCKET}, key={key}")
            upload_to_s3(local_or_uri, key, S3_BUCKET)
        except Exception as e:
            logging.error(f"[run_alphafold_multimer] Uploading to S3 failed: {e}")
            raise AlphaFoldError(f"S3 upload failed: {e}")
        return f"s3://{S3_BUCKET}/{key}"

    payload = {
        "job_name": job_name,
        "tokenid": tokenid,
        "property_name": "multimer_structure_prediction",
        "experiment_name": experiment_id,
        "experiment_id": experiment_id,
        "user_id": tokenid,
        "input_csv": input_path #input_s3
    }
    logging.debug(f"[run_alphafold_multimer] Payload: {payload!r}")

    # Update Mongo doc with input params
    try:
        set_input_params(str(oid), collection, (payload, created_at))
    except Exception:
        # already logged inside set_input_params
        pass

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

    # === 4) Submit API request ===
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=certifi.where()) as client:
            print("api args :" , api_args)
            logging.info(f"[run_alphafold_multimer] POST {url} experiment_id={experiment_id}")
            json_response, _, _, _, _ = await post_api_request_async(client, api_args)
            import pprint
            logging.info(f"[run_alphafold_multimer] API full response:\n{pprint.pformat(json_response)}")
            initial_status = json_response.get("status", "").lower()
    except KeyboardInterrupt:
        logging.warning("[run_alphafold_multimer] Execution interrupted by user.")
        # Optionally update Mongo doc status to 'interrupted'
        raise AlphaFoldError("AlphaFold execution interrupted by user.")
    except Exception as e:
        logging.error(f"[run_alphafold_multimer] API call failed: {e}")
        raise AlphaFoldError(f"AlphaFold API call failed: {e}")

    # === 5) Handle immediate vs queued status ===
    if initial_status == "error":
        logging.warning(f"[run_alphafold_multimer] API returned error status. Response: {json_response}")
        raise AlphaFoldError(f"AlphaFold failed with status: {initial_status}")
    elif initial_status in ("completed", "success"):
        status = initial_status
        res = json_response
    else:
        # e.g. 'queued', 'pending' etc. Wait on Mongo for final status update.
        logging.info(f"[run_alphafold_multimer] Initial status = {initial_status}. Waiting on Mongo status...")
        try:
            status, res = await fetch_collections_data(
                collection=collection,
                experiment_id=experiment_id,
                outfield="output.datainfo",  # adjust if your final path is under a different nesting
                timeout=timeout
            )
            print(res)
        except KeyboardInterrupt:
            logging.warning("[run_alphafold_multimer] Monitoring interrupted by user.")
            raise AlphaFoldError("AlphaFold monitoring interrupted by user.")
        except Exception as e:
            logging.error(f"[run_alphafold_multimer] Mongo wait failed: {e}")
            raise AlphaFoldError(f"Mongo wait failed: {e}")
        logging.info(f"[run_alphafold_multimer] Final status = {status}, response fragment = {res!r}")

    if status not in ("completed", "success"):
        raise AlphaFoldError(f"AlphaFold failed with status: {status}")
   # === 6) Extract S3 URI from response ===
    complex_s3_uri = None
    datainfo = {}

    if isinstance(res, dict):
        # Handles both top-level and nested 'output': { datainfo }
        datainfo = res.get("datainfo") or res.get("output", {}).get("datainfo", {})
        print("res:", res)
        print("datainfo :" , datainfo)

    else:
        raise AlphaFoldError(f"Expected dict response with 'datainfo', got: {type(res)} - {res!r}")
    output_csv_s3_uri = res.get("output_csv_path")
    output_zip_s3_uri = res.get("output_zip_path")

    if not output_csv_s3_uri or not output_zip_s3_uri:
        raise AlphaFoldError(
            f"Missing expected S3 paths in response:\n{datainfo}"
        )

    # def download_s3_to_local(s3_uri: str, subname: str) -> str:
    #     if s3_uri.startswith("s3://"):
    #         prefix = f"s3://{S3_BUCKET}/"
    #         key = s3_uri[len(prefix):] if s3_uri.startswith(prefix) else s3_uri.partition("s3://")[2]
    #     else:
    #         key = s3_uri
    #     filename = os.path.basename(key)
    #     local_dir = os.path.join(tempfile.gettempdir(), "antibody_workflow", experiment_id, "alphafold")
    #     os.makedirs(local_dir, exist_ok=True)
    #     local_path = os.path.join(local_dir, f"{subname}_{filename}")
    #     logging.info(
    #         f"[run_alphafold_multimer] Downloading {subname} from S3: bucket={S3_BUCKET}, key={key} -> {local_path}"
    #     )
    #     try:
    #         download_from_s3(key, local_path, bucket_name=S3_BUCKET)
    #     except Exception as e:
    #         raise AlphaFoldError(f"S3 download failed for {subname}: {e}")
        # return local_path

    # csv_local_path = download_s3_to_local(output_csv_s3_uri, "csv")
    # zip_local_path = download_s3_to_local(output_zip_s3_uri, "zip")

    return {
        # "csv_local_path": csv_local_path,
        # "zip_local_path": zip_local_path,
        "csv_s3_uri": output_csv_s3_uri,
        "zip_s3_uri": output_zip_s3_uri
    }

from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from app.tools.tool_waiter import await_async_tool
from app.tools.alphafold import run_alphafold_multimer

class AlphaFoldInput(BaseModel):
    """
    Minimal inputs for AlphaFold in the pipeline:
    - input_path: CSV prepared by preprocessing step (S3 key or local path).
    - experiment_id: same ID used in earlier steps.
    - tokenid: user token for tracking/Mongo ownership.
    """
    input_path: str = Field(..., description="Path (S3 key or local) to the CSV formatted for AlphaFold")
    experiment_id: str = Field(..., description="Experiment ID carried from prior steps")
    tokenid: str = Field(..., description="User token ID for tracking in Mongo/S3")

    # The following fields have defaults and are not required in the agent prompt:
    collection: str = Field("multimer_structure_prediction", description="Mongo collection name")
    outputfield: str = Field("complex_s3_uri", description="Field in Mongo doc where AlphaFold writes the result URI")
    set_uid: bool = Field(True, description="Whether to tag UID in Mongo")
    Node: str = Field("af_node", description="Internal node name for tracking")
    main_doc_exp_id: str = Field(experiment_id, description="Override doc ID if needed; defaults to experiment_id")
    timeout: float = Field(1800000.0, description="Timeout seconds for API call / polling")

def _alphafold_fn(
    input_path: str,
    experiment_id: str,
    tokenid: str,
    collection: str = "multimer_structure_prediction",
    # outputfield: str = "complex_s3_uri",
    set_uid: bool = True,
    Node: str = "af_node",
    main_doc_exp_id: str = None,
    timeout: float = 1800000.0,
) -> dict:
    """
    Wrapper to invoke the async AlphaFold runner via await_async_tool.
    Constructs job_name internally as "af_<experiment_id>".
    Returns:
      - csv_local_path, zip_local_path, csv_s3_uri, zip_s3_uri
      - plus echoing back 'tokenid' and 'experiment_id' so downstream tools can use them.
    """
    # Build a job_name
    job_name = f"af_{experiment_id}"
    # Use main_doc_exp_id if provided, else experiment_id
    # doc_id = main_doc_exp_id or experiment_id
    main_doc_exp_id =  experiment_id

    # Call the async runner
    out = await_async_tool(run_alphafold_multimer)(
        job_name=job_name,
        tokenid=tokenid,
        experiment_id=experiment_id,
        input_path=input_path,
        collection=collection,
        # outputfield=outputfield,
        set_uid=set_uid,
        main_doc_exp_id=experiment_id,
        Node=Node,
        timeout=timeout,
    )
    
    out["tokenid"] = tokenid
    out["experiment_id"] = experiment_id
    return out

alphafold_tool = StructuredTool.from_function(
    name="run_alphafold",
    description="Run AlphaFold multimer on the CSV prepared by preprocessing.  Inputs: input_path, experiment_id, tokenid.  Returns the local & S3 paths of CSV and ZIP outputs, and echoes back tokenid & experiment_id.",
    func=_alphafold_fn,
    args_schema=AlphaFoldInput,
)
