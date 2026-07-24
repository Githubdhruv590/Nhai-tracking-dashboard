import re
import logging
import pandas as pd
from utils import parse_chainage

logger = logging.getLogger(__name__)

def classify_and_calculate_lengths(df: pd.DataFrame) -> dict:
    """
    Classifies each row in the DataFrame based on its 'road_section' and
    calculates the absolute difference between 'chainage_to' and 'chainage_from'.
    
    Road Section Rules:
    1. Main Carriage Way (MCW): LHS and RHS. Matches if section contains "main carriage way",
       "main carriageway", or "mcw".
    2. Service Road: Matches if section contains "service road", or codes SRL1-5, SRR1-5.
    3. Intersecting Road: Matches if section contains "intersecting", "intersection", or
       codes IRL1-3, IRR1-3, or intersection codes like I1, I2, etc.
       
    Returns a dictionary of totals. If a section is not found in the sheet,
    its value is set to None (which displays as N/A).
    """
    mcw_lengths = []
    service_lengths = []
    intersecting_lengths = []
    
    for idx, row in df.iterrows():
        section = str(row['road_section']).strip().lower()
        if not section:
            continue
            
        # Clean section string for simple substring matching
        # Remove spaces, hyphens, and underscores
        clean_sec = section.replace(" ", "").replace("-", "").replace("_", "")
        
        # Try to parse chainages
        try:
            ch_from = parse_chainage(row['chainage_from'])
            ch_to = parse_chainage(row['chainage_to'])
            length = abs(ch_to - ch_from)
        except Exception as e:
            # Silently ignore rows with invalid or missing chainages
            # as requested: "Skip corrupted files/rows instead of crashing"
            continue
            
        # Categorization logic
        # 1. Main Carriage Way (MCW)
        if "maincarriageway" in clean_sec or "mcw" in clean_sec:
            mcw_lengths.append(length)
            
        # 2. Service Road (SRL1-5, SRR1-5, or service road)
        elif (
            "serviceroad" in clean_sec or 
            re.search(r'\bsr[lr][1-5]\b', section) or 
            re.search(r'sr[lr][1-5]', clean_sec)
        ):
            service_lengths.append(length)
            
        # 3. Intersecting Road / Intersections (IRL1-3, IRR1-3, I1, I2... or intersecting/intersection)
        elif (
            "intersecting" in clean_sec or 
            "intersection" in clean_sec or 
            re.search(r'\bir[lr][1-3]\b', section) or 
            re.search(r'ir[lr][1-3]', clean_sec) or 
            re.search(r'\bi\d+\b', section) or 
            re.search(r'^i\d+', clean_sec)
        ):
            intersecting_lengths.append(length)
            
    # Calculate sums, returning None if no elements matched (to represent N/A)
    return {
        'mcw_length': sum(mcw_lengths) if mcw_lengths else None,
        'service_road_length': sum(service_lengths) if service_lengths else None,
        'intersecting_road_length': sum(intersecting_lengths) if intersecting_lengths else None
    }
