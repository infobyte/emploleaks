import logging
from logging.handlers import RotatingFileHandler
from logging import handlers
import sys
import os

from colorama import Fore, Style    

class CustomFormatter(logging.Formatter):
    def __init__(self, fmt):
        super().__init__()
        self.fmt = fmt

        self.FORMATS = {
            logging.DEBUG: f"[{Fore.YELLOW}*{Style.RESET_ALL}] {self.fmt}",
            logging.INFO: f"[{Fore.GREEN}+{Style.RESET_ALL}] {self.fmt}",
            logging.WARNING: f"[{Fore.BLUE}*{Style.RESET_ALL}] {self.fmt}",
            logging.ERROR: f"[{Fore.RED}*{Style.RESET_ALL}] {self.fmt}",
            logging.CRITICAL: f"[{Fore.RED}-{Style.RESET_ALL}] {self.fmt}"
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

log = logging.getLogger('')
log.setLevel(logging.INFO)
format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
format_stdout = CustomFormatter("%(message)s")

ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(format_stdout)
log.addHandler(ch)

if not os.path.isdir("logs"):
    os.mkdir("logs")

fh = handlers.RotatingFileHandler(os.path.join("logs", "log.txt"), maxBytes=(1048576*5), backupCount=7)
fh.setFormatter(format)
log.addHandler(fh)
