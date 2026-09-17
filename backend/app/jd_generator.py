"""Job Description (JD) generator — produces professional PDF and DOCX documents
from the real job posting data stored in the database."""

import io
import os
import re
from datetime import datetime


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NAVY = (15, 42, 92)
TEAL = (15, 118, 110)
BLUE = (37, 99, 235)
LIGHT_GRAY = (241, 245, 249)
DARK_TEXT = (30, 41, 59)
MEDIUM_TEXT = (71, 85, 105)

SECTION_KEYWORDS = {
    "responsibilities": "Responsibilities",
    "key responsibilities": "Responsibilities",
    "about the role": "Job Summary",
    "role overview": "Job Summary",
    "role description": "Job Summary",
    "job overview": "Job Summary",
    "summary": "Job Summary",
    "description": "Job Summary",
    "requirements": "Required Qualifications",
    "required qualifications": "Required Qualifications",
    "qualifications": "Required Qualifications",
    "minimum qualifications": "Required Qualifications",
    "education": "Education Requirements",
    "education requirements": "Education Requirements",
    "experience": "Experience Requirements",
    "experience requirements": "Experience Requirements",
    "required experience": "Experience Requirements",
    "preferred": "Preferred Qualifications",
    "nice to have": "Preferred Qualifications",
    "bonus qualifications": "Preferred Qualifications",
    "skills": "Required Skills & Technologies",
    "required skills": "Required Skills & Technologies",
    "technical skills": "Required Skills & Technologies",
    "tech stack": "Required Skills & Technologies",
    "technologies": "Required Skills & Technologies",
    "perks": "Benefits & Perks",
    "benefits": "Benefits & Perks",
    "compensation": "Compensation",
    "salary": "Compensation",
    "what we offer": "Benefits & Perks",
    "about us": "About MuraAI",
    "about the company": "About MuraAI",
    "company overview": "About MuraAI",
    "about muraai": "About MuraAI",
    "how to apply": "How to Apply",
    "application process": "How to Apply",
}

DEFAULT_SECTIONS = [
    ("Job Summary", None),
    ("Responsibilities", None),
    ("Required Qualifications", None),
    ("Preferred Qualifications", None),
    ("Required Skills & Technologies", None),
    ("Experience Requirements", None),
    ("Education Requirements", None),
    ("Benefits & Perks", None),
]


def _safe(text):
    """Strip characters unsupported by fpdf's built-in fonts."""
    if text is None:
        return ""
    return "".join(ch if ord(ch) < 256 else "-" for ch in str(text))


def _esc(text):
    """Escape ampersand for python-docx XML."""
    if text is None:
        return ""
    return str(text).replace("&", "&amp;")


