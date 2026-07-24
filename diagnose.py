import os
import sys
import json
from googleapiclient.errors import HttpError

import config
from google_sheet_reader import get_google_services, read_package_projects
from drive_reader import get_excel_from_folder
from excel_parser import parse_furniture_assets
from calculator import classify_and_calculate_lengths

def format_len(val):
    return f"{val:,.2f} m" if val is not None else "N/A"

def main():
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass # fallback for older python versions
        
    print("==================================================")
    print("         NHAI END-TO-END PIPELINE DIAGNOSTICS      ")
    print("==================================================")
    
    # 1. Verify Configuration
    creds_path = config.get_service_account_path()
    spreadsheet_id = config.get_spreadsheet_id()
    
    print("\n[Step 1] Verifying local configuration...")
    print(f"  Service Account Path: '{creds_path}'")
    print(f"  Spreadsheet URL:      '{config.SPREADSHEET_URL}'")
    print(f"  Spreadsheet ID:       '{spreadsheet_id}'")
    
    if not os.path.exists(creds_path):
        print(f"[-] ERROR: Service account file not found at '{creds_path}'")
        sys.exit(1)
        
    if not spreadsheet_id or "your-spreadsheet-id-here" in spreadsheet_id:
        print("[-] ERROR: SPREADSHEET_URL is not set or is still the placeholder in .env")
        sys.exit(1)
        
    print("[+] Configuration looks correct.")
    
    # 2. Authenticate
    print("\n[Step 2] Authenticating with Google APIs...")
    try:
        sheets_service, drive_service = get_google_services(creds_path)
        print("[+] Authentication successful.")
    except Exception as e:
        print(f"[-] ERROR during authentication: {e}")
        sys.exit(1)
        
    # 3. Read spreadsheet packages
    print("\n[Step 3] Fetching projects from Master Spreadsheet...")
    packages = ["Package 1", "Package 2", "Package 3", "Package 4", "Package 5"]
    project_lists = {}
    total_projects = 0
    
    for pkg in packages:
        print(f"  Reading sheet '{pkg}'...")
        try:
            # Note: this will print the detailed debug logs for hyperlink/Drive ID extraction
            projects = read_package_projects(sheets_service, spreadsheet_id, pkg)
            project_lists[pkg] = projects
            total_projects += len(projects)
            print(f"    [+] Found {len(projects)} projects.")
        except Exception as e:
            print(f"    [-] ERROR reading sheet '{pkg}': {e}")
            project_lists[pkg] = []
            
    if total_projects == 0:
        print("[-] ERROR: No projects found in any package sheets. Exiting.")
        sys.exit(1)
        
    print(f"\n[+] Total projects found across all packages: {total_projects}")
    
    # 4. Access Drive and Run Calculations for each project
    print("\n[Step 4] Processing each project end-to-end...")
    print("--------------------------------------------------")
    
    success_count = 0
    fail_count = 0
    
    for pkg in packages:
        projects = project_lists[pkg]
        if not projects:
            continue
            
        print(f"\n--- {pkg} Diagnostics ---")
        # Process up to 3 projects per package for quick diagnostics, or all if short
        for proj in projects[:3]:  # Diagnostic run processes first 3 projects of each package
            name = proj["name"]
            drive_id = proj["folder_id"]
            is_file = proj.get("is_file", False)
            drive_url = proj["drive_url"]
            
            print(f"\nProject: '{name}'")
            print(f"  URL:         {drive_url}")
            print(f"  Drive ID:    '{drive_id}'")
            print(f"  Link Type:   {'Direct File' if is_file else 'Folder'}")
            
            try:
                # A. Download Excel file from Drive
                excel_bytes, file_name = get_excel_from_folder(drive_service, drive_id, is_file=is_file)
                print(f"  [+] Downloaded report: '{file_name}' ({len(excel_bytes)} bytes)")
                
                # B. Parse Excel worksheet
                df = parse_furniture_assets(excel_bytes)
                print(f"  [+] Worksheet 'Furniture Assets' parsed successfully. Row count: {len(df)}")
                
                # C. Calculate lengths
                lengths = classify_and_calculate_lengths(df)
                print(f"  [+] Calculations:")
                print(f"      - Total MCW Length:             {format_len(lengths['mcw_length'])}")
                print(f"      - Total Service Road Length:     {format_len(lengths['service_road_length'])}")
                print(f"      - Total Intersecting Road Length: {format_len(lengths['intersecting_road_length'])}")
                
                success_count += 1
            except Exception as e:
                print(f"  [-] FAILURE: {e}")
                fail_count += 1
                
    print("\n==================================================")
    print("               DIAGNOSTICS SUMMARY                ")
    print("==================================================")
    print(f"  Total Projects Attempted: {success_count + fail_count}")
    print(f"  Successful End-to-End:    {success_count}")
    print(f"  Failed:                   {fail_count}")
    print("==================================================")
    
    if fail_count > 0:
        print("\nTroubleshooting Tips:")
        print("1. If you get 'HTTP 404: File not found', make sure the Drive URL is correct and the Service Account email")
        print("   has been added as a Viewer on the Google Drive folder or file.")
        print("2. If you get 'HTTP 403: Google Drive API has not been used...', visit the Google Cloud Console")
        print("   and enable the 'Google Drive API' for your project.")
        print("3. Ensure that your local terminal has internet access to Google services.")

if __name__ == "__main__":
    main()
