"""Excel Bulk Job Upload Service for JOBFLEX / NEXORA.

Handles:
1. Generating a clean, pre-styled Excel (.xlsx) job template with instructions and sample rows.
2. Parsing uploaded Excel workbooks into structured job listings with validation and error reporting.
"""
import io
import re
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

import data

TEMPLATE_COLUMNS = [
    ("Job Title *", "title", True, "Senior Python Engineer"),
    ("Industry", "industry", False, "Technology"),
    ("Location", "location", False, "Sydney, NSW"),
    ("Job Type", "type", False, "Full-time"),
    ("Work Mode", "mode", False, "Hybrid"),
    ("Experience Level", "experience", False, "3-5 years"),
    ("Salary Min (AUD)", "salary_min", False, "120000"),
    ("Salary Max (AUD)", "salary_max", False, "150000"),
    ("About Role / Description", "description", False, "Exciting opportunity to build cutting-edge cloud applications."),
    ("Responsibilities (comma-separated)", "responsibilities", False, "Architect microservices, Mentor junior engineers, Code reviews"),
    ("Requirements (comma-separated)", "requirements", False, "Python 3, Flask or Django, PostgreSQL, Cloud experience"),
    ("Benefits (comma-separated)", "benefits", False, "Flexible hours, Annual learning budget, Health allowance"),
    ("Skills / Tags (comma-separated)", "skills", False, "Python, Flask, SQL, API"),
]


