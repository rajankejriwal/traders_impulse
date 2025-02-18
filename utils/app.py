import logging
import os
import time


unique_id = os.getenv("UNIQUE_ID")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger()
logger.info("Starting the file.")

while True:
    time.sleep(2)
    logger.info(f"Log Yes {unique_id}")
    print(f"print yes {unique_id}")
