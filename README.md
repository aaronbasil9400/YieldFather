# Factory Analytics Hub

Factory Analytics Hub is a Streamlit-based analytics platform built for test engineering teams to make production data analysis faster, smarter, and easier to act on.

It combines **yield analysis**, **defect analysis**, **WIP tracking**, **log file consolidation**, and **SPC / process capability analysis** into one unified tool for manufacturing and test environments.

This repository is designed for engineering teams working with Teradyne UltraFLEX and UltraFLEX Plus production data, especially where fast visibility into yields, failure modes, and process stability is critical.

---

## What This Tool Does

Factory Analytics Hub is organized into two main modules:

1. **Yield Report & Defect Analysis**
2. **SPC Dashboard**

Together, they help engineers:

- Track production yield performance
- Identify top defect drivers and recurring failure modes
- Analyze daily and weekly yield trends
- Review station-level performance
- Investigate WIP and serial status
- Upload and analyze log files for SPC studies
- Calculate Cp, Cpk, sigma level, and out-of-spec behavior
- Consolidate large TDF log datasets into structured analysis-ready outputs

---

## Key Features

### Yield and Defect Analysis

The yield module provides a practical view of production performance using CSV data such as `rptTestDetail.csv`.

It supports:

- Production yield analysis
- First Pass Yield (FPY)
- Overall yield calculation
- Defect Pareto analysis
- Top failure mode identification
- Daily yield trends
- Weekly yield trends
- Station-level yield comparison
- WIP analysis by part number
- Serial number traceability
- Raw detail review and export

### SPC and Process Capability

The SPC module is designed for deeper engineering analysis of test parameter behavior.

It supports:

- Automated TDF log parsing
- Consolidation of test logs into CSV and SQLite
- Interactive filtering by test attributes
- SPC trend charts
- Histogram distribution analysis
- Cp and Cpk calculation
- Sigma-level estimation
- Upper and lower control limit visualization
- Upper and lower specification limit comparison
- Parameter-level debugging for process excursions

### Logging and Consolidation

The SPC workflow includes a parsing and consolidation engine for Teradyne-style TDF files. It extracts key metadata and converts raw files into structured datasets that are much easier to analyze in Streamlit.

---

## Why This Tool Exists

Test engineers often spend a lot of time doing the same repetitive work:

- opening log files manually
- copying data into Excel
- building pivot tables
- calculating yield percentages
- identifying defect patterns
- checking process spread and capability
- preparing summary views for management or customer discussions

Factory Analytics Hub reduces that burden by bringing these workflows into a single, interactive dashboard.

Instead of spending hours consolidating files, you can spend more time on root cause analysis and corrective action.

---

## Main Modules

### 1. Home Page

The home page acts as the application launcher.

It provides direct access to:

- **Yield Report and Defect Analysis**
- **SPC Dashboard**

This makes the tool easy to navigate for engineers who want a quick entry point into the analysis they need.

### 2. Yield Report and Defect Analysis

This module is intended for production yield visibility and failure trend analysis.

It includes:

- KPI summary cards
- Yield by test station
- First pass and overall yield tables
- Daily and weekly trends
- Pareto of top defects
- WIP analysis
- Raw filtered data export

Typical output views include:

- filtered record count
- unique part number count
- unique serial count
- raw record yield
- overall yield
- test station specific yield contribution

### 3. SPC Dashboard

This module is intended for process capability and parameter analysis.

It includes:

- consolidated TDF log import
- filterable data views
- control chart analysis
- histogram and distribution checks
- statistical capability computation
- unit, channel, tester, and test-step level filters

This is especially useful when engineers need to understand not only whether a unit passed or failed, but also how test parameters behave across time, channels, stations, or programs.

---

## Supported Data Inputs

### Yield Module Input

The yield dashboard expects a CSV file similar to:

```text
rptTestDetail.csv
```

Typical fields used by the dashboard include:

- PN
- Product
- ProcessGroup
- TestStation1
- TestDate1_dt
- SerialNumber
- TestResult
- Row

### SPC Module Input

The SPC dashboard is built for Teradyne TDF log structures and supports input from folders containing files such as:

```text
*_Data_*.tdf
```

During consolidation, the tool extracts data into:

- a consolidated CSV file
- a SQLite database

These outputs can then be used for filtering, charts, and capability analysis.

---

## Technology Stack

Factory Analytics Hub uses the following core technologies:

- **Python**
- **Streamlit**
- **Pandas**
- **NumPy**
- **Plotly**
- **SQLite**
- **Regular Expressions**
- **Custom theme utilities**

---

## Repository Structure

A typical project layout is shown below:

