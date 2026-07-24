import subprocess
import sys
import os

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass # fallback for older python versions
        
    # Check if streamlit is installed
    try:
        import streamlit
    except ImportError:
        print("Error: Streamlit is not installed.")
        print("Please run: pip install -r requirements.txt")
        input("\nPress Enter to exit...")
        sys.exit(1)
        
    # Get absolute path of dashboard.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    dashboard_path = os.path.join(current_dir, "dashboard.py")
    
    if not os.path.exists(dashboard_path):
        print(f"Error: Could not find dashboard.py at '{dashboard_path}'")
        input("\nPress Enter to exit...")
        sys.exit(1)
        
    print("--------------------------------------------------")
    print("  Starting NHAI Tracking Sheet Dashboard...       ")
    print("  The application will open in your browser.     ")
    print("  To stop the application, press Ctrl+C here.     ")
    print("--------------------------------------------------")
    
    try:
        # Run streamlit command programmatically
        subprocess.run([sys.executable, "-m", "streamlit", "run", dashboard_path])
    except KeyboardInterrupt:
        print("\nDashboard stopped. Goodbye!")
