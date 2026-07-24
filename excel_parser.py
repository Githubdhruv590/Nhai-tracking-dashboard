import io
import logging
import pandas as pd
import openpyxl

logger = logging.getLogger(__name__)

def parse_furniture_assets(excel_bytes: bytes) -> pd.DataFrame:
    """
    Parses the "Furniture Assets" worksheet from an Excel file in-memory.
    Intelligently detects:
    1. The worksheet name (handling slight variations like case differences, spaces, or containing keywords).
    2. The column positions for Road Section, Chainage From, and Chainage To independently.
    3. The header row position.
    
    Returns:
      pd.DataFrame: A DataFrame with columns ['road_section', 'chainage_from', 'chainage_to']
      
    Raises:
      ValueError: If worksheet or required columns are not found.
    """
    try:
        # Load the workbook structure to inspect sheet names
        xl = pd.ExcelFile(io.BytesIO(excel_bytes))
    except Exception as e:
        logger.error(f"Failed to read Excel workbook: {e}")
        raise ValueError(f"Invalid Excel file format: {e}")
        
    sheet_names = xl.sheet_names
    target_sheet = None
    
    # Heuristic 1: Exact matches (case-insensitive)
    for name in sheet_names:
        name_clean = name.strip().lower()
        if name_clean == "furniture assets" or name_clean == "furniture_assets":
            target_sheet = name
            break
            
    # Heuristic 2: Substring matches for 'furniture'
    if not target_sheet:
        for name in sheet_names:
            name_clean = name.strip().lower()
            if "furniture" in name_clean:
                target_sheet = name
                break
                
    # Heuristic 3: Substring matches for 'asset'
    if not target_sheet:
        for name in sheet_names:
            name_clean = name.strip().lower()
            if "asset" in name_clean:
                target_sheet = name
                break
                
    # Heuristic 4: If there is exactly one sheet, select it as the target
    if not target_sheet and len(sheet_names) == 1:
        target_sheet = sheet_names[0]
        logger.info(f"Fallback: Only one worksheet found, selecting '{target_sheet}'")
        
    if not target_sheet:
        raise ValueError(f"Could not find a 'Furniture Assets' worksheet. Available sheets: {sheet_names}")
        
    logger.info(f"Selected worksheet '{target_sheet}' from Excel file.")
    
    # Load raw sheet data (no headers assumed initially to find them dynamically)
    df_raw = xl.parse(target_sheet, header=None)
    
    if df_raw.empty:
        raise ValueError(f"Worksheet '{target_sheet}' is empty.")
        
    header_row_idx = 0
    road_col = -1
    from_col = -1
    to_col = -1
    
    # Keywords for column detection
    road_kws = ['road section', 'section', 'location', 'asset location', 'road_section', 'description', 'road']
    from_kws = ['chainage from', 'from chainage', 'from ch', 'start chainage', 'start ch', 'from_ch', 'from_chainage', 'from', 'ch from', 'ch_from']
    to_kws = ['chainage to', 'to chainage', 'to ch', 'end chainage', 'end ch', 'to_ch', 'to_chainage', 'to', 'ch to', 'ch_to']
    
    # Scan columns independently over the first 15 rows
    for col_idx in range(df_raw.shape[1]):
        col_cells = [str(df_raw.iloc[r_idx, col_idx]).strip().lower() for r_idx in range(min(15, len(df_raw)))]
        
        # Check Road Section
        if road_col == -1:
            if any(any(kw == cell or cell.startswith(kw) for kw in road_kws) for cell in col_cells):
                road_col = col_idx
                for r_idx, cell in enumerate(col_cells):
                    if any(kw == cell or cell.startswith(kw) for kw in road_kws):
                        header_row_idx = max(header_row_idx, r_idx)
                        break
                        
        # Check Chainage From
        if from_col == -1:
            if any(any(kw == cell or cell.endswith(kw) for kw in from_kws) for cell in col_cells):
                from_col = col_idx
                for r_idx, cell in enumerate(col_cells):
                    if any(kw == cell or cell.endswith(kw) for kw in from_kws):
                        header_row_idx = max(header_row_idx, r_idx)
                        break
                        
        # Check Chainage To
        if to_col == -1:
            if any(any(kw == cell or cell.endswith(kw) for kw in to_kws) for cell in col_cells):
                to_col = col_idx
                for r_idx, cell in enumerate(col_cells):
                    if any(kw == cell or cell.endswith(kw) for kw in to_kws):
                        header_row_idx = max(header_row_idx, r_idx)
                        break
                        
    # Fallback to column index scan if detection failed
    if road_col == -1:
        road_col = 0
    if from_col == -1:
        from_col = 1
    if to_col == -1:
        to_col = 2
        
    # Check if the detected column indices are within DataFrame bounds
    max_cols = df_raw.shape[1]
    if road_col >= max_cols or from_col >= max_cols or to_col >= max_cols:
        road_col = min(0, max_cols - 1)
        from_col = min(1, max_cols - 1)
        to_col = min(2, max_cols - 1)
        header_row_idx = 0
        
    logger.info(f"Using columns: Road Section={road_col}, Chainage From={from_col}, Chainage To={to_col}")
    
    # Extract data rows below the header
    data_df = df_raw.iloc[header_row_idx + 1:].copy()
    
    # Build clean output DataFrame
    clean_df = pd.DataFrame()
    clean_df['road_section'] = data_df.iloc[:, road_col].fillna("").astype(str).str.strip()
    clean_df['chainage_from'] = data_df.iloc[:, from_col]
    clean_df['chainage_to'] = data_df.iloc[:, to_col]
    
    # Remove rows where all columns are empty
    clean_df = clean_df[~((clean_df['road_section'] == "") & clean_df['chainage_from'].isna() & clean_df['chainage_to'].isna())]
    
    return clean_df
