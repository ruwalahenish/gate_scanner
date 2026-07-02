class GATEBaseError(Exception):
    status_code: int = 500
    detail: str = "Internal server error"


class ScanInProgressError(GATEBaseError):
    status_code = 409
    detail = "A scan is already running. Wait for it to complete."


class SymbolNotFoundError(GATEBaseError):
    status_code = 404
    detail = "Symbol not found in universe"


class DataFetchError(GATEBaseError):
    status_code = 503
    detail = "Market data temporarily unavailable"
