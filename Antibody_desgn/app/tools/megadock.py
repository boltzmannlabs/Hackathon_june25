# app/tools/megadock.py

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

class MegadockError(Exception):
    pass

async def run_megadock_v2(
    job_name: str,
    tokenid: str,
    experiment_id: str,
    receptor_path:str ,
    ligand_path:str ,
    collection: str = None,
    outputfield: str = None,
    set_uid: bool = True,
    main_doc_exp_id: str = None,
    Node: str = "md_node",
    timeout: float = 1800000.0
) -> Dict[str, Any]:
    """
    Async megadock wrapper using S3 and single-request pipeline.
    Ensures:
      - The Mongo document is created/initialized before submitting the API request,
      - Payload uses the exact schema fields:
          job_name, tokenid, property_name, experiment_name,
          experiment_id, user_id, input_csv.
    """
    url = TOOL_API_MAP.get("megadock")
    if not url:
        raise MegadockError("Megadock API URL not configured")

    # Defaults
    if collection is None:
        collection = "megadock_gpu"
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
            "receptor_path":receptor_path,
            "ligand_path":ligand_path ,
            "experiment_id": experiment_id,
        },
        "createdAt": created_at,
    }
    try:
        oid = create_document(collection, experiment_id, init_contents)
    except Exception as e:
        logging.error(f"[run_megadock] Could not create/init Mongo document for experiment {experiment_id}: {e}")
        raise MegadockError(f"Mongo init failed: {e}")
    # Tag owner UID
    if set_uid and tokenid:
        set_owner_uid(str(oid), collection, tokenid)

    # === 2) Upload local CSV to S3 (or accept existing s3://) ===
    def ensure_s3_uri(local_or_uri: str) -> str:
        if local_or_uri.startswith("s3://"):
            return local_or_uri
        if not os.path.exists(local_or_uri):
            raise MegadockError(f"Local file not found: {local_or_uri}")
        suffix = os.path.basename(local_or_uri)
        key = f"{tokenid}/{experiment_id}/megdock/{uuid.uuid4().hex}_{suffix}"
        try:
            logging.info(f"Uploading to S3: {local_or_uri} -> bucket={S3_BUCKET}, key={key}")
            upload_to_s3(local_or_uri, key, S3_BUCKET)
        except Exception as e:
            logging.error(f"[run_megadock_multimer] Uploading to S3 failed: {e}")
            raise MegadockError(f"S3 upload failed: {e}")
        return f"s3://{S3_BUCKET}/{key}"

    payload = {
        "job_name": job_name,
        "tokenid": tokenid,
        "experiment_id": experiment_id,
        "receptor_path":receptor_path,
        "ligand_path":ligand_path ,
    }
    logging.debug(f"[run_megadock] Payload: {payload!r}")

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
            print("experiment id" , experiment_id)
            logging.info(f"[run_megadock] POST {url} experiment_id={experiment_id}")
            json_response, _, _, _, _ = await post_api_request_async(client, api_args)
            import pprint
            logging.info(f"[run_megadock] API full response:\n{pprint.pformat(json_response)}")
            initial_status = json_response.get("status", "").lower()
    except KeyboardInterrupt:
        logging.warning("[run_megadock] Execution interrupted by user.")
        # Optionally update Mongo doc status to 'interrupted'
        raise MegadockError("megadock execution interrupted by user.")
    except Exception as e:
        logging.error(f"[run_megadock_multimer] API call failed: {e}")
        raise MegadockError(f"megadock API call failed: {e}")

    # === 5) Handle immediate vs queued status ===
    if initial_status == "error":
        logging.warning(f"[run_megadock] API returned error status. Response: {json_response}")
        raise MegadockError(f"megadock failed with status: {initial_status}")
    elif initial_status in ("completed", "success"):
        status = initial_status
        res = json_response
    else:
        # e.g. 'queued', 'pending' etc. Wait on Mongo for final status update.
        logging.info(f"[run_megadock] Initial status = {initial_status}. Waiting on Mongo status...")
        try:
            status, res = await fetch_collections_data(
                collection=collection,
                experiment_id=experiment_id,
                outfield="output.datainfo",  # adjust if your final path is under a different nesting
                timeout=timeout
            )
            print(res)
        except KeyboardInterrupt:
            logging.warning("[run_megadock] Monitoring interrupted by user.")
            raise MegadockError("megadock monitoring interrupted by user.")
        except Exception as e:
            logging.error(f"[run_megadock] Mongo wait failed: {e}")
            raise MegadockError(f"Mongo wait failed: {e}")
        logging.info(f"[run_megadock] Final status = {status}, response fragment = {res!r}")

    if status not in ("completed", "success"):
        raise MegadockError(f"megadock failed with status: {status}")
   # === 6) Extract S3 URI from response ===
    complex_s3_uri = None
    datainfo = {}

    if isinstance(res, dict):
        # Handles both top-level and nested 'output': { datainfo }
        datainfo = res.get("datainfo") or res.get("output", {}).get("datainfo", {})
        print("res:", res)
        print("datainfo :" , datainfo)

    else:
        raise MegadockError(f"Expected dict response with 'datainfo', got: {type(res)} - {res!r}")
    output_csv_s3_uri = res.get("outputFilePath")
    output_zip_s3_uri = res.get("outputFolderPath")

    if not output_csv_s3_uri or not output_zip_s3_uri:
        raise MegadockError(
            f"Missing expected S3 paths in response:\n{datainfo}"
        )

    
    return {
        # "csv_local_path": csv_local_path,
        # "zip_local_path": zip_local_path,
        "csv_s3_uri": output_csv_s3_uri,
        "zip_s3_uri": output_zip_s3_uri
    }

