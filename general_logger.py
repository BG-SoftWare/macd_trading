import datetime
import logging
import os


def get_logger(name: str, file_name: str):
    if os.path.exists(f"logs/{datetime.datetime.now().strftime('%Y')}/{datetime.datetime.now().strftime('%m')}"):
        pass
    else:
        os.makedirs(f"logs/{datetime.datetime.now().strftime('%Y')}/{datetime.datetime.now().strftime('%m')}")

    filename = f"logs/{datetime.datetime.now().strftime('%Y')}/{datetime.datetime.now().strftime('%m')}/" \
               f"{file_name.lower()}_{datetime.datetime.now().strftime('%Y-%m-%d')}.log"

    stream_handler = logging.StreamHandler()
    file_handler = logging.FileHandler(filename=filename, mode="a")
    logging.basicConfig(level=logging.INFO,
                        format='[%(levelname)s] - %(asctime)s - %(name)s - %(threadName)s - %(message)s',
                        handlers=[file_handler, stream_handler])
    logging.getLogger("binance").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return logging.getLogger(name)