```text
Factory_Analytics_Hub/
├── Home.py
├── Yield_Report.py
├── spc_dashboard.py
├── theme_utils.py
├── assets/
│   └── logo.png
├── output_data/
│   └── results.db
├── rptTestDetail.csv
└── README.md
```

### File Overview

- **`Home.py`**: Main landing page and module launcher
- **`Yield_Report.py`**: Yield analysis and defect analytics dashboard
- **`spc_dashboard.py`**: SPC dashboard and TDF consolidation engine
- **`theme_utils.py`**: Visual theme and styling helpers
- **`assets/logo.png`**: Optional logo for branding
- **`output_data/results.db`**: SQLite database generated from consolidated logs

---

## How It Works

### Yield Workflow

1. User uploads a CSV or uses a local default file
2. Data is loaded and normalized
3. Filters are applied by PN, product, process, station, and date range
4. KPI cards are calculated
5. Yield charts, Pareto charts, trend charts, and WIP summaries are displayed
6. User can export filtered tables as CSV

### SPC Workflow

1. User selects a TDF root folder or a consolidated SQLite database
2. The parser scans the folder structure and extracts metadata
3. Test rows are converted into structured records
4. Data is stored in CSV and/or SQLite format
5. User filters by tester, channel, program, test step, DUT, unit, or result
6. SPC statistics and control charts are generated interactively

---

## Typical Use Cases

This tool is useful for:

- Daily production yield review
- Yield excursion investigation
- Top defect analysis
- Station performance comparison
- WIP visibility
- Serial traceability
- SPC parameter monitoring
- Cpk / Cp studies
- Escalation support for process issues
- Management review preparation
- Customer or partner discussion support

---

## Target Users

Factory Analytics Hub is intended for:

- Test Engineers
- Product Engineers
- Failure Analysis Engineers
- Manufacturing Engineers
- NPI Teams
- Yield Improvement Teams
- SPC / Process Engineering Teams
- Production Support Engineers

---

## Installation

### 1. Create a Virtual Environment

```bash
python -m venv .venv
```

### 2. Activate the Environment

#### Windows

```bash
.venv\Scripts\activate
```

#### Linux / Raspberry Pi

```bash
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

If you do not have a `requirements.txt` file yet, install the core dependencies manually:

```bash
pip install streamlit pandas numpy plotly
```

---

## Running the Application

Start the home page with:

```bash
streamlit run Home.py
```

If required, you can also run the individual pages directly depending on your project setup.

---

## Configuration Notes

### Yield Dashboard

The yield dashboard includes a `PART_MASTER` dictionary for mapping part numbers to product and process rules.

If your factory uses different part numbers, products, or process groups, update that dictionary to match your environment.

### SPC Dashboard

The SPC dashboard expects TDF data arranged in a folder structure that allows the parser to infer:

- root folder information
- step folder information
- timestamp folder information
- file-level metadata

If your naming convention changes, update the regex parsing logic in the SPC parser functions.

---

## Output Files

Depending on your workflow, the tool may generate or use the following outputs:

- filtered CSV exports
- station summary CSV
- consolidated CSV
- SQLite database
- interactive charts and tables within the Streamlit UI

---

## Example Strengths of This Tool

This project is valuable because it brings together multiple engineering needs in one place:

- yield reporting
- defect trending
- test station comparison
- SPC analysis
- log consolidation
- process capability review
- downloadable analysis outputs

That makes it much more than a simple reporting app. It is a practical engineering decision-support tool.

---

## Suggested Project Naming Ideas

If you want a more fun internal name for the repo or the app, here are some strong options:

- **Yieldfather**
- **The Bin Whisperer**
- **Bin There, Done That**
- **Captain CPK**
- **Failure Therapist**
- **Yieldzilla**
- **Sigma Slayer**
- **TestIQ**
- **YieldOps**
- **Factory Sherlock**

If you want something funny but still professional enough for management, **Yieldfather** or **The Bin Whisperer** are strong choices.

---

## Suggested Tagline Ideas

You can use one of these as a subtitle or banner line in your repo:

- **Turning raw test data into engineering decisions**
- **Yield, defect, and SPC analysis in one place**
- **Less manual digging. More real engineering insight.**
- **Built for test engineers, by test engineers**
- **From log files to action in minutes**

---

## Future Enhancements

Possible improvements for future versions:

- automated email / report export
- trend alerts for yield excursions
- defect clustering and correlation analysis
- programmable filter presets
- deeper integration with factory databases
- role-based dashboards
- Power BI or Excel export automation
- enhanced root cause visualization
- batch comparison between lots, shifts, or testers

---

## Author

Built for engineering teams who want faster yield analysis, better visibility into defects, and more efficient SPC investigation.

Designed to reduce manual work and improve decision speed on the factory floor.

---

## License

Add your preferred license here before publishing the repository.