def _find_logo_path():
    """Look for a MuraAI logo image in the static assets directory."""
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "static", "assets", "logo.png"),
        os.path.join(os.path.dirname(__file__), "..", "static", "assets", "muraai-logo.png"),
        os.path.join(os.path.dirname(__file__), "..", "static", "logo.png"),
        os.path.join(os.path.dirname(__file__), "..", "static", "assets", "logo.jpg"),
        os.path.join(os.path.dirname(__file__), "..", "static", "assets", "muraai-logo.jpg"),
        os.path.join(os.path.dirname(__file__), "..", "static", "logo.jpg"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def _parse_description(description, skills):
    """Parse the free-form job description into structured sections.

    Returns a list of (heading, content_string) tuples.
    If the description contains identifiable section headings they are used;
    otherwise the entire text is treated as the job summary.
    """
    if not description and not skills:
        return []

    lines = (description or "").strip().split("\n")
    sections = []
    current_heading = None
    current_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            current_lines.append("")
            continue

        lower = stripped.lower().rstrip(":")
        # Detect markdown-style heading
        if stripped.startswith("#") or (
            len(stripped) < 80
            and stripped.endswith(":")
            and not stripped.startswith("-")
            and not stripped.startswith("*")
        ):
            heading_text = stripped.lstrip("#").strip().rstrip(":")
            key = heading_text.lower()
            matched_heading = SECTION_KEYWORDS.get(key)
            if not matched_heading:
                for kw, mapped in SECTION_KEYWORDS.items():
                    if kw in key:
                        matched_heading = mapped
                        break
            if matched_heading:
                if current_lines:
                    sections.append((current_heading or "Job Summary", "\n".join(current_lines).strip()))
                current_heading = matched_heading
                current_lines = []
                continue

        current_lines.append(stripped)

    if current_lines:
        sections.append((current_heading or "Job Summary", "\n".join(current_lines).strip()))

    # Append skills section from the skills JSON field
    if skills:
        skills_text = ", ".join(skills) if isinstance(skills, list) else str(skills)
        sections.append(("Required Skills & Technologies", skills_text))

    # If no sections were parsed, treat the whole description as summary
    if not sections and description:
        sections = [("Job Summary", description.strip())]

    # Merge duplicate headings
    merged = {}
    for heading, content in sections:
        if heading in merged:
            merged[heading] += "\n\n" + content
        else:
            merged[heading] = content

    return [(h, merged[h]) for h in merged]


def _clean_section_content(content):
    """Remove the section heading from the start of content if duplicated."""
    return content.strip()


# ===========================================================================
# PDF Generation
# ===========================================================================
def generate_jd_pdf(job) -> bytes:
    """Generate a professional PDF job description.

    Parameters
    ----------
    job : models.Job (or dict-like)
        The job posting model instance.

    Returns
    -------
    bytes
        The raw PDF file content.
    """
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=30)
    pdf.set_margins(20, 15, 20)
    pdf.add_page()

    # --- Logo / Brand header ---
    logo_path = _find_logo_path()
    if logo_path:
        try:
            fmt = "PNG" if logo_path.lower().endswith(".png") else "JPG"
            pdf.image(logo_path, x=150, y=12, w=40, h=0, type=fmt)
        except Exception:
            logo_path = None

    if not logo_path:
        # Draw a professional text-based MuraAI logo with accent mark
        pdf.set_fill_color(*NAVY)
        pdf.rect(150, 13, 6, 12, "F")
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(*NAVY)
        pdf.set_xy(158, 13)
        pdf.cell(32, 12, _safe("MuraAI"))
        # Accent underline
        pdf.set_fill_color(*TEAL)
        pdf.rect(158, 25.5, 32, 1.2, "F")

    # --- Document title ---
    pdf.set_y(32)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*TEAL)
    pdf.cell(0, 7, _safe("JOB DESCRIPTION"), ln=1)
    pdf.ln(1)

    # --- Job title ---
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*NAVY)
    pdf.multi_cell(0, 10, _safe(job.title or "Position"))
    pdf.ln(1)

    # --- Metadata table ---
    meta_items = [
        ("Job ID", job.id),
        ("Department", job.dept),
        ("Category", job.category),
        ("Location", job.location),
        ("Employment Type", "Full-Time"),
        ("Experience", job.exp),
        ("Salary Range", job.salary),
        ("Referral Bonus", f"INR {job.bonus:,}" if job.bonus else ""),
        ("Status", job.status),
        ("Posted", job.posted.strftime("%B %d, %Y") if job.posted else ""),
    ]

    valid_meta = [(k, v) for k, v in meta_items if v and str(v).strip()]

    if valid_meta:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(*LIGHT_GRAY)
        col1_w = 42
        col2_w = 140
        row_h = 7

        for i, (label, value) in enumerate(valid_meta):
            if pdf.get_y() > 258:
                pdf.add_page()
            y = pdf.get_y()
            # Zebra striping
            if i % 2 == 0:
                pdf.set_fill_color(246, 248, 252)
                pdf.rect(20, y, col1_w + col2_w, row_h, "F")
            pdf.set_text_color(*MEDIUM_TEXT)
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_xy(22, y + 1.2)
            pdf.cell(col1_w, row_h - 2, _safe(label))
            pdf.set_text_color(*DARK_TEXT)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_xy(22 + col1_w, y + 1.2)
            pdf.cell(col2_w, row_h - 2, _safe(str(value))[:80])
            pdf.set_y(y + row_h)

    pdf.ln(4)

    # --- Accent line ---
    pdf.set_draw_color(*TEAL)
    pdf.set_line_width(0.8)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(6)

    # --- Sections ---
    sections = _parse_description(
        job.description or "",
        job.skills if isinstance(job.skills, list) else [],
    )

    # Ensure standard section order
    section_order = [
        "Job Summary", "About MuraAI", "Responsibilities",
        "Required Qualifications", "Preferred Qualifications",
        "Required Skills & Technologies", "Experience Requirements",
        "Education Requirements", "Benefits & Perks", "Compensation",
        "How to Apply",
    ]
    ordered = []
    seen = set()
    for heading in section_order:
        for h, c in sections:
            if h == heading:
                ordered.append((h, c))
                seen.add(h)
                break
    for h, c in sections:
        if h not in seen:
            ordered.append((h, c))

    if not ordered:
        ordered = [("Job Summary", job.description or "No description available.")]

    for heading, content in ordered:
        if not content or not content.strip():
            continue

        # Check if we need a page break (need at least 40mm for a section header + some content)
        if pdf.get_y() > 250:
            pdf.add_page()

        # Section heading
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*NAVY)
        pdf.cell(0, 9, _safe(heading), ln=1)

        # Accent underline below heading
        pdf.set_fill_color(*TEAL)
        pdf.rect(20, pdf.get_y() - 1, 30, 0.6, "F")
        pdf.ln(4)

        # Section content
        content = _clean_section_content(content)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*DARK_TEXT)

        # Detect if content looks like a list
        lines = content.split("\n")
        is_list = sum(1 for l in lines if l.strip().startswith(("-", "*", "•", "1", "2", "3", "4", "5", "6", "7", "8", "9"))) > len(lines) * 0.3

        if is_list:
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    pdf.ln(2)
                    continue
                # Clean up list markers
                clean = re.sub(r"^[\-\*•]\s*", "", stripped)
                clean = re.sub(r"^\d+[\.\)]\s*", "", clean)
                if not clean:
                    continue

                if pdf.get_y() > 258:
                    pdf.add_page()

                # Bullet character
                x_start = pdf.get_x()
                pdf.set_font("Helvetica", "B", 7)
                pdf.set_text_color(*TEAL)
                pdf.set_xy(x_start + 2, pdf.get_y() + 0.8)
                pdf.cell(4, 4, "-")

                pdf.set_font("Helvetica", "", 9.5)
                pdf.set_text_color(*DARK_TEXT)
                pdf.set_xy(x_start + 8, pdf.get_y() - 0.8)
                pdf.multi_cell(155, 5, _safe(clean))
                pdf.ln(0.5)
        else:
            # Regular paragraph text
            pdf.multi_cell(0, 5.5, _safe(content))
            pdf.ln(2)

    # --- Footer / Page numbering (second pass) ---
    total_pages = pdf.page
    page_left = 20
    page_right = 190
    page_width = page_right - page_left

    for i in range(1, total_pages + 1):
        pdf.page = i

        # Horizontal separator line
        pdf.set_y(-15)
        pdf.set_draw_color(200, 210, 225)
        pdf.set_line_width(0.3)
        pdf.line(page_left, pdf.get_y(), page_right, pdf.get_y())

        # Footer text row — positioned explicitly to prevent overlap
        pdf.set_y(-13)
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(*MEDIUM_TEXT)

        # Page number only — right-aligned
        pdf.set_xy(page_left, pdf.get_y())
        pdf.cell(page_width, 5, _safe(f"Page {i} of {total_pages}"), align="R")

    return bytes(pdf.output())


