import io
import json
import logging
import time
import random
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
from utils import execute_with_retry
import utils

logger = logging.getLogger(__name__)

def get_excel_from_folder(drive_service, drive_id: str, is_file: bool = False):
    """
    Retrieves Excel file content from Google Drive in-memory.
    
    If is_file is True:
      Directly fetches and downloads the file matching drive_id.
    If is_file is False (default):
      Lists all files inside the Google Drive folder matching drive_id,
      ignores PDFs, uses a scoring heuristic to choose the best Excel report,
      and downloads it.
      
    Supports Shared Drives/Team Drives and detailed Google API error extraction.
    
    Returns:
      (bytes_content, file_name)
    """
    # Verify Drive service initialization
    if not drive_service:
        print("[-] Error: Drive service client is NOT initialized (is None)!")
        raise ValueError("Drive service client is not initialized.")
    else:
        print("[+] Drive service client is successfully initialized.")
        
    if not drive_id or not drive_id.strip():
        raise ValueError("Report Link is missing or invalid in Spreadsheet")
        
    try:
        file_id = None
        file_name = None
        
        if is_file:
            print(f"[+] Accessing direct file link. Extracted File ID: '{drive_id}'")
            # Retrieve file metadata to confirm it's an Excel file
            try:
                request = drive_service.files().get(
                    fileId=drive_id,
                    fields="id, name, mimeType",
                    supportsAllDrives=True
                )
                f = execute_with_retry(request)
            except HttpError as he:
                print(f"[-] HTTP Error fetching metadata for File ID '{drive_id}': Status {he.resp.status}")
                print(f"[-] API Response: {he.content.decode('utf-8')}")
                raise he
                
            name = f.get('name', '').strip()
            mime = f.get('mimeType', '').strip().lower()
            name_lower = name.lower()
            
            # Verify if it's an Excel file
            is_excel = (
                name_lower.endswith('.xlsx') or 
                name_lower.endswith('.xls') or 
                mime in [
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    'application/vnd.ms-excel'
                ]
            )
            
            if not is_excel:
                print(f"[-] Error: Linked file '{name}' is not a valid Excel file. MimeType: {mime}")
                raise ValueError(f"Linked file '{name}' is not an Excel file (Mime: {mime}).")
                
            file_id = drive_id
            file_name = name
            print(f"[+] Successfully verified Excel file: '{file_name}'")
            
        else:
            print(f"[+] Accessing folder. Extracted Folder ID: '{drive_id}'")
            # Query files inside the folder (supporting Shared Drives)
            query = f"'{drive_id}' in parents and trashed = false"
            print(f"[+] Exact query passed to files().list(): \"{query}\"")
            
            try:
                request = drive_service.files().list(
                    q=query,
                    fields="files(id, name, mimeType)",
                    pageSize=100,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                )
                results = execute_with_retry(request)
            except HttpError as he:
                print(f"[-] HTTP Error listing files in Folder ID '{drive_id}': Status {he.resp.status}")
                print(f"[-] API Response: {he.content.decode('utf-8')}")
                raise he
                
            files = results.get('files', [])
            
            print(f"[+] Folder ID '{drive_id}' list results: Found {len(files)} files.")
            for idx, f in enumerate(files):
                print(f"    [{idx + 1}] File: '{f.get('name')}' | ID: {f.get('id')} | Mime: {f.get('mimeType')}")
                
            excel_files = []
            for f in files:
                name = f.get('name', '').strip()
                mime = f.get('mimeType', '').strip().lower()
                name_lower = name.lower()
                
                # Explicitly ignore PDFs
                if name_lower.endswith('.pdf') or mime == 'application/pdf':
                    continue
                    
                # Check if Excel file (by extension or mime type)
                is_excel = (
                    name_lower.endswith('.xlsx') or 
                    name_lower.endswith('.xls') or 
                    mime in [
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        'application/vnd.ms-excel'
                    ]
                )
                
                if is_excel:
                    # Scoring heuristic to select the best Excel file if multiple exist
                    score = 0
                    if "furniture" in name_lower:
                        score += 15
                    if "asset" in name_lower:
                        score += 10
                    if "report" in name_lower:
                        score += 5
                    if "final" in name_lower:
                        score += 5
                    if "submit" in name_lower:
                        score += 3
                    if "copy" in name_lower:
                        score -= 10
                    if "backup" in name_lower:
                        score -= 10
                    if "temp" in name_lower or "tmp" in name_lower:
                        score -= 15
                        
                    excel_files.append((score, f))
                    
            if not excel_files:
                print(f"[-] Error: No Excel files found inside folder '{drive_id}' after ignoring PDFs.")
                raise FileNotFoundError(f"No Excel files found in Drive folder ID: {drive_id}")
                
            # Sort by score descending; fallback to shorter names as tie breaker
            excel_files.sort(key=lambda x: (x[0], -len(x[1].get('name', ''))), reverse=True)
            best_score, selected_file = excel_files[0]
            
            file_id = selected_file['id']
            file_name = selected_file['name']
            print(f"[+] Selected Excel file: '{file_name}' (Score: {best_score}, ID: {file_id})")
            
        # Download the file content in-memory with retry logic
        print(f"[+] Starting download for file: '{file_name}' (ID: {file_id})")
        backoff = 1.0
        retries = 5
        for attempt in range(1, retries + 1):
            try:
                request = drive_service.files().get_media(
                    fileId=file_id,
                    supportsAllDrives=True
                )
                file_stream = io.BytesIO()
                downloader = MediaIoBaseDownload(file_stream, request)
                
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    
                file_stream.seek(0)
                print(f"[+] Download complete for '{file_name}' ({len(file_stream.getvalue())} bytes).")
                return file_stream.getvalue(), file_name
            except Exception as e:
                if attempt == retries:
                    raise e
                err_str = str(e).lower()
                is_transient = any(keyword in err_str for keyword in ["connection", "timeout", "max retry", "socket", "10054", "winerror 10054"])
                if isinstance(e, HttpError) and (e.resp.status >= 500 or e.resp.status == 429):
                    is_transient = True
                    
                if is_transient:
                    utils.transient_retry_count += 1
                    sleep_time = backoff + random.uniform(0, 0.5)
                    print(f"[-] Download failed due to transient error: {e}. Attempt {attempt}/{retries}. Retrying in {sleep_time:.2f}s...")
                    time.sleep(sleep_time)
                    backoff *= 2.0
                else:
                    raise e
        
    except HttpError as he:
        # Extract precise HTTP error details
        try:
            err_data = json.loads(he.content.decode('utf-8'))
            err_msg = err_data.get('error', {}).get('message', he.reason)
        except Exception:
            err_msg = he.reason
            
        status_code = he.resp.status
        detailed_msg = f"Google Drive API HTTP {status_code}: {err_msg}"
        logger.error(f"Drive API Exception: {detailed_msg}")
        raise Exception(detailed_msg) from he
        
    except Exception as e:
        logger.error(f"Unexpected error retrieving file from Drive (ID: {drive_id}): {e}")
        raise e
