from __future__ import annotations

import io
import sys
from typing import TextIO


def _encode_message(message: str, encoding: str) -> bytes:
    """Encode a message using the target encoding with graceful fallback."""

    try:
        return message.encode(encoding)
    except UnicodeEncodeError:
        return message.encode(encoding, errors="replace")
    except Exception:
        return message.encode(encoding, errors="backslashreplace")


def safe_print(message: str, *, file: TextIO | None = None) -> None:
    """Print a message without raising UnicodeEncodeError on legacy consoles.

    The original message is emitted when the stream encoding supports it; otherwise
    characters are replaced using the stream's encoding. This keeps human-friendly
    emoji/Persian messages visible on UTF-8 terminals while degrading gracefully on
    Windows cp1252 consoles.
    """

    target: TextIO = file or sys.stdout
    encoding = getattr(target, "encoding", None) or sys.getdefaultencoding()
    data = _encode_message(message, encoding)

    # Prefer writing bytes to the buffer to bypass text-encoding surprises.
    buffer = getattr(target, "buffer", None)
    if buffer is not None and not isinstance(buffer, io.BytesIO):
        try:
            buffer.write(data + b"\n")
            buffer.flush()
            return
        except Exception:
            pass

    # Fallback to text printing with replacement to ensure no crash.
    try:
        text = data.decode(encoding, errors="replace")
    except Exception:
        text = message
    print(text, file=target)
