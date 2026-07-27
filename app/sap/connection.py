import logging
import queue
from contextlib import contextmanager
from typing import Iterator

from app.config import Settings
from app.sap.exceptions import SAPConnectionError

logger = logging.getLogger(__name__)

try:
    from pyrfc import Connection as RFCConnection  # type: ignore
    from pyrfc import RFCError  # type: ignore

    PYRFC_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when pyrfc isn't installed
    RFCConnection = None
    RFCError = Exception
    PYRFC_AVAILABLE = False


class SAPConnectionManager:
    """Manages a small pool of RFC connections to an SAP application server.

    Requires the optional `pyrfc` package plus the proprietary SAP NW RFC SDK
    to be installed (see requirements-sap.txt). If unavailable, use the
    mock client (app.sap.mock_client) instead - the middleware detects this
    automatically based on Settings.sap_mock_mode.
    """

    def __init__(self, settings: Settings):
        if not PYRFC_AVAILABLE:
            raise SAPConnectionError(
                "pyrfc is not installed. Install requirements-sap.txt and the "
                "SAP NW RFC SDK, or set SAP_MOCK_MODE=true to use the mock client."
            )
        self._settings = settings
        self._pool: queue.Queue = queue.Queue(maxsize=settings.sap_pool_size)
        for _ in range(settings.sap_pool_size):
            self._pool.put(None)  # lazily created on first checkout

    def _connection_params(self) -> dict:
        return {
            "ashost": self._settings.sap_ashost,
            "sysnr": self._settings.sap_sysnr,
            "client": self._settings.sap_client,
            "user": self._settings.sap_user,
            "passwd": self._settings.sap_passwd,
            "lang": self._settings.sap_lang,
        }

    def _open(self) -> "RFCConnection":
        try:
            return RFCConnection(**self._connection_params())
        except RFCError as exc:
            raise SAPConnectionError(f"Unable to connect to SAP: {exc}") from exc

    @contextmanager
    def get_connection(self) -> Iterator["RFCConnection"]:
        conn = self._pool.get()
        if conn is None or not conn.alive:
            conn = self._open()
        try:
            yield conn
            self._pool.put(conn)
        except Exception:
            try:
                conn.close()
            finally:
                self._pool.put(None)
            raise

    def close_all(self) -> None:
        while not self._pool.empty():
            conn = self._pool.get()
            if conn is not None:
                conn.close()
