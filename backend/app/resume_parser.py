"""
Real resume text extraction — no mocks.

Supports:
  - .pdf   -> native text layer via pdfplumber, falling back to per-page OCR
             (pdf2image + pytesseract) for scanned/image-only PDFs
  - .docx  -> python-docx (paragraphs + tables)
  - .doc   -> best-effort via antiword/textract-style fallback is not bundled;
             we ask the user to re-save as .docx/.pdf if this fails (see note below)
  - .png/.jpg/.jpeg/.webp -> pytesseract OCR directly

Every function returns plain extracted text. Nothing here calls the AI —
this module's only job is turning a file into text so ai_service can read it.
"""
import io
import os
import re
import shutil
import logging
import subprocess
import tempfile

import pdfplumber
from PIL import Image
import pytesseract
import docx  # python-docx

logger = logging.getLogger("resume_parser")

MIN_NATIVE_TEXT_CHARS_PER_PAGE = 40  # below this, we treat the page as "scanned" and OCR it

# OCR language can be overridden by admin settings; defaults to English.
_OCR_LANG = "eng"


def set_ocr_language(lang: str):
    """Called at startup or when admin changes OCR language settings."""
    global _OCR_LANG
    if lang:
        _OCR_LANG = lang


class ResumeParseError(Exception):
    pass


