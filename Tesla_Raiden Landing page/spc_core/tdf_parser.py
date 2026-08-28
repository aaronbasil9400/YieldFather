"""Teradyne TDF parsing engine.

Extracted verbatim from SPC_DASHBOARD.py (Streamlit era) into an import-safe,
deterministic module. Bump PARSER_VERSION whenever parsing behavior changes;
the consolidator records it alongside each output database.
"""

import datetime as dt
import re
from pathlib import Path

# Bump on any change that alters produced rows (columns, regexes, DUT rules).
# v2: falls back to the consolidation ROOT folder name for UnitSN/RunAttempt
# when the tree has no <UnitSN>_<RunAttempt> ancestor level below the root.
PARSER_VERSION = "2"

FIXED_COLUMNS = [
    "Result", "Slot", "Subslot", "Instrument", "TestGrp2", "TestGrp1",
    "TestType", "TestNb", "Channel", "TypeofTest", "ExpVal", "LowLim",
    "Value", "HighLim", "Units", "PctDelta", "LpCnt",
]
N_FIXED = len(FIXED_COLUMNS)
NUMERIC_COLS = ["ExpVal", "LowLim", "Value", "HighLim", "PctDelta"]
DEFAULT_DUT_PARTNUMBERS = ["638-249-30", "627-001-30", "627-000-40"]

OUTPUT_COLUMNS = (
    ["SourceFile", "FolderBin", "RootFolder", "UnitSN", "RunAttempt",
     "TestStepFolder", "ProductCode", "FolderRev", "TestStep", "ATP",
     "RunTimestampFolder", "DataFileName", "FileNumber"]
    + ["TDFVersion", "Tester", "IGXLVersion", "IGXLBuild", "TestDateTime",
       "SystemType", "ProgramName", "TesterSystemSN"]
    + ["DUT_SN", "ModuleSN", "ModulePartNum", "ModuleRevDate", "ModuleCalState", "ModuleOptionName"]
    + FIXED_COLUMNS
    + ["ExpVal_num", "LowLim_num", "Value_num", "HighLim_num", "PctDelta_num"]
    + ["TestLabel", "TestParameters"]
)

ROOT_FOLDER_RE = re.compile(r"^(?P<sn>.+?)_(?P<run>\d+)$")
STEP_FOLDER_RE = re.compile(
    r"^(?P<product>[A-Za-z0-9]+)_(?P<rev>\d+)_(?P<phase>[A-Za-z]+)_(?P<stage>[A-Za-z]+)_"
    r"(?P<teststep>[A-Za-z0-9]+)_ATP-(?P<atp>[\d\-]+)$"
)
TIMESTAMP_FOLDER_RE = re.compile(r"^(?P<ts>\d{8}_\d{6})$")
SLOT_ROW_RE = re.compile(r"^\d+\.\d+\t")

HEADER_KEYS = {
    "TDF Version": "TDFVersion", "Tester": "Tester", "IG-XL VERSION": "IGXLVersion",
    "IG-XL BUILD": "IGXLBuild", "CURRENT TIME": "TestDateTime", "SYSTEM TYPE": "SystemType",
    "PROGRAM NAME": "ProgramName", "SYSTEM SERIAL NUMBER": "TesterSystemSN", "FileNumber": "FileNumber",
}


def parse_root_folder(name: str):
    m = ROOT_FOLDER_RE.match(name)
    return (m.group("sn"), m.group("run")) if m else (name, "")


def parse_step_folder(name: str):
    m = STEP_FOLDER_RE.match(name)
    return (m.group("product"), m.group("rev"), m.group("teststep"), m.group("atp")) if m else ("", "", name, "")


def parse_run_timestamp(name: str):
    m = TIMESTAMP_FOLDER_RE.match(name)
    if not m: return name, None
    ts_raw = m.group("ts")
    try:
        return ts_raw, dt.datetime.strptime(ts_raw, "%Y%m%d_%H%M%S").isoformat(sep=" ")
    except ValueError:
        return ts_raw, None


def find_ancestor_folders(tdf_path: Path, root: Path):
    parts = tdf_path.relative_to(root).parts[:-1]
    run_ts = parts[-1] if len(parts) >= 1 else ""
    step = parts[-2] if len(parts) >= 2 else ""
    rootf = parts[-3] if len(parts) >= 3 else ""
    binf = parts[-4] if len(parts) >= 4 else ""
    return binf, rootf, step, run_ts


