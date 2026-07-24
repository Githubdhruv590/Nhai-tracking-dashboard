import streamlit as st
import pandas as pd
import os
import config
from google_sheet_reader import get_google_services, read_package_projects
from drive_reader import get_excel_from_folder
from excel_parser import parse_furniture_assets
from calculator import classify_and_calculate_lengths
import utils

# Set page configuration
st.set_page_config(
    page_title="NHAI Asset Tracking Dashboard",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium styling
st.markdown("""
<style>
    /* Main container styling */
    .main {
        background-color: #F8FAFC;
    }
    
    /* Header typography */
    h1 {
        color: #1E3A8A;
        font-family: 'Outfit', 'Inter', sans-serif;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    /* Subtitle styling */
    .subtitle {
        color: #64748B;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* Metric card styling */
    div[data-testid="metric-container"] {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        padding: 20px 24px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        border-left: 6px solid #2563EB;
        transition: transform 0.2s ease;
    }
    
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
    }
    
    div[data-testid="stMetricValue"] {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
    }
    
    div[data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748B;
    }
    
    /* Sidebar header */
    .sidebar-header {
        font-size: 1.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 1rem;
    }
    
    /* Success, Warning, Info badges */
    .status-success {
        color: #16A34A;
        font-weight: bold;
    }
    
    .status-warning {
        color: #D97706;
        font-weight: bold;
    }
    
    .status-error {
        color: #DC2626;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to safely sum lengths (ignoring None values)
def sum_lengths(values):
    valid_vals = [v for v in values if v is not None]
    return sum(valid_vals) if valid_vals else None

# Helper to format numbers or return N/A
def format_length(val):
    return f"{val:,.2f}" if val is not None else "N/A"

@st.cache_data(show_spinner=False)
def load_and_process_all_data():
    """
    Fetches projects from Google Sheets and parses Excel files from Drive.
    Stores the processed results in memory.
    """
    utils.reset_retry_count()
    creds_path = config.get_service_account_path()
    spreadsheet_id = config.get_spreadsheet_id()
    
    if not os.path.exists(creds_path):
        raise FileNotFoundError(f"Google Service Account key file is missing at: '{creds_path}'")
        
    if not spreadsheet_id or "your-spreadsheet-id-here" in spreadsheet_id:
        raise ValueError("Spreadsheet URL is not configured. Please paste your Google Spreadsheet link in the .env file.")
        
    # Authenticate
    sheets_service, drive_service = get_google_services(creds_path)
    
    packages = ["Package 1", "Package 2", "Package 3", "Package 4", "Package 5"]
    project_lists = {}
    total_projects = 0
    
    # Step 1: Read all sheets first
    for pkg in packages:
        try:
            projects = read_package_projects(sheets_service, spreadsheet_id, pkg)
            project_lists[pkg] = projects
            total_projects += len(projects)
        except Exception as e:
            st.error(f"Error loading {pkg} from Spreadsheet: {e}")
            project_lists[pkg] = []
            
    if total_projects == 0:
        raise ValueError("No projects found in sheets Package 1 to Package 5.")
        
    # Step 2: Download & process each project's Excel
    data = {}
    processed_count = 0
    
    # Progress UI
    progress_container = st.empty()
    status_container = st.empty()
    
    for pkg in packages:
        data[pkg] = []
        projects = project_lists[pkg]
        
        for proj in projects:
            proj_name = proj["name"]
            folder_id = proj["folder_id"]
            drive_url = proj["drive_url"]
            
            # Update progress bar
            percent_complete = processed_count / total_projects
            progress_container.progress(percent_complete)
            status_container.text(f"Processing {pkg} | Project: {proj_name} ({processed_count + 1}/{total_projects})")
            
            proj_data = {
                "name": proj_name,
                "drive_url": drive_url,
                "mcw_length": None,
                "service_road_length": None,
                "intersecting_road_length": None,
                "status": "Success",
                "error_detail": None
            }
            
            try:
                # Get Excel content
                excel_bytes, file_name = get_excel_from_folder(
                    drive_service, 
                    folder_id, 
                    is_file=proj.get("is_file", False)
                )
                # Parse workbook
                df = parse_furniture_assets(excel_bytes)
                # Calculate lengths
                lengths = classify_and_calculate_lengths(df)
                
                proj_data["mcw_length"] = lengths["mcw_length"]
                proj_data["service_road_length"] = lengths["service_road_length"]
                proj_data["intersecting_road_length"] = lengths["intersecting_road_length"]
                
                # Check if all lengths are None (sheet exists but has no matching asset rows)
                if lengths["mcw_length"] is None and lengths["service_road_length"] is None and lengths["intersecting_road_length"] is None:
                    proj_data["status"] = "Warning"
                    proj_data["error_detail"] = "Worksheet exists but contains no matching asset rows"
                    
            except FileNotFoundError as e:
                proj_data["status"] = "Error"
                proj_data["error_detail"] = str(e)
            except ValueError as e:
                proj_data["status"] = "Error"
                err_msg = str(e)
                if "Furniture Assets" in err_msg:
                    proj_data["error_detail"] = "Worksheet 'Furniture Assets' missing"
                else:
                    proj_data["error_detail"] = err_msg
            except Exception as e:
                proj_data["status"] = "Error"
                # Display the complete Google API error details (status code & message)
                proj_data["error_detail"] = str(e)
            
            data[pkg].append(proj_data)
            processed_count += 1
            
    # Complete
    progress_container.empty()
    status_container.empty()
    
    # Calculate summary metrics
    success_count = 0
    failed_count = 0
    for p_pkg in packages:
        for proj in data[p_pkg]:
            if proj["status"] == "Error":
                failed_count += 1
            else:
                success_count += 1
                
    data["_summary"] = {
        "total": total_projects,
        "success": success_count,
        "failed": failed_count,
        "retried": utils.get_retry_count()
    }
    
    return data

# --- SIDEBAR CONFIGURATION ---
st.sidebar.markdown('<div class="sidebar-header">🛠️ Configuration & Status</div>', unsafe_allow_html=True)

# Service Account Check
creds_path = config.get_service_account_path()
has_creds = os.path.exists(creds_path)
if has_creds:
    st.sidebar.success("✅ service_account.json loaded")
else:
    st.sidebar.error("❌ service_account.json missing")
    st.sidebar.info("Place `service_account.json` in the project root directory.")

# Spreadsheet ID Check
spreadsheet_id = config.get_spreadsheet_id()
has_sheet_url = bool(spreadsheet_id) and "your-spreadsheet-id-here" not in spreadsheet_id
if has_sheet_url:
    st.sidebar.success("✅ SPREADSHEET_URL configured")
else:
    st.sidebar.error("❌ SPREADSHEET_URL missing")
    st.sidebar.info("Paste your spreadsheet link inside the `.env` file.")

st.sidebar.divider()

# Force Reload Button
if st.sidebar.button("🔄 Force Reload Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.caption("NHAI Asset Tracking Dashboard v1.0.0")

# --- MAIN DASHBOARD INTERFACE ---
st.markdown("<h1>🛣️ NHAI Tracking Sheet Dashboard</h1>", unsafe_allow_html=True)
st.markdown('<div class="subtitle">Local Python dashboard to calculate and track furniture asset lengths for MCW, Service Roads, and Intersections.</div>', unsafe_allow_html=True)

if not has_creds or not has_sheet_url:
    st.warning("⚠️ Setup required: Please check the sidebar status and complete the configuration in the project folder before proceeding.")
    st.markdown("""
    ### Setup Steps:
    1. **Place your Service Account credentials file** in the project directory and name it `service_account.json`.
    2. **Open the `.env` file** and replace the `SPREADSHEET_URL` value with your actual Google Spreadsheet URL.
    3. Ensure the Service Account email address is **invited/shared** (Viewer access) to:
       - The Google Spreadsheet
       - The Google Drive folders containing the project reports
    4. Click the **Force Reload Data** button in the sidebar once setup is complete.
    """)
else:
    # Initialize/Fetch Data
    try:
        with st.spinner("Fetching and processing data from Google Sheets & Drive folders..."):
            processed_data = load_and_process_all_data()
            
        if processed_data:
            # Display summary in sidebar if available
            summary = processed_data.get("_summary")
            if summary:
                with st.sidebar:
                    st.markdown("---")
                    st.markdown("### 📊 Processing Summary")
                    st.write(f"**Total Projects:** {summary['total']}")
                    st.write(f"**Successful:** {summary['success']}")
                    st.write(f"**Failed:** {summary['failed']}")
                    st.write(f"**Retries Attempted:** {summary['retried']}")
            
            # Package Selector
            st.write("---")
            packages = [k for k in processed_data.keys() if not k.startswith("_")]
            selected_pkg = st.selectbox("📂 Select Package", packages, index=0)
            
            # Get projects for the selected package
            pkg_projects = processed_data[selected_pkg]
            
            if not pkg_projects:
                st.warning(f"No projects found in '{selected_pkg}'")
            else:
                # Calculate package-wide totals
                total_mcw = sum_lengths([p["mcw_length"] for p in pkg_projects])
                total_sr = sum_lengths([p["service_road_length"] for p in pkg_projects])
                total_ir = sum_lengths([p["intersecting_road_length"] for p in pkg_projects])
                
                # Display Summary Cards
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(
                        label="Total MCW Length (m)",
                        value=format_length(total_mcw)
                    )
                with col2:
                    st.metric(
                        label="Total Service Road Length (m)",
                        value=format_length(total_sr)
                    )
                with col3:
                    st.metric(
                        label="Total Intersecting Road Length (m)",
                        value=format_length(total_ir)
                    )
                
                st.write("")
                st.write("")
                st.markdown(f"### Projects in {selected_pkg}")
                
                # Format project rows for DataFrame
                display_rows = []
                for i, p in enumerate(pkg_projects, start=1):
                    mcw = format_length(p["mcw_length"])
                    sr = format_length(p["service_road_length"])
                    ir = format_length(p["intersecting_road_length"])
                    
                    status = p["status"]
                    if status == "Success":
                        status_display = "🟢 Success"
                    elif status == "Warning":
                        status_display = f"🟡 Warning: {p['error_detail']}"
                    else:
                        status_display = f"🔴 Error: {p['error_detail']}"
                        
                    display_rows.append({
                        "S.No.": i,
                        "Project Name": p["name"],
                        "MCW Length (m)": mcw,
                        "Service Road Length (m)": sr,
                        "Intersecting Road Length (m)": ir,
                        "Processing Status": status_display,
                        "Drive Folder Link": p["drive_url"]
                    })
                    
                display_df = pd.DataFrame(display_rows)
                
                # Render projects table with link config
                st.dataframe(
                    display_df,
                    column_config={
                        "S.No.": st.column_config.NumberColumn("S.No.", format="%d"),
                        "Drive Folder Link": st.column_config.LinkColumn("Drive Folder", display_text="Open Google Drive Link")
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
    except Exception as e:
        st.error(f"Error running application: {e}")
        st.info("If you just updated your `.env` or placed the credentials, try clicking 'Force Reload Data' in the sidebar.")
