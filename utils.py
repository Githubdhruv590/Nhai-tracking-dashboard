import re
import logging
import time
import random
import socket
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

transient_retry_count = 0

def reset_retry_count():
    global transient_retry_count
    transient_retry_count = 0

def get_retry_count():
    global transient_retry_count
    return transient_retry_count

def execute_with_retry(request, retries=5, initial_backoff=1.0):
    """
    Executes a Google API request with retry logic and exponential backoff.
    Handles transient 5xx HTTP errors, connection resets, timeouts, and other network errors.
    """
    global transient_retry_count
    backoff = initial_backoff
    for attempt in range(1, retries + 1):
        try:
            return request.execute()
        except HttpError as e:
            status = e.resp.status
            if status >= 500 or status == 429:
                if attempt == retries:
                    raise e
                transient_retry_count += 1
                sleep_time = backoff + random.uniform(0, 0.5)
                logger.warning(f"Transient HTTP {status} on attempt {attempt}/{retries}. Retrying in {sleep_time:.2f}s...")
                time.sleep(sleep_time)
                backoff *= 2.0
            else:
                raise e
        except (socket.timeout, ConnectionResetError, ConnectionAbortedError, ConnectionError, OSError) as e:
            if attempt == retries:
                raise e
            transient_retry_count += 1
            sleep_time = backoff + random.uniform(0, 0.5)
            logger.warning(f"Network error '{e}' on attempt {attempt}/{retries}. Retrying in {sleep_time:.2f}s...")
            time.sleep(sleep_time)
            backoff *= 2.0
        except Exception as e:
            err_str = str(e).lower()
            is_transient = any(keyword in err_str for keyword in ["connection", "timeout", "max retry", "socket", "10054"])
            if is_transient and attempt < retries:
                transient_retry_count += 1
                sleep_time = backoff + random.uniform(0, 0.5)
                logger.warning(f"Suspected transient error '{e}' on attempt {attempt}/{retries}. Retrying in {sleep_time:.2f}s...")
                time.sleep(sleep_time)
                backoff *= 2.0
            else:
                raise e

def extract_folder_id(url: str) -> str:
    """
    Extracts the Google Drive Folder ID from various URL formats.
    Supported formats:
    - https://drive.google.com/drive/folders/FOLDER_ID
    - https://drive.google.com/drive/u/0/folders/FOLDER_ID
    - https://drive.google.com/open?id=FOLDER_ID
    """
    drive_id, is_file = extract_drive_info(url)
    if not is_file:
        return drive_id
    return ""

def extract_drive_info(url: str):
    """
    Extracts the Google Drive ID from a URL and determines if it points to a file or folder.
    
    Returns:
      (drive_id, is_file)
    """
    if not url:
        return "", False
    url = url.strip()
    
    # 1. Check for file link format: /file/d/FILE_ID
    file_match = re.search(r"/file/d/([a-zA-Z0-9-_]+)", url)
    if file_match:
        return file_match.group(1), True
        
    # 2. Check for folder link format: /folders/FOLDER_ID
    folder_match = re.search(r"/folders/([a-zA-Z0-9-_]+)", url)
    if folder_match:
        return folder_match.group(1), False
        
    # 3. Check for open?id=ID format
    open_match = re.search(r"[?&]id=([a-zA-Z0-9-_]+)", url)
    if open_match:
        is_file = "file" in url.lower() or ("view" in url.lower() and "folder" not in url.lower())
        return open_match.group(1), is_file
        
    # 4. Check if the url itself looks like a raw ID (no spaces, slashes, or dots, and length between 19 and 50)
    if re.match(r"^[a-zA-Z0-9-_]+$", url) and "/" not in url and "." not in url:
        if 19 <= len(url) <= 50:
            return url, False
        
    return "", False


def parse_chainage(value) -> float:
    """
    Parses a chainage value to a float. Handles:
    - Numeric values (e.g., 18500, 18.5)
    - Chainage strings with '+' (e.g., "18+500", " 18 + 500 ", "18+000")
    - Comma-separated numbers (e.g., "18,500")
    - Drops unit prefixes/suffixes if present (e.g. "km 18+500", "Ch 18500")
    
    Raises ValueError if conversion is not possible.
    """
    if value is None or (isinstance(value, float) and value != value): # check NaN
        raise ValueError("Chainage is None or NaN")
        
    # Convert to string and clean up
    val_str = str(value).strip().lower()
    if not val_str:
        raise ValueError("Chainage is empty")
        
    # Remove common prefixes like 'ch', 'km', 'chainage' and spaces
    val_str = re.sub(r"^(ch|km|chainage)\.?\s*", "", val_str)
    val_str = val_str.replace(" ", "")
    
    # Check if there is a plus sign
    if "+" in val_str:
        parts = val_str.split("+")
        if len(parts) == 2:
            km_part = parts[0].strip().replace(",", "")
            m_part = parts[1].strip().replace(",", "")
            
            km = float(km_part) if km_part else 0.0
            m = float(m_part) if m_part else 0.0
            
            # Note: if km is 18 and m is 500, return 18500.0.
            # If the user has other chainages in km (e.g. 18.5 and 19.0), they usually don't use the '+' format.
            # Standard NHAI chainage representation uses + for meters.
            return km * 1000.0 + m
        else:
            raise ValueError(f"Invalid chainage plus format: '{value}'")
            
    # Try standard numeric conversion
    cleaned = val_str.replace(",", "")
    # Check if it has letters or symbols (other than dot/minus)
    if re.search(r"[a-z]", cleaned):
         # Try to extract first floating number found
         match = re.search(r"[-+]?\d*\.\d+|\d+", cleaned)
         if match:
             return float(match.group())
         raise ValueError(f"Invalid characters in chainage: '{value}'")
         
    return float(cleaned)
