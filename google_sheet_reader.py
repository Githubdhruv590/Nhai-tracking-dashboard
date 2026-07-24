import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
import config
from utils import extract_drive_info, execute_with_retry

logger = logging.getLogger(__name__)

# Scopes required for Sheets and Drive access
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/drive.readonly'
]

def get_google_services(credentials_path: str):
    """
    Authenticates with the service account and returns Sheets and Drive service clients.
    """
    try:
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
        sheets_service = build('sheets', 'v4', credentials=creds, cache_discovery=False)
        drive_service = build('drive', 'v3', credentials=creds, cache_discovery=False)
        return sheets_service, drive_service
    except Exception as e:
        logger.error(f"Failed to authenticate with Service Account: {e}")
        raise e

def detect_columns(rows):
    """
    Intelligently detects:
    1. The header row index.
    2. The column index for Project Name.
    3. The column index for the Drive Folder Link.
    
    Returns:
      (header_idx, project_name_col_idx, drive_link_col_idx)
    """
    if not rows:
        return 0, 0, 18  # Defaults: row 0, col 0 (name), col 18 (S)
        
    header_row_idx = 0
    project_col = -1
    drive_col = -1
    
    # Heuristic 1: Scan first 15 rows to find a header row
    for r_idx in range(min(15, len(rows))):
        row = rows[r_idx]
        row_str = [str(cell).lower().strip() for cell in row]
        
        # Check for project name variations
        proj_keywords = ['project name', 'name of project', 'name of work', 'project description', 'name of the project', 'work name']
        link_keywords = ['submitted report link', 'report link', 'drive link', 'folder link', 'google drive', 'submitted report', 'link to report']
        
        has_proj = any(any(kw in cell for kw in proj_keywords) for cell in row_str)
        has_link = any(any(kw in cell for kw in link_keywords) for cell in row_str)
        
        if has_proj or has_link:
            header_row_idx = r_idx
            # Found potential header row, let's find the exact columns on this row
            for c_idx, cell in enumerate(row_str):
                if project_col == -1 and any(kw in cell for kw in proj_keywords):
                    project_col = c_idx
                if drive_col == -1 and any(kw in cell for kw in link_keywords):
                    drive_col = c_idx
            break
            
    # Heuristic 2: If we couldn't find columns via headers, scan all rows and cell contents
    # We look for a column that contains Google Drive links
    if drive_col == -1:
        drive_counts = [0] * max(len(r) for r in rows)
        for row in rows:
            for c_idx, cell in enumerate(row):
                cell_str = str(cell).strip().lower()
                if "drive.google.com" in cell_str or "folders/" in cell_str:
                    if c_idx < len(drive_counts):
                        drive_counts[c_idx] += 1
                        
        # Column with the most drive links is likely the drive link column
        max_links = max(drive_counts) if drive_counts else 0
        if max_links > 0:
            drive_col = drive_counts.index(max_links)
            
    # Heuristic 3: If project name column is still not found, search for column with text that is not a link
    if project_col == -1:
        # Default to first column with non-empty, non-numeric, non-link text
        for c_idx in range(max(len(r) for r in rows)):
            if c_idx == drive_col:
                continue
            # Check values in this column for first few rows
            text_count = 0
            for r_idx in range(header_row_idx + 1, min(header_row_idx + 10, len(rows))):
                if r_idx < len(rows) and c_idx < len(rows[r_idx]):
                    val = str(rows[r_idx][c_idx]).strip()
                    if val and not val.replace(".", "").isdigit() and "http" not in val:
                        text_count += 1
            if text_count > 3:
                project_col = c_idx
                break
                
    # Fallback to defaults if detection failed
    if project_col == -1:
        project_col = 0
    if drive_col == -1:
        # Try Column S (index 18) as specified in requirements
        drive_col = 18
        
    return header_row_idx, project_col, drive_col