# ===========================================================================
# DOCX Generation
# ===========================================================================
def generate_jd_docx(job) -> bytes:
    """Generate a professional Word (.docx) job description.

    Parameters
    ----------
    job : models.Job (or dict-like)
        The job posting model instance.

    Returns
    -------
    bytes
        The raw DOCX file content.
    """
    from docx import Document
    from docx.shared import Pt, Inches, Cm, RGBColor, Emu
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.section import WD_ORIENT
    from docx.oxml.ns import qn

    doc = Document()

    # --- Page margins ---
    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    navy_rgb = RGBColor(*NAVY)
    teal_rgb = RGBColor(*TEAL)
    dark_rgb = RGBColor(*DARK_TEXT)
    medium_rgb = RGBColor(*MEDIUM_TEXT)

    # --- Style setup ---
    styles = doc.styles
    normal_style = styles["Normal"]
    normal_style.font.name = "Calibri"
    normal_style.font.size = Pt(10.5)
    normal_style.font.color.rgb = dark_rgb

    for level in range(1, 4):
        style_name = f"Heading {level}"
        if style_name in styles:
            h = styles[style_name]
            h.font.name = "Calibri"
            h.font.color.rgb = navy_rgb
            if level == 1:
                h.font.size = Pt(20)
            elif level == 2:
                h.font.size = Pt(13)
            else:
                h.font.size = Pt(11)

    # --- Header: Logo area + Title ---
    header_table = doc.add_table(rows=1, cols=2)
    header_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    # Remove table borders
    for row in header_table.rows:
        for cell in row.cells:
            tc = cell._element
            tcPr = tc.get_or_add_tcPr()
            tcBorders = tcPr.makeelement(qn("w:tcBorders"), {})
            for border_name in ["top", "left", "bottom", "right"]:
                border_elem = tcBorders.makeelement(
                    qn(f"w:{border_name}"),
                    {
                        qn("w:val"): "none",
                        qn("w:sz"): "0",
                        qn("w:space"): "0",
                        qn("w:color"): "auto",
                    },
                )
                tcBorders.append(border_elem)
            tcPr.append(tcBorders)

    # Left cell: Document title + Job title
    title_cell = header_table.cell(0, 0)
    title_cell.width = Inches(4.5)
    title_para = title_cell.paragraphs[0]
    doc_type_run = title_para.add_run("JOB DESCRIPTION\n")
    doc_type_run.font.size = Pt(11)
    doc_type_run.font.color.rgb = teal_rgb
    doc_type_run.bold = True
    title_run = title_para.add_run(job.title or "Position")
    title_run.font.size = Pt(22)
    title_run.font.color.rgb = navy_rgb
    title_run.bold = True

    # Right cell: Logo
    logo_cell = header_table.cell(0, 1)
    logo_cell.width = Inches(1.5)
    logo_para = logo_cell.paragraphs[0]
    logo_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    logo_path = _find_logo_path()
    if logo_path:
        try:
            logo_para.add_run().add_picture(logo_path, width=Inches(1.2))
        except Exception:
            logo_path = None

    if not logo_path:
        logo_run = logo_para.add_run("MuraAI")
        logo_run.font.size = Pt(18)
        logo_run.font.color.rgb = navy_rgb
        logo_run.bold = True

    # Subtitle line
    subtitle = doc.add_paragraph()
    sub_run = subtitle.add_run("Employee Referral Platform")
    sub_run.font.size = Pt(11)
    sub_run.font.color.rgb = teal_rgb
    sub_run.italic = True
    subtitle.space_after = Pt(4)

    # --- Accent line (horizontal rule) ---
    hr_para = doc.add_paragraph()
    hr_para.space_before = Pt(2)
    hr_para.space_after = Pt(8)
    pPr = hr_para._element.get_or_add_pPr()
    pBdr = pPr.makeelement(qn("w:pBdr"), {})
    bottom = pBdr.makeelement(
        qn("w:bottom"),
        {
            qn("w:val"): "single",
            qn("w:sz"): "6",
            qn("w:space"): "1",
            qn("w:color"): "0F766E",
        },
    )
    pBdr.append(bottom)
    pPr.append(pBdr)

    # --- Metadata table ---
    meta_items = [
        ("Job ID", job.id),
        ("Department", job.dept),
        ("Category", job.category),
        ("Location", job.location),
        ("Employment Type", "Full-Time"),
        ("Experience", job.exp),
        ("Salary Range", job.salary),
        ("Referral Bonus", f"INR {job.bonus:,}" if job.bonus else ""),
        ("Status", job.status),
        ("Posted", job.posted.strftime("%B %d, %Y") if job.posted else ""),
    ]
    valid_meta = [(k, v) for k, v in meta_items if v and str(v).strip()]

    if valid_meta:
        meta_table = doc.add_table(rows=len(valid_meta), cols=2)
        meta_table.alignment = WD_TABLE_ALIGNMENT.LEFT
        meta_table.autofit = True

        for i, (label, value) in enumerate(valid_meta):
            # Label cell
            label_cell = meta_table.cell(i, 0)
            label_cell.width = Inches(1.8)
            lp = label_cell.paragraphs[0]
            lp.space_before = Pt(1)
            lp.space_after = Pt(1)
            lr = lp.add_run(label)
            lr.font.size = Pt(9)
            lr.font.color.rgb = medium_rgb
            lr.bold = True

            # Value cell
            val_cell = meta_table.cell(i, 1)
            val_cell.width = Inches(4.5)
            vp = val_cell.paragraphs[0]
            vp.space_before = Pt(1)
            vp.space_after = Pt(1)
            vr = vp.add_run(str(value))
            vr.font.size = Pt(9.5)
            vr.font.color.rgb = dark_rgb

            # Zebra striping
            if i % 2 == 0:
                for cell in [label_cell, val_cell]:
                    shading = cell._element.get_or_add_tcPr().makeelement(
                        qn("w:shd"),
                        {qn("w:fill"): "F6F8FC", qn("w:val"): "clear"},
                    )
                    cell._element.get_or_add_tcPr().append(shading)

        doc.add_paragraph()  # spacer

    # --- Sections ---
    sections = _parse_description(
        job.description or "",
        job.skills if isinstance(job.skills, list) else [],
    )

    section_order = [
        "Job Summary", "About MuraAI", "Responsibilities",
        "Required Qualifications", "Preferred Qualifications",
        "Required Skills & Technologies", "Experience Requirements",
        "Education Requirements", "Benefits & Perks", "Compensation",
        "How to Apply",
    ]
    ordered = []
    seen = set()
    for heading in section_order:
        for h, c in sections:
            if h == heading:
                ordered.append((h, c))
                seen.add(h)
                break
    for h, c in sections:
        if h not in seen:
            ordered.append((h, c))

    if not ordered:
        ordered = [("Job Summary", job.description or "No description available.")]

    for heading, content in ordered:
        if not content or not content.strip():
            continue

        # Section heading
        h_para = doc.add_heading(heading, level=2)
        h_para.space_before = Pt(12)
        h_para.space_after = Pt(4)
        for run in h_para.runs:
            run.font.color.rgb = navy_rgb

        # Section content
        content = _clean_section_content(content)
        lines = content.split("\n")
        is_list = sum(
            1 for l in lines
            if l.strip().startswith(("-", "*", chr(8226), "1", "2", "3", "4", "5", "6", "7", "8", "9"))
        ) > len(lines) * 0.3

        if is_list:
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                clean = re.sub(r"^[\-\*•]\s*", "", stripped)
                clean = re.sub(r"^\d+[\.\)]\s*", "", clean)
                if not clean:
                    continue
                p = doc.add_paragraph(style="List Bullet")
                p.space_before = Pt(1)
                p.space_after = Pt(1)
                run = p.add_run(clean)
                run.font.size = Pt(10)
                run.font.color.rgb = dark_rgb
        else:
            p = doc.add_paragraph()
            p.space_before = Pt(2)
            p.space_after = Pt(4)
            run = p.add_run(content)
            run.font.size = Pt(10.5)
            run.font.color.rgb = dark_rgb

    # --- Footer text ---
    doc.add_paragraph()
    footer_para = doc.add_paragraph()
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer_para.add_run(
        f"MuraAI Refer  |  Generated {datetime.now().strftime('%B %d, %Y')}  |  Confidential"
    )
    footer_run.font.size = Pt(8)
    footer_run.font.color.rgb = medium_rgb
    footer_run.italic = True

    # Save to bytes
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ===========================================================================
# Public API
# ===========================================================================
def generate_jd(job, fmt: str = "pdf") -> bytes:
    """Generate a JD document in the requested format.

    Parameters
    ----------
    job : models.Job
        The job posting model instance.
    fmt : str
        'pdf' or 'docx'.

    Returns
    -------
    bytes
        The file content.

    Raises
    ------
    ValueError
        If fmt is not 'pdf' or 'docx'.
    """
    if fmt == "pdf":
        return generate_jd_pdf(job)
    elif fmt in ("docx", "word"):
        return generate_jd_docx(job)
    else:
        raise ValueError(f"Unsupported format: {fmt}. Use 'pdf' or 'docx'.")
