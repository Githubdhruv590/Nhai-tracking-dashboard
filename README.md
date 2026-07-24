# NHAI Survey Dashboard

A FastAPI-based backend application for the **NHAI Survey Dashboard**. This application connects to Google Sheets and Google Drive using a Google Service Account, processes survey/project data, and exposes REST APIs consumed by the frontend.

---

## 📁 Project Structure

```text
Nhai-tracking-dashboard/
│
├── venv/                         # Python virtual environment (local)
├── .env                          # Environment variables
├── .env.example                  # Sample environment configuration
├── .gitignore                    # Git ignore rules
├── README.md                     # Project documentation
├── requirements.txt              # Python dependencies
│
├── credentials.json              # Google Service Account credentials (do not commit)
│
├── main.py                       # Application entry point
├── dashboard.py                  # Dashboard UI and application workflow
├── calculator.py                 # Road length calculation logic
├── config.py                     # Configuration and environment loading
├── drive_reader.py               # Google Drive integration
├── google_sheet_reader.py        # Google Sheets integration
├── excel_parser.py               # Excel file parsing utilities
├── utils.py                      # Common utility functions
├── diagnose.py                   # Diagnostic utilities
├── verify_drive_access.py        # Verify Google Drive access
│
└── logs/                         # Generated log files (if applicable)
```


---

# Prerequisites

- Python 3.11+
- Git
- Google Cloud Project
- Google Sheets API enabled
- Google Drive API enabled

---

# Google Cloud Setup

## 1. Create a Google Cloud Project

1. Open **Google Cloud Console**.
2. Create a new project.
3. Navigate to:

```
IAM & Admin → Service Accounts
```

4. Click **Create Service Account**.
5. Give it a suitable name.
6. Click **Done**.

---

## 2. Create Credentials

1. Open the created Service Account.
2. Go to

```
Keys → Add Key → Create New Key
```

3. Select **JSON**.
4. Download the credentials.

Rename the downloaded file to

```
credentials.json
```

Place it inside:

```
backend/
```

---

## 3. Enable APIs

Enable the following APIs from Google Cloud Console:

- Google Sheets API
- Google Drive API

---

## 4. Share Google Resources

Open your Google Spreadsheet and Google Drive folders.

Share them with the Service Account email as **Viewer**.

Example:

```
nhai-reader@project-id.iam.gserviceaccount.com
```

---

# Environment Variables

Create a file named

```
backend/.env
```

Example:

```env
SPREADSHEET_URL=https://docs.google.com/spreadsheets/d/<spreadsheet-id>/edit

GOOGLE_APPLICATION_CREDENTIALS=credentials.json
```

Add any additional environment variables required by your application.

---

# Installation

## Clone Repository

```bash
git clone <repository-url>
```

```bash
cd Nhai-survey-dashboard
```

---

## Create Virtual Environment

Move into backend.

```bash
cd backend
```

Create virtual environment.

```bash
python -m venv venv
```

Activate virtual environment.

### Windows PowerShell

```powershell
.\venv\Scripts\Activate.ps1
```

### Windows CMD

```cmd
venv\Scripts\activate.bat
```

### Linux / macOS

```bash
source venv/bin/activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Running the Backend

## Step 1

Go to the project root.

```bash
cd ..
```

Your folder should be

```
Nhai-survey-dashboard/

```

---

## Step 2

Start the FastAPI server.

```bash
python main.py
```

Server starts on

```
http://127.0.0.1:8000
```

---

# API Documentation

Swagger UI

```
http://127.0.0.1:8000/docs
```

ReDoc

```
http://127.0.0.1:8000/redoc
```

---

# Development Workflow

Activate virtual environment.

```powershell
.\venv\Scripts\Activate.ps1
```

Return to project root.

```bash
cd ..
```

Run server.

```bash
python main.py
```

---

# Installing New Packages

After activating the virtual environment,

```bash
pip install <package-name>
```

Update requirements.

```bash
pip freeze > backend/requirements.txt
```

---

# Common Issues

## Python is not recognized

Verify installation.

```bash
python --version
```

If Python is not found, ensure it is installed and added to the system PATH.

---

## Virtual Environment Activation Error

Run

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then

```powershell
.\venv\Scripts\Activate.ps1
```

---

## ModuleNotFoundError: No module named 'backend'

Ensure:

- You are running the command from the project root.
- The `backend` folder contains an empty `__init__.py` file.

Correct command:

```bash
uvicorn backend.main:app --reload
```

Do **not** run:

```bash
cd backend
uvicorn backend.main:app --reload
```

because Python will not find the `backend` package from inside the `backend` directory.

---

## Verify Installation

```bash
python --version
```

```bash
pip --version
```

```bash
uvicorn --version
```

---

# Stopping the Server

Press

```
CTRL + C
```

in the terminal.

---

# Technology Stack

- FastAPI
- Uvicorn
- Pandas
- Google Sheets API
- Google Drive API
- Python 3.11+

---

# License

This project is intended for internal NHAI survey dashboard usage.
