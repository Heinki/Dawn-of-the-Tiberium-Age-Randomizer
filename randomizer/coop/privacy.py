"""Display-only privacy filtering for co-op connection messages."""

import re


def redact_connection_details(value, *private_values):
    """Remove connection details from visible messages, not network payloads."""
    text = str(value)
    for private in sorted({str(item) for item in private_values if item}, key=len, reverse=True):
        text = text.replace(private, '[hidden]')
    return re.sub(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])', '[hidden IP]', text)
