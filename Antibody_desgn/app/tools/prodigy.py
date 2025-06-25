

import os
import uuid
import tempfile
import logging
import csv
import zipfile
from typing import Dict, Any, List
import httpx
import certifi
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel, Field
from langchain_core.tools import tool

from app.config import TOOL_API_MAP
from app.utils.api_utils import post_api_request_async, fetch_collections_data, create_document, set_input_params, set_owner_uid
from app.tools.tool_waiter import await_async_tool
from commons.s3_upload import upload_to_s3, download_from_s3, bucket_name as S3_BUCKET


def select_top_negative_affinities_csv(
    local_csv_path: str,
    output_csv_path: str,
    top_n: int
) -> int:
    """
    Read local_csv_path, detect binding-affinity columns (header contains 'binding_affinity' case-insensitive),
    parse them as floats, pick the most negative per row, sort ascending (most negative first),
    take up to top_n rows, and write to output_csv_path with columns: id, binding_affinity.
    Returns the number of rows written.
    """
    if not os.path.isfile(local_csv_path):
        raise ProdigyError(f"Downloaded Prodigy CSV not found: {local_csv_path}")
    rows = []
    with open(local_csv_path, newline='') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        if not headers:
            raise ProdigyError("No headers found in Prodigy CSV")
        if 'id' not in headers:
            raise ProdigyError(f"No 'id' column in Prodigy CSV headers: {headers}")
        affinity_cols = [h for h in headers if 'binding_affinity' in h.lower()]
        if not affinity_cols:
            raise ProdigyError(f"No binding_affinity column found in Prodigy CSV headers: {headers}")
        for row in reader:
            best_aff = None
            for col in affinity_cols:
                raw = row.get(col, "").strip()
                if raw == "":
                    continue
                try:
                    val = float(raw)
                except:
                    continue
                if best_aff is None or val < best_aff:
                    best_aff = val
            if best_aff is None:
                continue
            rows.append({'id': row['id'], 'binding_affinity': best_aff})
    if not rows:
        raise ProdigyError("No valid numeric binding_affinity values found in Prodigy CSV")
    rows.sort(key=lambda x: x['binding_affinity'])
    top_rows = rows[:top_n]
    with open(output_csv_path, 'w', newline='') as fout:
        writer = csv.DictWriter(fout, fieldnames=['id', 'binding_affinity'])
        writer.writeheader()
        for r in top_rows:
            writer.writerow(r)
    logging.info(f"Wrote top {len(top_rows)} affinity rows to {output_csv_path}")
    return len(top_rows)


class ProdigyError(Exception):
    pass

