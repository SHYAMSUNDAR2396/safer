"""Bounded inspection of untrusted upload bytes.

The parent runs this file as a separate, isolated Python process with an empty environment,
so parser bugs or resource exhaustion cannot reach the API process or its credentials.
The child imports nothing from `safer`. Network isolation is SAF-009 (sandboxed scanner).
"""

import io
import json
import subprocess
import sys

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 30
MAX_PIXELS = 40_000_000
SIGNATURES = {
    b"%PDF-": "application/pdf",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}


def sniff(data: bytes) -> str | None:
    return next((media for sig, media in SIGNATURES.items() if data.startswith(sig)), None)


def _child(data: bytes, mode: str):
    proc = subprocess.run(
        [sys.executable, "-I", __file__, mode],
        input=data,
        capture_output=True,
        timeout=15,
        env={},
    )
    return json.loads(proc.stdout) if proc.returncode == 0 else None


def text_layer(data: bytes) -> list | None:
    """Positioned text lines [page, x, y, text] of a PDF, parsed in the isolated child."""
    try:
        return _child(data, "text")
    except (subprocess.TimeoutExpired, ValueError):
        return None


def check(data: bytes) -> dict:
    """Return page/pixel facts, or {"reason": ...} when the file must be rejected."""
    try:
        return _child(data, "check") or {"reason": "unreadable"}
    except (subprocess.TimeoutExpired, ValueError):
        return {"reason": "unreadable"}


def _inspect(data: bytes) -> dict:
    media = sniff(data)
    if media == "application/pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            return {"reason": "Encrypted PDFs are not accepted."}
        pages = len(reader.pages)
        if not 1 <= pages <= MAX_PAGES:
            return {"reason": f"PDFs must have 1 to {MAX_PAGES} pages."}
        return {"page_count": pages}
    from PIL import Image

    too_large = {"reason": "Images must be at most 40 megapixels."}
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        im = Image.open(io.BytesIO(data))
    except Image.DecompressionBombError:
        return too_large
    with im:
        if im.format not in {"PNG", "JPEG"} or im.size[0] * im.size[1] > MAX_PIXELS:
            return too_large
        im.verify()
    return {"page_count": None}


def _text(data: bytes) -> list:
    from pypdf import PdfReader

    lines = []
    for number, page in enumerate(PdfReader(io.BytesIO(data)).pages[:MAX_PAGES], 1):

        def visit(text, cm, tm, font, size, number=number):
            if text.strip():
                lines.append([number, round(tm[4], 1), round(tm[5], 1), text.strip()[:300]])

        page.extract_text(visitor_text=visit)
    return lines[:5000]


if __name__ == "__main__":
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    try:  # Not enforced on macOS; the CPU limit and parent timeout still apply.
        resource.setrlimit(resource.RLIMIT_AS, (1 << 30, 1 << 30))
    except (ValueError, OSError):
        pass
    data = sys.stdin.buffer.read(MAX_BYTES + 1)
    if sys.argv[1:] == ["text"]:
        try:
            print(json.dumps(_text(data)))
        except Exception:
            sys.exit(1)
    else:
        try:
            result = _inspect(data)
        except Exception:
            result = {"reason": "unreadable"}
        print(json.dumps(result))
