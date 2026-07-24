import os
import sys
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def main():
    folder_id = "1hu_1caTcxyvIrV4EKWQjyrRnEmVBOPcS"
    creds_path = "service_account.json"
    
    print("==================================================")
    print("      STANDALONE DRIVE API VERIFICATION           ")
    print("==================================================")
    print(f"Folder ID: '{folder_id}'")
    print(f"Credentials File: '{creds_path}'")
    
    # 1. Check credentials file existence
    if not os.path.exists(creds_path):
        print(f"[-] ERROR: '{creds_path}' not found in the current directory.")
        sys.exit(1)
        
    # 2. Authenticate
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    try:
        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        drive_service = build('drive', 'v3', credentials=creds, cache_discovery=False)
        print("[+] Drive service initialized successfully.")
    except Exception as e:
        print(f"[-] Authentication failed: {e}")
        sys.exit(1)
        
    # 3. Call files().get()
    print("\n--- [Step 1] Calling files().get() ---")
    get_success = False
    try:
        response_get = drive_service.files().get(
            fileId=folder_id,
            fields="id, name, mimeType, owners, capabilities, permissions",
            supportsAllDrives=True
        ).execute()
        print("[+] SUCCESS: files().get() returned:")
        print(json.dumps(response_get, indent=2))
        get_success = True
    except HttpError as he:
        print(f"[-] HTTP ERROR on files().get(): Status {he.resp.status}")
        try:
            err_details = json.loads(he.content.decode('utf-8'))
            print("Response Body:")
            print(json.dumps(err_details, indent=2))
        except Exception:
            print(f"Raw Response Content: {he.content}")
    except Exception as e:
        print(f"[-] Unexpected Error on files().get(): {e}")
        
    # 4. Call files().list()
    print("\n--- [Step 2] Calling files().list() ---")
    query = f"'{folder_id}' in parents and trashed = false"
    print(f"Query: \"{query}\"")
    
    list_success = False
    try:
        response_list = drive_service.files().list(
            q=query,
            fields="files(id, name, mimeType)",
            pageSize=100,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        print("[+] SUCCESS: files().list() returned:")
        print(json.dumps(response_list, indent=2))
        list_success = True
    except HttpError as he:
        print(f"[-] HTTP ERROR on files().list(): Status {he.resp.status}")
        try:
            err_details = json.loads(he.content.decode('utf-8'))
            print("Response Body:")
            print(json.dumps(err_details, indent=2))
        except Exception:
            print(f"Raw Response Content: {he.content}")
    except Exception as e:
        print(f"[-] Unexpected Error on files().list(): {e}")
        
    # 5. Analysis & Diagnosis
    print("\n==================================================")
    print("               DIAGNOSIS REPORT                   ")
    print("==================================================")
    
    if get_success and list_success:
        files_found = response_list.get('files', [])
        print("[+] Both API calls succeeded.")
        print(f"[+] Folder exists and is fully visible to the Service Account.")
        print(f"[+] Children count: {len(files_found)}")
        excel_files = [f for f in files_found if f.get('name', '').lower().endswith(('.xlsx', '.xls'))]
        print(f"[+] Excel files found: {len(excel_files)}")
        for f in excel_files:
            print(f"  - Excel Report: '{f.get('name')}' (ID: {f.get('id')})")
            
        if not excel_files:
            print("[-] CAUSE: The folder is fully accessible, but it contains NO Excel (.xlsx or .xls) files.")
            
    elif not get_success:
        print("[-] CAUSE: The Service Account CANNOT access the folder metadata.")
        print("    This usually means:")
        print("    a) The folder ID is incorrect/invalid.")
        print("    b) The folder belongs to a different domain/drive and the Service Account")
        print("       has not been added as a member or viewer of the folder/Shared Drive.")
        print("    c) Even if the folder is 'Anyone with the link can view' in a web browser,")
        print("       Google's API security policies require explicit sharing (Viewer access)")
        print("       granted directly to the Service Account's email address to allow programmatic access.")
        
    elif get_success and not list_success:
        print("[-] CAUSE: The folder metadata was retrieved successfully, but querying the contents failed.")
        print("    This points to a query syntax issue or a restriction on listing operations for link-shared files.")
        
    print("==================================================")

if __name__ == "__main__":
    main()