def safe_float(s):
    if s is None or s == "": return None
    try: return float(s)
    except ValueError: return None


def parse_tdf_file(path: Path):
    header_meta = {v: "" for v in HEADER_KEYS.values()}
    board_cfg, rows = {}, []
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        section = "header"
        for raw_line in f:
            line = raw_line.rstrip("\r\n")
            if section == "header":
                if line.startswith("Board Configuration:"):
                    section = "boardcfg"
                    continue
                if ":" in line:
                    key, _, val = line.partition(":")
                    key = key.strip()
                    if key in HEADER_KEYS: header_meta[HEADER_KEYS[key]] = val.strip()
                continue
            if section == "boardcfg":
                if line.startswith("P/F\t"):
                    section = "data"
                    continue
                if SLOT_ROW_RE.match(line):
                    cols = line.split("\t")
                    slot_part, _, subslot_part = cols[0].partition(".")
                    board_cfg[(slot_part, subslot_part)] = {
                        "ModuleSN": cols[2].strip() if len(cols) > 2 else "",
                        "ModulePartNum": cols[4].strip() if len(cols) > 4 else "",
                        "ModuleRevDate": cols[3].strip() if len(cols) > 3 else "",
                        "ModuleCalState": cols[5].strip() if len(cols) > 5 else "",
                        "ModuleOptionName": cols[1].strip() if len(cols) > 1 else "",
                    }
                continue
            if section == "data":
                if not line or line.startswith("DIB\t"): continue
                parts_ = line.split("|", N_FIXED)
                if len(parts_) < N_FIXED + 1: continue
                fixed = parts_[:N_FIXED]
                test_label, _, test_params = parts_[N_FIXED].rpartition("|")
                row = dict(zip(FIXED_COLUMNS, fixed))
                row["TestLabel"], row["TestParameters"] = test_label, test_params
                rows.append(row)
    return header_meta, board_cfg, rows


def is_dut_partnum(partnum: str, dut_partnumbers) -> bool:
    partnum = (partnum or "").strip()
    if not partnum: return False
    return any(partnum == pn or partnum.startswith(pn) for pn in dut_partnumbers if pn.strip())


def iter_output_rows(tdf_path: Path, root: Path, dut_partnumbers):
    header_meta, board_cfg, data_rows = parse_tdf_file(tdf_path)
    binf, rootf, step, run_ts_folder = find_ancestor_folders(tdf_path, root)
    unit_source = rootf if rootf else root.name
    unit_sn, run_attempt = parse_root_folder(unit_source)
    product, folder_rev, test_step, atp = parse_step_folder(step)
    run_ts_raw, run_ts_iso = parse_run_timestamp(run_ts_folder)
    file_number = header_meta.get("FileNumber", "").strip() or "1"

    base_meta = {
        "SourceFile": str(tdf_path), "FolderBin": binf, "RootFolder": rootf, "UnitSN": unit_sn,
        "RunAttempt": run_attempt, "TestStepFolder": step, "ProductCode": product, "FolderRev": folder_rev,
        "TestStep": test_step, "ATP": atp, "RunTimestampFolder": run_ts_iso or run_ts_raw,
        "DataFileName": tdf_path.name, "FileNumber": file_number, "TDFVersion": header_meta.get("TDFVersion", ""),
        "Tester": header_meta.get("Tester", ""), "IGXLVersion": header_meta.get("IGXLVersion", ""),
        "IGXLBuild": header_meta.get("IGXLBuild", ""), "TestDateTime": header_meta.get("TestDateTime", "").strip(),
        "SystemType": header_meta.get("SystemType", ""), "ProgramName": header_meta.get("ProgramName", ""),
        "TesterSystemSN": header_meta.get("TesterSystemSN", ""),
    }
    empty_module = {"ModuleSN": "", "ModulePartNum": "", "ModuleRevDate": "", "ModuleCalState": "", "ModuleOptionName": ""}

    for row in data_rows:
        mod = board_cfg.get((row["Slot"].strip(), row["Subslot"].strip()), empty_module)
        out = dict(base_meta)
        out.update(mod)
        out["DUT_SN"] = mod["ModuleSN"] if is_dut_partnum(mod.get("ModulePartNum", ""), dut_partnumbers) else ""
        out.update(row)
        for c in NUMERIC_COLS: out[f"{c}_num"] = safe_float(row.get(c))
        yield out