from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from app.tools.tool_waiter import await_async_tool
from app.tools.megadock import run_megadock_v2

class MegadockInput(BaseModel):
    """
    Minimal inputs for megadock in the pipeline:
    - input_path: CSV prepared by preprocessing step (S3 key or local path).
    - experiment_id: same ID used in earlier steps.
    - tokenid: user token for tracking/Mongo ownership.
    """
    receptor_path: str = Field(..., description="Path (S3 key or local) the alphafold output zip")
    ligand_path: str = Field(..., description="Path (S3 key or local) the antigen pdb file which returned from rf antibody step")

    experiment_id: str = Field(..., description="Experiment ID carried from prior steps")
    tokenid: str = Field(..., description="User token ID for tracking in Mongo/S3")

    # The following fields have defaults and are not required in the agent prompt:
    collection: str = Field("megadock_gpu", description="Mongo collection name")
    outputfield: str = Field("complex_s3_uri", description="Field in Mongo doc where megadock writes the result URI")
    set_uid: bool = Field(True, description="Whether to tag UID in Mongo")
    Node: str = Field("MD_node", description="Internal node name for tracking")
    main_doc_exp_id: str = Field(experiment_id, description="Override doc ID if needed; defaults to experiment_id")
    timeout: float = Field(1800000.0, description="Timeout seconds for API call / polling")

def _megadock_fn(
    receptor_path: str,
    ligand_path : str ,
    experiment_id: str,
    tokenid: str,
    collection: str = "megadock_gpu",

) -> dict:
    """
    Wrapper to invoke the async megadock runner via await_async_tool.
    Constructs job_name internally as "md_<experiment_id>".
    Returns:
      - outputFolderPath , outputFilePath
      - plus echoing back 'tokenid' and 'experiment_id' so downstream tools can use them.
    """
    # Build a job_name
    job_name = f"md_{experiment_id}"
    # Use main_doc_exp_id if provided, else experiment_id
    # doc_id = main_doc_exp_id or experiment_id
    main_doc_exp_id =  experiment_id

    # Call the async runner
    out = await_async_tool(run_megadock_v2)(
        job_name=job_name,
        tokenid=tokenid,
        experiment_id=experiment_id,
        receptor_path=receptor_path,
        ligand_path=ligand_path,
        collection=collection,

    )
    
    out["tokenid"] = tokenid
    out["experiment_id"] = experiment_id
    return out

megadock_tool = StructuredTool.from_function(
    name="run_megadock",
    description="Run megadock multimer on the zip file conatining prepared by megadock.  Inputs: receptor_path,ligand_path, experiment_id, tokenid.  Returns the S3 paths of txt  and ZIP outputs, and echoes back tokenid & experiment_id.",
    func=_megadock_fn,
    args_schema=MegadockInput,
)