def get_cell_hyperlink(cell) -> str:
    """
    Extracts the hyperlink URL from a cell object returned by includeGridData=True.
    Checks:
    1. Direct cell-level hyperlink.
    2. Hyperlink inside textFormatRuns (for partially formatted or pasted links).
    3. Hyperlink inside chipRuns (for Google Sheets Smart Chips / Rich Links).
    """
    if not cell:
        return ""
        
    # 1. Check cell-level hyperlink
    hyperlink = cell.get('hyperlink')
    if hyperlink:
        return hyperlink.strip()
        
    # 2. Check text format runs for links
    runs = cell.get('textFormatRuns', [])
    for run in runs:
        run_format = run.get('format', {})
        run_link = run_format.get('link', {})
        run_uri = run_link.get('uri')
        if run_uri:
            return run_uri.strip()
            
    # 3. Check chipRuns for Smart Chips / Rich Links
    chip_runs = cell.get('chipRuns', [])
    for run in chip_runs:
        chip = run.get('chip', {})
        link_props = chip.get('richLinkProperties', {})
        uri = link_props.get('uri')
        if uri:
            return uri.strip()
            
    return ""

def read_package_projects(sheets_service, spreadsheet_id: str, package_name: str):
    """
    Reads the projects for a specific sheet (e.g. 'Package 1').
    Returns a list of dicts: [{'name': str, 'drive_url': str, 'folder_id': str, 'is_file': bool}]
    """
    try:
        # Request grid data to extract hyperlink metadata from cells
        range_name = f"'{package_name}'!A1:Z200"
        request = sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            ranges=[range_name],
            includeGridData=True
        )
        result = execute_with_retry(request)
        
        sheets = result.get('sheets', [])
        if not sheets:
            logger.warning(f"No sheets found for '{package_name}'")
            return []
            
        sheet_data = sheets[0].get('data', [])
        if not sheet_data:
            logger.warning(f"No data found in sheet '{package_name}'")
            return []
            
        row_data = sheet_data[0].get('rowData', [])
        if not row_data:
            logger.warning(f"No row data found in sheet '{package_name}'")
            return []
            
        # Convert rowData structure to a list of lists of cell dicts and raw strings
        rows_for_detection = []
        rows_cells = []
        
        for r in row_data:
            cells = r.get('values', [])
            rows_cells.append(cells)
            
            row_vals = []
            for cell in cells:
                # Use hyperlink if present for detection, else display value
                hyperlink = get_cell_hyperlink(cell)
                display_val = cell.get('formattedValue', '').strip()
                row_vals.append(hyperlink if hyperlink else display_val)
            rows_for_detection.append(row_vals)
            
        header_idx, proj_col, drive_col = detect_columns(rows_for_detection)
        logger.info(f"Sheet '{package_name}': Header Row={header_idx}, Project Name Col={proj_col}, Drive Link Col={drive_col}")
        
        projects = []
        # Start reading data rows after the header row
        for r_idx in range(header_idx + 1, len(rows_cells)):
            row = rows_cells[r_idx]
            
            if r_idx >= len(rows_for_detection):
                continue
                
            proj_name = ""
            if proj_col < len(row):
                proj_name = str(row[proj_col].get('formattedValue', '')).strip()
                
            # Clean project name (ignore header replicas or empty names)
            if not proj_name or proj_name.lower() in ['project name', 'name of project', 'total', 'grand total']:
                continue
                
            drive_url = ""
            display_text = ""
            hyperlink = ""
            
            if drive_col < len(row):
                cell = row[drive_col]
                display_text = cell.get('formattedValue', '').strip()
                hyperlink = get_cell_hyperlink(cell)
                
                # Use hyperlink if it exists, otherwise fall back to display text
                drive_url = hyperlink if hyperlink else display_text
                
            # Extract drive ID and check if it is a file or folder
            drive_id, is_file = extract_drive_info(drive_url)
            
            # Add debug logging in the requested format
            if proj_name:
                # Helper to print safely in console without Unicode crashes
                safe_display = str(display_text).encode('ascii', errors='ignore').decode('ascii')
                safe_hyperlink = str(hyperlink).encode('ascii', errors='ignore').decode('ascii')
                
                print("--------------------------------------------------")
                print(f"Display Text : {safe_display}")
                print(f"Hyperlink    : {safe_hyperlink if hyperlink else 'None'}")
                print(f"Drive ID     : {drive_id if drive_id else 'None'}")
                print(f"Is Folder    : {not is_file if drive_id else 'N/A'}")
                print("--------------------------------------------------")
                
                projects.append({
                    "name": proj_name,
                    "drive_url": drive_url,
                    "folder_id": drive_id if drive_id else "",  # keep key 'folder_id' for compatibility
                    "is_file": is_file,
                    "row_num": r_idx + 1
                })
                
        return projects
        
    except Exception as e:
        logger.error(f"Error reading package '{package_name}': {e}")
        raise e
