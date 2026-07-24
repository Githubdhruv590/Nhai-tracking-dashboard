import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the current directory
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

SPREADSHEET_URL = os.getenv("SPREADSHEET_URL", "").strip()
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json").strip()

def get_service_account_path() -> str:
    """
    Returns the absolute path of the Google service account JSON file.
    If the path specified is relative, resolves it relative to the project root.
    """
    path = Path(GOOGLE_APPLICATION_CREDENTIALS)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    return str(path)

def get_spreadsheet_id() -> str:
    """
    Extracts the Google Spreadsheet ID from the SPREADSHEET_URL.
    """
    url = SPREADSHEET_URL
    if not url:
        return ""
    
    # Typical spreadsheet URL format:
    # https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit#gid=0
    # or just the ID itself
    if "docs.google.com/spreadsheets" in url:
        try:
            parts = url.split("/d/")
            if len(parts) > 1:
                subparts = parts[1].split("/")
                return subparts[0]
        except Exception:
            pass
    return url  # Fallback to the url itself if it looks like an ID
