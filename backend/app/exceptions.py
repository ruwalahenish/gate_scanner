class GATEBaseError(Exception):
    status_code: int = 500
    detail: str = "Internal server error"


class ScanInProgressError(GATEBaseError):
    status_code = 409
    detail = "A scan is already running. Wait for it to complete."


class SymbolNotFoundError(GATEBaseError):
    status_code = 404
    detail = "Symbol not found in universe"


class InsufficientCapitalError(GATEBaseError):
    status_code = 422
    detail = "Insufficient virtual capital for this trade"


class PositionNotFoundError(GATEBaseError):
    status_code = 404
    detail = "Position not found"


class DataFetchError(GATEBaseError):
    status_code = 503
    detail = "Market data temporarily unavailable"


class BacktestInProgressError(GATEBaseError):
    status_code = 409
    detail = "A backtest is already running"
