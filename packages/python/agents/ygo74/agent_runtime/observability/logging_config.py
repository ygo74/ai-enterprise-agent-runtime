import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Configure logging from supplied settings.

    Args:
        level (int): Logging level applied to the package logger.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s route=%(route)s %(message)s",
    )
