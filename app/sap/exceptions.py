class SAPConnectionError(Exception):
    """Raised when a connection to the SAP system cannot be established."""


class BAPIExecutionError(Exception):
    """Raised when a BAPI call returns an error in its RETURN/RETURN[] table."""

    def __init__(self, bapi_name: str, messages: list[dict]):
        self.bapi_name = bapi_name
        self.messages = messages
        text = "; ".join(m.get("MESSAGE", "") for m in messages) or "unknown error"
        super().__init__(f"{bapi_name} failed: {text}")
