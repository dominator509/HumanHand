"""Windows DPAPI key provider via ctypes (Crypt32).

Implements the ``KeyProvider`` protocol with the real
``CryptProtectData`` / ``CryptUnprotectData`` calls. Uses
``CRYPTPROTECT_UI_FORBIDDEN`` (0x1) and no additional entropy. Any
ctypes/WinError failure raises ``EncryptionUnavailableError`` with the
error kind only — never user data.

The crypt32/kernel32 DLLs are loaded only when ``sys.platform == "win32"``;
constructing the provider on another platform raises
``EncryptionUnavailableError``.
"""

from __future__ import annotations

import ctypes
import sys

from humanhand.infra.stores.key_provider import EncryptionUnavailableError

_CRYPTPROTECT_UI_FORBIDDEN = 0x1


class _DataBlob(ctypes.Structure):
    """DATA_BLOB mirror: cbData (DWORD) + pbData (LPBYTE)."""

    _fields_ = [
        ("cbData", ctypes.c_ulong),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


if sys.platform == "win32":
    _crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _CryptProtectData = _crypt32.CryptProtectData
    _CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.c_wchar_p,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(_DataBlob),
    ]
    _CryptProtectData.restype = ctypes.c_int  # BOOL

    _CryptUnprotectData = _crypt32.CryptUnprotectData
    _CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(ctypes.c_wchar_p),
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(_DataBlob),
    ]
    _CryptUnprotectData.restype = ctypes.c_int  # BOOL

    def _blob_from_bytes(data: bytes) -> _DataBlob:
        """Build a DATA_BLOB pointing at a copy of ``data``."""
        size = max(len(data), 1)
        buffer = ctypes.create_string_buffer(data, size)
        return _DataBlob(len(data), buffer)

    def _bytes_from_blob(blob: _DataBlob) -> bytes:
        """Copy the blob payload out and LocalFree the buffer."""
        try:
            if blob.cbData == 0:
                return b""
            return ctypes.string_at(blob.pbData, blob.cbData)
        finally:
            _kernel32.LocalFree(ctypes.cast(blob.pbData, ctypes.c_void_p))

    def _protect(data: bytes) -> bytes:
        blob_in = _blob_from_bytes(data)
        blob_out = _DataBlob()
        if not _CryptProtectData(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(blob_out),
        ):
            raise EncryptionUnavailableError("dpapi_protect_failed")
        return _bytes_from_blob(blob_out)

    def _unprotect(data: bytes) -> bytes:
        blob_in = _blob_from_bytes(data)
        blob_out = _DataBlob()
        if not _CryptUnprotectData(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(blob_out),
        ):
            raise EncryptionUnavailableError("dpapi_unprotect_failed")
        return _bytes_from_blob(blob_out)

else:

    def _protect(data: bytes) -> bytes:
        raise EncryptionUnavailableError("dpapi_unavailable_on_non_windows")

    def _unprotect(data: bytes) -> bytes:
        raise EncryptionUnavailableError("dpapi_unavailable_on_non_windows")


class WindowsDpapiKeyProvider:
    """Real Windows DPAPI encryption bound to the machine-local user.

    Ciphertexts are only decryptable by the same Windows user on the same
    machine (DPAPI scope = current user). Implements ``KeyProvider``.
    """

    provider_name = "dpapi"

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise EncryptionUnavailableError("dpapi_unavailable_on_non_windows")

    def encrypt(self, plaintext: bytes) -> bytes:
        """Protect ``plaintext`` with CryptProtectData (UI forbidden)."""
        return _protect(plaintext)

    def decrypt(self, ciphertext: bytes) -> bytes:
        """Unprotect a DPAPI blob with CryptUnprotectData."""
        return _unprotect(ciphertext)
