# app/utils/api_utils.py

import os
import tempfile
import ssl
import certifi
import traceback
import logging
import httpx
import asyncio
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
from typing import Tuple, Any, Dict

# Import your S3 upload/download from commons
from commons.s3_upload import upload_to_s3, download_from_s3
from app.config import MONGO_URI, DB_NAME

# --- Configuration ---
ssl_context = ssl.create_default_context(cafile=certifi.where())

# --- MongoDB Helpers ---
def get_db(db_name: str = DB_NAME):
    # Disable TLS validation if necessary; adjust per your setup
    client = MongoClient(MONGO_URI, tls=False, tlsAllowInvalidCertificates=True)
    return client[db_name]

initialize_mongo = get_db

# --- Document Utilities ---
def generate_hex_code(input_str: str, num_str: str) -> ObjectId:
    """
    Generate a pseudo-ObjectId from input_str + num_str.
    """
    try:
        hex_str = input_str[:24]
        hex_value = int(hex_str, 16)
        num_value = int(num_str)
        new_value = hex_value + num_value
        new_hex = hex(new_value)[2:].upper().zfill(24)[:24]
        return ObjectId(new_hex)
    except Exception:
        raise ValueError("Invalid input for hex generation")

def create_document(collection: str, doc_id: str, contents: dict) -> ObjectId:
    """
    Create or replace a Mongo document with given _id. If doc_id invalid ObjectId, generate one.
    """
    db = initialize_mongo()
    try:
        oid = ObjectId(doc_id)
    except Exception:
        # Generate a new ObjectId-like from doc_id string
        oid = generate_hex_code(doc_id, "0")
    contents["_id"] = oid
    try:
        db[collection].replace_one({"_id": oid}, contents, upsert=True)
    except Exception as e:
        logging.error(f"[create_document] MongoDB error replacing document {oid} in {collection}: {e}")
        raise
    return oid

def set_owner_uid(doc_id: str, collection: str, user_id: str) -> None:
    """
    Upserts the owner UID on the given document, if doc_id and user_id are valid ObjectId strings.
    """
    db = initialize_mongo()
    try:
        oid = ObjectId(doc_id)
        new_uid = ObjectId(user_id)
    except Exception as e:
        logging.warning(f"[set_owner_uid] Invalid document ID or user ID for ObjectId: {e}")
        return
    try:
        col = db[collection]
        col.update_one(
            {"_id": oid},
            {"$set": {"uid": new_uid, "userId": new_uid}},
            upsert=True
        )
    except Exception as e:
        logging.error(f"[set_owner_uid] MongoDB error updating uid for {doc_id} in {collection}: {e}")

def set_input_params(doc_id: str, collection: str, inp: Tuple[Any, str]) -> None:
    """
    Set inputparams and mark status pending on the document.
    """
    db = initialize_mongo()
    try:
        oid = ObjectId(doc_id)
    except Exception as e:
        logging.warning(f"[set_input_params] Invalid doc_id for ObjectId: {e}")
        return
    params, created_at = inp
    try:
        db[collection].update_one(
            {"_id": oid},
            {"$set": {"inputparams": params, "status": "pending", "createdAt": created_at}},
            upsert=True
        )
    except Exception as e:
        logging.error(f"[set_input_params] MongoDB error for {doc_id} in {collection}: {e}")

# --- S3 Helpers ---

def ensure_s3_uri(local_or_uri: str, bucket_name: str, prefix: str) -> str:
    """
    If local_or_uri starts with "s3://", return as-is; else upload to S3 with given prefix
    and return "s3://bucket_name/key".
    """
    if local_or_uri.startswith("s3://"):
        return local_or_uri
    if not os.path.exists(local_or_uri):
        raise FileNotFoundError(f"Local file not found: {local_or_uri}")
    # Construct S3 key: <prefix>/<filename>
    filename = os.path.basename(local_or_uri)
    key = f"{prefix}/{filename}"
    # Use upload_to_s3: returns object_key or maybe full URI? Adapt depending on your commons.s3_upload implementation.
    # Let's assume upload_to_s3 returns the object_key, and we build "s3://bucket_name/object_key"
    bucket = bucket_name or os.getenv("S3_BUCKET_NAME")
    if not bucket:
        raise RuntimeError("S3_BUCKET_NAME not set")
    try:
        upload_to_s3(local_or_uri, key, bucket)
    except Exception as e:
        raise RuntimeError(f"S3 upload failed for {local_or_uri}: {e}")
    return f"s3://{bucket}/{key}"