def generate_job_template() -> io.BytesIO:
    """Generate an Excel job upload template (.xlsx) with sample data and styling."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Job Upload Template"

    # Header styling
    header_fill = PatternFill(start_color="0A1236", end_color="0A1236", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    sample_font = Font(name="Calibri", size=10, color="333333")
    sample_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0")
    )

    # Write headers
    headers = [col[0] for col in TEMPLATE_COLUMNS]
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Write 2 sample rows
    sample_rows = [
        [
            "Senior Python Engineer", "Technology", "Sydney, NSW", "Full-time", "Hybrid",
            "3-5 years", 120000, 150000,
            "Exciting opportunity to build cutting-edge cloud recruitment tools.",
            "Architect backend services, Lead technical design, Conduct code reviews",
            "5+ years Python experience, PostgreSQL, RESTful APIs, Git",
            "Flexible work arrangements, Health insurance, $2000 annual learning stipend",
            "Python, Flask, PostgreSQL, Docker"
        ],
        [
            "Product Designer (UI/UX)", "Design", "Melbourne, VIC", "Full-time", "Remote",
            "1-3 years", 85000, 105000,
            "Design delightful user journeys and intuitive interfaces for job seekers.",
            "Conduct user research, Create Figma prototypes, Collaborate with engineers",
            "Figma proficiency, Design systems, Portfolio of modern web apps",
            "Work from anywhere in Australia, Home office setup budget",
            "Figma, UI/UX, Design Systems, Prototyping"
        ]
    ]

    for row_data in sample_rows:
        ws.append(row_data)
        current_row = ws.max_row
        for col_idx in range(1, len(row_data) + 1):
            c = ws.cell(row=current_row, column=col_idx)
            c.font = sample_font
            c.fill = sample_fill
            c.border = thin_border
            if isinstance(row_data[col_idx - 1], (int, float)):
                c.alignment = Alignment(horizontal="right", vertical="center")
            else:
                c.alignment = Alignment(horizontal="left", vertical="center")

    # Set column widths
    for col_idx, (header, _, _, _) in enumerate(TEMPLATE_COLUMNS, start=1):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = max(len(header) + 4, 18)

    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 22
    ws.row_dimensions[3].height = 22

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def _clean_str(val):
    if val is None:
        return ""
    return str(val).strip()


def _clean_int(val, default=0):
    if val is None:
        return default
    try:
        # Remove commas, dollar signs, currency symbols
        cleaned = re.sub(r"[^\d.]", "", str(val).strip())
        if not cleaned:
            return default
        return int(float(cleaned))
    except (ValueError, TypeError):
        return default


def _split_items(val):
    if not val:
        return []
    if isinstance(val, list):
        return val
    parts = re.split(r"[,;\n]+", str(val))
    return [p.strip() for p in parts if p.strip()]


def parse_job_excel(file_stream, max_jobs=50) -> dict:
    """
    Parse an uploaded Excel workbook.
    Returns:
    {
        "ok": bool,
        "valid_jobs": list of job dicts,
        "errors": list of error messages,
        "total_rows": int
    }
    """
    try:
        wb = openpyxl.load_workbook(file_stream, data_only=True)
        ws = wb.active
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Invalid Excel file: {str(exc)}",
            "valid_jobs": [],
            "errors": [f"Could not read Excel file: {str(exc)}"],
            "total_rows": 0
        }

    rows = list(ws.iter_rows(values_only=True))
    if not rows or len(rows) < 2:
        return {
            "ok": False,
            "error": "The Excel file is empty or missing headers.",
            "valid_jobs": [],
            "errors": ["File contains no data rows."],
            "total_rows": 0
        }

    # Match header row
    header_row = [str(c or "").strip().lower() for c in rows[0]]
    header_map = {}
    for col_title, field_name, required, _ in TEMPLATE_COLUMNS:
        normalized_target = col_title.split("*")[0].strip().lower()
        for idx, h in enumerate(header_row):
            if normalized_target in h or field_name in h:
                header_map[field_name] = idx
                break

    if "title" not in header_map:
        return {
            "ok": False,
            "error": "Missing required header: 'Job Title'. Please use the official JOBFLEX template.",
            "valid_jobs": [],
            "errors": ["Could not locate 'Job Title' column."],
            "total_rows": len(rows) - 1
        }

    valid_jobs = []
    errors = []
    seen_titles = set()

    for row_idx, row in enumerate(rows[1:], start=2):
        if not any(row):
            continue  # skip completely blank lines

        if len(valid_jobs) >= max_jobs:
            errors.append(f"Row {row_idx}: Maximum upload limit of {max_jobs} jobs reached. Remaining rows skipped.")
            break

        def get_val(field):
            idx = header_map.get(field)
            if idx is not None and idx < len(row):
                return row[idx]
            return None

        title = _clean_str(get_val("title"))
        if not title:
            errors.append(f"Row {row_idx}: Missing Job Title. Row skipped.")
            continue

        # Duplicate title check within the same spreadsheet
        title_lower = title.lower()
        if title_lower in seen_titles:
            errors.append(f"Row {row_idx}: Duplicate job title '{title}' within this upload. Skipped.")
            continue
        seen_titles.add(title_lower)

        # Normalize industry
        raw_industry = _clean_str(get_val("industry"))
        industry = next((ind for ind in data.INDUSTRIES if ind.lower() == raw_industry.lower()), "Technology")

        # Normalize location
        raw_location = _clean_str(get_val("location"))
        location = next((loc for loc in data.LOCATIONS if raw_location.lower() in loc.lower()), raw_location or "Sydney, NSW")

        # Normalize job type
        raw_type = _clean_str(get_val("type"))
        job_type = next((t for t in data.JOB_TYPES if t.lower() == raw_type.lower()), "Full-time")

        # Normalize work mode
        raw_mode = _clean_str(get_val("mode"))
        work_mode = next((m for m in data.WORK_MODES if m.lower() == raw_mode.lower()), "Hybrid")

        # Normalize experience
        raw_exp = _clean_str(get_val("experience"))
        experience = next((e for e in data.EXPERIENCE_LEVELS if raw_exp.lower() in e.lower()), "3-5 years")

        # Salaries
        s_min = _clean_int(get_val("salary_min"), 70000)
        s_max = _clean_int(get_val("salary_max"), 100000)
        if s_max < s_min:
            s_min, s_max = s_max, s_min

        desc = _clean_str(get_val("description")) or f"Join our team as a {title}. Excellent growth opportunity in {location}."
        resps = _split_items(get_val("responsibilities")) or ["Deliver against primary job objectives", "Collaborate with cross-functional teams"]
        reqs = _split_items(get_val("requirements")) or [f"Experience level: {experience}", f"Expertise in {industry}"]
        benefits = _split_items(get_val("benefits")) or ["Competitive compensation", "Flexible working environment"]
        skills = _split_items(get_val("skills")) or [industry]

        valid_jobs.append({
            "row_number": row_idx,
            "title": title[:120],
            "industry": industry,
            "location": location,
            "type": job_type,
            "mode": work_mode,
            "experience": experience,
            "salary_min": s_min,
            "salary_max": s_max,
            "description": desc[:5000],
            "responsibilities": resps[:10],
            "requirements": reqs[:10],
            "benefits": benefits[:8],
            "skills": [s[:40] for s in skills[:8]],
        })

    return {
        "ok": True,
        "valid_jobs": valid_jobs,
        "errors": errors,
        "total_rows": len(rows) - 1,
        "parsed_count": len(valid_jobs),
    }