async def run_prodigy(
    job_name: str,
    tokenid: str,
    experiment_id: str,
    input_path: str,
    chain_list: List[str] = None,
    collection: str = None,
    outputfield: str = None,
    top_n: int = 10,
    set_uid: bool = True,
    main_doc_exp_id: str = None,
    Node: str = "pr_node",
    timeout: float = 18000.0
) -> Dict[str, Any]:
    """
    Async prodigy wrapper using S3 and single-request pipeline.
    After Prodigy completes, select top negative affinities and package corresponding PDBs into a ZIP.
    Returns dict with top_n count, CSV S3 URI, and ZIP S3 URI of selected PDBs.
    """
    url = TOOL_API_MAP.get("prodigy")
    if not url:
        raise ProdigyError("Prodigy API URL not configured")

    if collection is None:
        collection = "prodigy_gpu"
    if outputfield is None:
        outputfield = "complex_s3_uri"
    if main_doc_exp_id is None:
        main_doc_exp_id = experiment_id
    if not chain_list or not isinstance(chain_list, list):
        raise ProdigyError("chain_list must be a non-empty list of strings, e.g., ['A,B', 'C']")
    for item in chain_list:
        if not isinstance(item, str) or not item.strip():
            raise ProdigyError("Each chain_list entry must be a non-empty string")


    # === 1) Initialize Mongo document up front ===
    created_at = datetime.utcnow().isoformat()
    init_contents = {
        "status": "pending",
        "inputparams": {
            "job_name": job_name,
            "tokenid": tokenid,
            "input_path": input_path,
            "chain_list": chain_list,
            "experiment_id": experiment_id,
        },
        "createdAt": created_at,
    }
    try:
        oid = create_document(collection, experiment_id, init_contents)
    except Exception as e:
        logging.error(f"[run_prodigy] Could not create/init Mongo document for experiment {experiment_id}: {e}")
        raise ProdigyError(f"Mongo init failed: {e}")
    if set_uid and tokenid:
        set_owner_uid(str(oid), collection, tokenid)

    # === 2) Build payload & update Mongo ===
    payload = {
        "job_name": job_name,
        "tokenid": tokenid,
        "experiment_id": experiment_id,
        "input_path": input_path,
        "chain_list": chain_list,
    }
    try:
        set_input_params(str(oid), collection, (payload, created_at))
    except Exception:
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

    # === 3) Submit API request ===
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=certifi.where()) as client:
            logging.info(f"[run_prodigy] POST {url} experiment_id={experiment_id}")
            json_response, _, _, _, _ = await post_api_request_async(client, api_args)
            initial_status = json_response.get("status", "").lower()
    except KeyboardInterrupt:
        logging.warning("[run_prodigy] Execution interrupted by user.")
        raise ProdigyError("prodigy execution interrupted by user.")
    except Exception as e:
        logging.error(f"[run_prodigy] API call failed: {e}")
        raise ProdigyError(f"prodigy API call failed: {e}")

    # === 4) Handle immediate vs queued status ===
    if initial_status == "error":
        logging.warning(f"[run_prodigy] API returned error status. Response: {json_response}")
        raise ProdigyError(f"prodigy failed with status: {initial_status}")
    elif initial_status in ("completed", "success"):
        status = initial_status
        res = json_response
    else:
        logging.info(f"[run_prodigy] Initial status = {initial_status}. Waiting on Mongo status...")
        try:
            status, res = await fetch_collections_data(
                collection=collection,
                experiment_id=experiment_id,
                outfield="output.datainfo.outputFilePath",
                timeout=timeout
            )
        except KeyboardInterrupt:
            logging.warning("[run_prodigy] Monitoring interrupted by user.")
            raise ProdigyError("prodigy monitoring interrupted by user.")
        except Exception as e:
            logging.error(f"[run_prodigy] Mongo wait failed: {e}")
            raise ProdigyError(f"Mongo wait failed: {e}")
        logging.info(f"[run_prodigy] Final status = {status}, response fragment = {res!r}")

    if status not in ("completed", "success"):
        raise ProdigyError(f"prodigy failed with status: {status}")

    # === 5) Extract S3 URI from response ===
    output_zip_s3_uri = res.get("output.datainfo.outputFilePath")
    if not output_zip_s3_uri:
        raise ProdigyError(f"No outputFilePath in response data: {res}")
    s3_input_key = output_zip_s3_uri

    # === 6) Prepare local directories ===
    local_dir = os.path.join("antibody_workflow", experiment_id)
    os.makedirs(local_dir, exist_ok=True)

    # === 7) Download full Prodigy CSV from S3 ===
    local_csv = os.path.join(local_dir, "prodigy_full.csv")
    try:
        download_from_s3(s3_input_key, local_csv, bucket_name=S3_BUCKET)
    except Exception as e:
        raise ProdigyError(f"Failed to download Prodigy CSV from S3: {e}")

    # === 8) Select top negative affinities CSV ===
    top_csv_local = os.path.join(local_dir, "top_prodigy_affinities.csv")
    try:
        actual_n = select_top_negative_affinities_csv(local_csv, top_csv_local, top_n)
    except Exception as e:
        raise ProdigyError(f"Failed to parse & select top affinities: {e}")

    # === 9) Prepare PDB ZIP extraction ===
    # Determine local input ZIP: if input_path is S3 URI, download; else assume local path
    # Use a temp file for input ZIP if needed
    def _download_input_zip(uri: str) -> str:
        # if uri.startswith("s3://"):
        #     tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip")
        #     os.close(tmp_fd)
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip")
            os.close(tmp_fd)
            download_from_s3(uri, tmp_path, bucket_name=S3_BUCKET)
        except Exception as e:
            raise ProdigyError(f"Failed to download input ZIP from S3: {e}")
        return tmp_path
        # else:
        #     if not os.path.isfile(uri):
        #         raise ProdigyError(f"Local input ZIP not found: {uri}")
        #     return uri

    try:
        local_input_zip
        local_input_zip = _download_input_zip(input_path)
    except ProdigyError:
        raise
    except Exception as e:
        raise ProdigyError(f"Error preparing input ZIP: {e}")

    # Read top IDs from CSV
    top_ids: List[str] = []
    with open(top_csv_local, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if 'id' in row:
                top_ids.append(row['id'])
    if not top_ids:
        raise ProdigyError("No IDs found in top affinities CSV to extract PDBs.")

    # Extract matching PDB files from input ZIP
    extracted_dir = os.path.join(local_dir, "top_pdbs")
    os.makedirs(extracted_dir, exist_ok=True)
    try:
        with zipfile.ZipFile(local_input_zip, 'r') as zin:
            for member in zin.namelist():
                basename = os.path.basename(member)
                stem, ext = os.path.splitext(basename)
                if stem in top_ids and ext.lower() == '.pdb':
                    # Extract to extracted_dir preserving basename
                    try:
                        zin.extract(member, path=extracted_dir)
                    except Exception:
                        # If nested, extract and rename
                        data = zin.read(member)
                        out_path = os.path.join(extracted_dir, basename)
                        with open(out_path, 'wb') as outf:
                            outf.write(data)
    except zipfile.BadZipFile as e:
        raise ProdigyError(f"Input ZIP is invalid: {e}")
    except Exception as e:
        raise ProdigyError(f"Error extracting PDBs: {e}")

    # === 10) Create ZIP of selected PDBs ===
    top_pdbs_zip_local = os.path.join(local_dir, "top_prodigy_pdbs.zip")
    try:
        with zipfile.ZipFile(top_pdbs_zip_local, 'w', zipfile.ZIP_DEFLATED) as zout:
            for fname in os.listdir(extracted_dir):
                file_path = os.path.join(extracted_dir, fname)
                if os.path.isfile(file_path):
                    # Add without directory prefix
                    zout.write(file_path, arcname=fname)
    except Exception as e:
        raise ProdigyError(f"Failed to create top PDBs ZIP: {e}")

    # === 11) Upload top CSV and PDB ZIP to S3 ===
    # CSV
    top_csv_key = f"{tokenid}/{experiment_id}/prodigy/top_prodigy_affinities.csv"

    top_zip_key = f"{tokenid}/{experiment_id}/prodigy/top_prodigy_pdbs.zip"

    # === 12) Return result ===
    return {
        "top_n": actual_n,
        "top_csv_s3_uri": top_csv_key,
        "top_pdbs_zip_s3_uri": top_zip_key
    }


from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from app.tools.tool_waiter import await_async_tool
# Pydantic model and StructuredTool wrapper remain unchanged
class ProdigyInput(BaseModel):
    input_path: str = Field(..., description="ZIP of PDBs from megadock or S3 URI")
    chain_list: List[str] = Field(["A,B","C"], description="List of chain identifiers for Prodigy API; entries like ['A,B', 'C'] are accepted as default/fixed")
    experiment_id: str = Field(..., description="Experiment ID from prior steps")
    tokenid: str = Field(..., description="User token ID")
    top_n: int = Field(5, description="Number of top complexes to select")
    collection: str = Field("prodigy", description="Mongo collection name")
    outputfield: str = Field("topn_output_s3_uri", description="Field for Prodigy result ZIP in Mongo")
    set_uid: bool = Field(True)
    Node: str = Field("pr_node", description="Internal node name for tracking")
    main_doc_exp_id: str = Field(None)
    timeout: float = Field(18000.0)


def _prodigy_fn(
    input_path: str,
    experiment_id: str,
    tokenid: str,
    chain_list: List[str] =["A,B","C"] ,
    top_n: int = 10,
    collection: str = "prodigy",
    set_uid: bool = True,
    Node: str = "pr_node",
    main_doc_exp_id: str = None,
    timeout: float = 18000.0,
) -> dict:
    job_name = f"pg_{experiment_id}"
    out = await_async_tool(run_prodigy)(
        job_name=job_name,
        tokenid=tokenid,
        chain_list=chain_list,
        experiment_id=experiment_id,
        input_path=input_path,
        top_n=top_n,
        collection=collection,
        set_uid=set_uid,
        Node=Node,
        main_doc_exp_id=main_doc_exp_id or experiment_id,
        timeout=timeout,
    )
    return out

prodigy_tool = StructuredTool.from_function(
    name="run_prodigy",
    description="Run Prodigy ranking on Megadock outputs; returns top affinities CSV and ZIP of corresponding PDBs.",
    func=_prodigy_fn,
    args_schema=ProdigyInput,
)