def _ocr_image(img: "Image.Image") -> str:
    try:
        return pytesseract.image_to_string(img, lang=_OCR_LANG) or ""
    except Exception as exc:  # pytesseract/tesseract not available, corrupt image, etc.
        logger.warning("OCR failed on an image: %s", exc)
        return ""


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF. Uses the real text layer where present, and
    falls back to OCR (rendering the page to an image and running Tesseract)
    for pages that are scanned images with no selectable text."""
    text_parts = []
    needs_ocr_pages = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = (page.extract_text() or "").strip()
            if len(page_text) >= MIN_NATIVE_TEXT_CHARS_PER_PAGE:
                text_parts.append(page_text)
            else:
                text_parts.append(None)  # placeholder, fill in after OCR pass
                needs_ocr_pages.append(i)

    if needs_ocr_pages:
        try:
            from pdf2image import convert_from_bytes
            images = convert_from_bytes(file_bytes, dpi=250)
            for i in needs_ocr_pages:
                if i < len(images):
                    text_parts[i] = _ocr_image(images[i])
        except Exception as exc:
            logger.warning("PDF->image OCR fallback failed: %s", exc)
            for i in needs_ocr_pages:
                if text_parts[i] is None:
                    text_parts[i] = ""

    return "\n".join(p for p in text_parts if p).strip()


def extract_text_from_docx(file_bytes: bytes) -> str:
    document = docx.Document(io.BytesIO(file_bytes))
    parts = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts).strip()


def extract_text_from_image(file_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(file_bytes))
    return _ocr_image(img).strip()


def extract_text_from_txt(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8").strip()
    except UnicodeDecodeError:
        try:
            return file_bytes.decode("latin-1").strip()
        except Exception:
            raise ResumeParseError("Could not read the text file. Please re-save it with UTF-8 encoding.")


def _doc_best_window(text: str) -> str:
    """Longest contiguous run of prose-like characters in a decoded .doc stream."""
    runs = re.findall(r"[\w\s.,;:!?()&'\"%+@#*$₹\u2013\u2014\u2022\-/]+", text)
    return max(runs, key=len) if runs else ""


def _extract_doc_olefile(file_bytes: bytes) -> str:
    """Pure-Python fallback for legacy .doc via olefile.

    Older Word binary documents keep their text in the WordDocument stream.
    We decode it both as UTF-16LE (stripping the interleaved null bytes) and as
    CP1252, then keep whichever yields the longest readable prose run. This is
    heuristic but works for the large majority of unsophisticated .doc files; the
    `antiword` path above is used first whenever it is available.
    """
    import olefile

    ole = olefile.OleFileIO(io.BytesIO(file_bytes))
    try:
        if not ole.exists("WordDocument"):
            raise ResumeParseError("Not a valid Word 97-2003 .doc file")
        stream = ole.openstream("WordDocument").read()
    finally:
        ole.close()

    candidates = []

    utf16 = stream.decode("utf-16-le", errors="ignore").replace("\x00", "")
    candidates.append(_doc_best_window(utf16))

    cp1252 = stream.decode("cp1252", errors="replace")
    candidates.append(_doc_best_window(cp1252))

    text = max(candidates, key=len) if candidates else ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    text = "\n".join(lines).strip()

    if len(text) < 20:
        raise ResumeParseError(
            "Could not read text from this .doc file. Please re-save it as .docx "
            "or .pdf and upload again, or paste the text manually."
        )
    return text


def _looks_like_rtf(data: bytes) -> bool:
    head = data[:256].lstrip()
    return head.lower().startswith(b"{\\rtf") or (head.lower().startswith(b"rtf") and head.find(b"{") >= 0)


_RTF_SKIP_GROUPS = {
    "fonttbl", "colortbl", "stylesheet", "info", "generator", "themedata",
    "colorschememapping", "listtable", "listoverridetable", "revtbl", "rsidtbl",
}


def _drop_rtf_groups(raw: str) -> str:
    """Remove balanced RTF groups we don't want as text (font tables, style
    sheets, info blocks, and any '{\* ...}' group)."""
    res = []
    i, n = 0, len(raw)
    while i < n:
        if raw[i] == "{":
            m = re.match(r"\{(\*)?\\(\w+)", raw[i:])
            if m and (m.group(1) or m.group(2).lower() in _RTF_SKIP_GROUPS):
                depth, j = 1, i + 1
                while j < n and depth > 0:
                    if raw[j] == "{":
                        depth += 1
                    elif raw[j] == "}":
                        depth -= 1
                    j += 1
                i = j
                continue
        res.append(raw[i])
        i += 1
    return "".join(res)


def extract_text_from_rtf(file_bytes: bytes) -> str:
    """Decode text from an RTF stream (common for '.doc' files that are really
    RTF — WordPad/Word 'Save as Rich Text' with a .doc extension)."""
    try:
        raw = file_bytes.decode("cp1252", errors="replace")
    except Exception:
        raw = file_bytes.decode("latin-1", errors="replace")

    raw = _drop_rtf_groups(raw)
    text, i, n = [], 0, len(raw)
    while i < n:
        ch = raw[i]
        if ch == "\\":
            j = i + 1
            while j < n and raw[j].isalpha():
                j += 1
            cmd = raw[i + 1:j]
            if cmd in ("par", "line", "tab"):
                text.append("\n" if cmd != "tab" else "    ")
            if j < n and raw[j] == "-":
                j += 1
            while j < n and raw[j].isdigit():
                j += 1
            if j < n and raw[j] == " ":
                j += 1
            if cmd == "'" and j < n:  # \'hh hex control char
                hexs = raw[j:j + 2]
                try:
                    text.append(bytes([int(hexs, 16)]).decode("cp1252"))
                except Exception:
                    pass
                j += 2
            if cmd.startswith("u") and cmd[1:].isdigit():  # \uN unicode escape
                try:
                    text.append(chr(int(cmd[1:])))
                except Exception:
                    pass
            i = j
            continue
        if ch in "{}":
            i += 1
            continue
        text.append(ch)
        i += 1

    lines = [l.strip() for l in "".join(text).splitlines() if l.strip()]
    return "\n".join(lines).strip()


def _looks_like_html(data: bytes) -> bool:
    head = data[:512].lower()
    return b"<html" in head or b"<!doctype html" in head or (b"<p" in head and b"<body" in head)


def extract_text_from_html(file_bytes: bytes) -> str:
    """Best-effort text extraction from an HTML file saved with a .doc extension
    (a common trick used by Word 'Save As -> Web Page (*.htm;*.html)' with a
    .doc name)."""
    import html as _html

    try:
        raw = file_bytes.decode("utf-8", errors="replace")
    except Exception:
        raw = file_bytes.decode("cp1252", errors="replace")
    raw = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.I)
    raw = re.sub(r"<style[\s\S]*?</style>", " ", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", "\n", raw)
    raw = _html.unescape(raw)
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    return "\n".join(lines).strip()


def extract_text_from_doc(file_bytes: bytes) -> str:
    """Extract text from a legacy Word 97-2003 binary .doc.

    Primary path uses the `antiword` utility (installed in the Docker image via
    apt), which reliably decodes the binary format. Falls back to a pure-Python
    `olefile` reader so .doc still works on machines without antiword (e.g. local
    Windows dev) — with slightly lower fidelity. Also handles files that merely
    carry a .doc extension but are actually RTF or HTML.
    """
    antiword_bin = shutil.which("antiword")
    if antiword_bin:
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".doc")
            with os.fdopen(fd, "wb") as tmp:
                tmp.write(file_bytes)
            proc = subprocess.run(
                [antiword_bin, "-w", "0", tmp_path],  # -w 0 = keep lines unwrapped
                capture_output=True,
                timeout=30,
            )
            if proc.returncode == 0 and proc.stdout:
                text = proc.stdout.decode("utf-8", errors="replace").strip()
                if len(text) >= 20:
                    return text
        except Exception as exc:  # antiword missing, returns non-zero, timeout, etc.
            logger.warning("antiword .doc extraction failed: %s", exc)
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    if _looks_like_rtf(file_bytes):
        text = extract_text_from_rtf(file_bytes)
        if len(text) >= 20:
            return text
    if _looks_like_html(file_bytes):
        text = extract_text_from_html(file_bytes)
        if len(text) >= 20:
            return text

    try:
        return _extract_doc_olefile(file_bytes)
    except ResumeParseError:
        raise
    except Exception as exc:
        logger.warning("olefile .doc extraction failed: %s", exc)
        raise ResumeParseError(
            "Could not read this .doc file. It may be an encrypted or non-standard "
            "document — please re-save it as .docx or .pdf and upload again, or paste "
            "the text manually."
        )


EXTENSION_HANDLERS = {
    ".pdf": extract_text_from_pdf,
    ".docx": extract_text_from_docx,
    ".doc": extract_text_from_doc,
    ".txt": extract_text_from_txt,
    ".png": extract_text_from_image,
    ".jpg": extract_text_from_image,
    ".jpeg": extract_text_from_image,
    ".webp": extract_text_from_image,
}


def extract_text(filename: str, file_bytes: bytes) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    handler = EXTENSION_HANDLERS.get(ext)
    if not handler:
        raise ResumeParseError(
            f"Unsupported file type '{ext}'. Upload a PDF, DOCX, or image (PNG/JPG) resume."
        )
    try:
        text = handler(file_bytes)
    except ResumeParseError:
        raise
    except Exception as exc:
        logger.exception("Unhandled extraction error for %s: %s", filename, exc)
        raise ResumeParseError(
            f"Could not read this {ext or 'file'}. It may be corrupted or a "
            "non-standard format — please re-save it as .docx or .pdf and upload again, "
            "or paste the text manually."
        )
    if not text or len(text.strip()) < 20:
        raise ResumeParseError(
            "Could not extract readable text from this file. It may be a low-quality "
            "scan, password-protected, or empty — try a clearer copy or paste the text manually."
        )
    return text