def download_from_s3_uri(s3_uri: str, local_path: str) -> str:
    """
    Download from s3://bucket/key to local_path.
    """
    if not s3_uri.startswith("s3://"):
        raise ValueError("Not a valid S3 URI")
    parts = s3_uri[5:].split("/", 1)
    if len(parts) != 2:
        raise ValueError("Invalid S3 URI format")
    bucket, key = parts
    try:
        download_from_s3(key, local_path, bucket_name=bucket)
    except Exception as e:
        raise RuntimeError(f"S3 download failed for {s3_uri}: {e}")
    return local_path

# --- API Interaction & Monitoring ---

async def post_api_request_async(
    client: httpx.AsyncClient,
    tup: Tuple[dict, str, str, str, str, str, bool, str, str]
) -> Tuple[dict, str, str, str, str]:
    """
    Expects tup = (payload:dict, url:str, user_id:str, collection:str, experiment_id:str,
                   outputfield:str, set_uid:bool, Node:str, main_doc_exp_id:str)
    Posts JSON to external API, tags ownership in Mongo, and returns (json_response, collection, experiment_id, outputfield, main_doc_exp_id).
    """
    payload, url, user_id, collection, experiment_id, outputfield, set_uid, Node, main_doc_exp_id = tup
    
    # Tag owner in Mongo if enabled
    if set_uid and user_id:
        set_owner_uid(experiment_id, collection, user_id)

    headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    # No API-key header, since external API doesn't require it per your note

    logging.info(f"[post_api_request_async] POST {url} with experiment_id={experiment_id}")
    try:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code if e.response else "<no response>"
        text = e.response.text if e.response else ""
        logging.error(f"[post_api_request_async] HTTP error {status} for {url}: {text}")
        raise
    except Exception as e:
        logging.exception(f"[post_api_request_async] Exception posting to {url}: {e}")
        raise

    try:
        data = resp.json()
    except Exception:
        logging.error(f"[post_api_request_async] Failed to parse JSON from {url}")
        raise

    return data, collection, experiment_id, outputfield, main_doc_exp_id

async def fetch_collections_data(
    collection: str, experiment_id: str, outfield: str,
    timeout: float = 300.0
) -> Tuple[str, Any]:
    """
    Poll MongoDB document status until 'completed' or 'failed', then return (status, doc[outfield]).
    Assumes external API or background process updates the document {status: "...", ...}.
    """
    db = initialize_mongo()
    coll = db[collection]
    try:
        oid = ObjectId(experiment_id)
    except Exception as e:
        logging.warning(f"[fetch_collections_data] Invalid experiment_id for ObjectId: {e}")
        return "failed", None

    # initial check
    doc = coll.find_one({"_id": oid})
    status = (doc or {}).get("status", "").lower()
    if status in ("completed", "failed"):
        return status, _extract_outfield(doc, outfield)

    # watch for updates via change stream (requires Mongo replica set)
    import time
    start = time.time()
    pipeline = [{"$match": {"operationType": "update", "documentKey._id": oid, "updateDescription.updatedFields.status": {"$exists": True}}}]
    try:
        with coll.watch(pipeline, full_document='updateLookup') as stream:
            while time.time() - start < timeout:
                change = stream.try_next()
                if change:
                    doc = change["fullDocument"]
                    status = doc.get("status", "").lower()
                    if status in ("completed", "failed"):
                        return status, _extract_outfield(doc, outfield)
                time.sleep(0.1)
    except Exception as e:
        logging.warning(f"[fetch_collections_data] Change stream error or timeout: {e}")

    # Timeout
    return "timeout", None

def _extract_outfield(doc: dict, outfield: str) -> Any:
    """
    Extract nested field from doc by dot notation.
    If outfield == "*", return whole doc.
    """
    if outfield == "*" or not outfield:
        return doc
    parts = outfield.split(".")
    val = doc
    for p in parts:
        if isinstance(val, dict):
            val = val.get(p)
        else:
            return None
    return val

async def parallel_requests(req_list: list) -> list:
    """
    Execute multiple post_api_request_async in parallel, then fetch results.
    Each tup should match post_api_request_async signature.
    Returns list of (status, data) tuples.
    """
    timeout = httpx.Timeout(600.0)
    async with httpx.AsyncClient(timeout=timeout, verify=certifi.where()) as client:
        tasks = [post_api_request_async(client, t) for t in req_list]
        resps = await asyncio.gather(*tasks, return_exceptions=True)
    results = []
    for resp, tup in zip(resps, req_list):
        if isinstance(resp, Exception):
            results.append(("failed", str(resp)))
        else:
            data, collection, exp, outfield, main_id = resp
            try:
                status, data2 = await fetch_collections_data(collection, exp, outfield)
                results.append((status, data2))
            except Exception as e:
                results.append(("failed", str(e)))
    return results
