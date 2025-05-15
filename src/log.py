import sys
import logging
from colorlog import ColoredFormatter

def init_log(level=logging.DEBUG):
    logger = logging.getLogger()
    logger.setLevel(level)
    logging.getLogger().setLevel(level)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('cache').setLevel(logging.WARNING)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)

    stdout_handler.setFormatter(ColoredFormatter(
        "%(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(asctime)-24s%(reset)s | %(log_color)s%(module)-13s%(reset)s | %(log_color)s%(message)s%(reset)s",
        log_colors={
            'DEBUG':    'green',
            'INFO':     'purple',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'red,bg_white',
        }))
    logger.addHandler(stdout_handler)

    return logger