"""Per-user DeepSeek credentials, kept outside the shareable project.

Run `python web/private_config.py` to enter or replace the key without echo.
Windows DPAPI encrypts the credential for the current Windows account.
Other operating systems can continue using server environment variables.
"""

from __future__ import annotations

import base64
import ctypes
import errno
import getpass
import json
import os
import re
import tempfile
from ctypes import wintypes
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-flash"


def config_path() -> Path:
    if os.name != "nt" or not os.environ.get("LOCALAPPDATA"):
        raise RuntimeError("Private file storage requires Windows; use LLM environment variables on other systems.")
    path = (Path(os.environ["LOCALAPPDATA"]) / "Puman21" / "deepseek.json").resolve()
    if path.is_relative_to(PROJECT_ROOT):
        raise RuntimeError("Private credentials must be stored outside the project.")
    return path


class DataBlob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi(value: bytes, *, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Windows DPAPI is required for private file storage.")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    function.argtypes = [
        ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob),
    ]
    function.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    buffer = (ctypes.c_ubyte * len(value)).from_buffer_copy(value)
    source = DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = DataBlob()
    # CRYPTPROTECT_UI_FORBIDDEN, user scope (never LOCAL_MACHINE).
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise RuntimeError("Private credential encryption/decryption failed for this Windows account.")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel32.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))


def save_deepseek_key(key: str) -> Path:
    key = key.strip()
    if not re.fullmatch(r"sk-[A-Za-z0-9_-]{16,}", key):
        raise ValueError("Invalid key format; nothing was saved.")
    path = config_path()
    encrypted = _dpapi(key.encode("utf-8"))
    document = {
        "version": 1, "protection": "windows-dpapi-current-user",
        "base_url": DEEPSEEK_BASE_URL, "model": DEEPSEEK_MODEL,
        "timeout": "40", "api_key_dpapi": base64.b64encode(encrypted).decode("ascii"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            json.dump(document, output, indent=2)
        try:
            os.replace(temporary, path)
        except OSError as error:
            if error.errno != errno.EXDEV and getattr(error, "winerror", None) != 17:
                raise
            # Some managed Windows profiles redirect the final file to another
            # volume. Only the DPAPI-encrypted document is copied in this case.
            path.write_bytes(temporary.read_bytes())
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return path


def load_private_config() -> bool:
    """Load at server startup only. Explicit environment values take precedence."""
    if os.name != "nt":
        return False
    path = config_path()
    if not path.exists():
        return False
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document["version"] != 1 or document["protection"] != "windows-dpapi-current-user":
            raise ValueError("Unsupported private configuration")
        if not os.environ.get("LLM_API_KEY", "").strip():
            key = _dpapi(base64.b64decode(document["api_key_dpapi"], validate=True), decrypt=True).decode("utf-8")
            os.environ["LLM_API_KEY"] = key
        for name, value in (
            ("LLM_BASE_URL", document["base_url"]),
            ("LLM_MODEL", document["model"]),
            ("LLM_TIMEOUT", document.get("timeout", "40")),
        ):
            if not os.environ.get(name, "").strip():
                os.environ[name] = str(value)
    except (KeyError, ValueError, OSError, RuntimeError):
        raise RuntimeError("Cannot load private AI configuration. Run python web/private_config.py to replace it.") from None
    return True


if __name__ == "__main__":
    try:
        destination = save_deepseek_key(getpass.getpass("DeepSeek API key (hidden input): "))
        print("Encrypted credential saved outside the project:", destination)
        print("Restart the backend to activate it. The key was not printed or stored in source code.")
    except (ValueError, RuntimeError, OSError) as error:
        print(str(error))
        raise SystemExit(1) from None
