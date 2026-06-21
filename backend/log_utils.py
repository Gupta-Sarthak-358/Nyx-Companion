import logging
import sys

def setup_logger(name=__name__):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    handler.setFormatter(fmt)

    if not logger.handlers:
        logger.addHandler(handler)

    return logger

logger = setup_logger("interview")
