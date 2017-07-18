import logging

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__package__)
logger.setLevel(logging.INFO)
