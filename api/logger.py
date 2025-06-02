
from configparser import ConfigParser
from datetime import datetime
from logging import handlers

from pathlib import Path
import logging

import os
import socket

from api import CONFIG


def get_logger():
    

    # init logging
    outfolder=CONFIG.get('LOGGING','PATH_AVAILABILITY_CHECK_STATS', fallback=os.path.join(Path.cwd(), "/log_availability_check"))
    os.makedirs(outfolder, exist_ok=True)
    
    os.makedirs(outfolder, exist_ok=True)
    
    _handlers=[
            logging.StreamHandler(),
        ]
    
    if CONFIG.getboolean('LOGGING','ACTIVE_FILE_LOGGING', fallback="True"):
        logdir=CONFIG.get('LOGGING','PATH_AVAILABILITY_CHECK_LOGS', fallback=os.path.join(Path.cwd(), "/log_availability_check/sys_logs"))
        _handlers.append(logging.FileHandler(os.path.join(logdir, f"downloader_{datetime.now().date().isoformat()}.log")))
        
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # set formatter
    formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s')
    for h in _handlers:
        h.setFormatter(formatter)
    for h in _handlers:
        logger.addHandler(h)
    
    if CONFIG.getboolean('EMAIL_LOGGER','ACTIVE', fallback="True"):
        mailhost = CONFIG.get('EMAIL_LOGGER', 'MAILHOST', fallback=None)
        mailport = CONFIG.getint('EMAIL_LOGGER', 'MAILPORT', fallback=None)
        fromaddr = CONFIG.get('EMAIL_LOGGER', 'FROMADDR', fallback=None)
        toaddrs = CONFIG.get('EMAIL_LOGGER', 'TOADDRS', fallback=None)
        subject = CONFIG.get('EMAIL_LOGGER', 'SUBJECT', fallback="")+" on "+socket.gethostname()
        username = CONFIG.get('EMAIL_LOGGER', 'USERNAME', fallback=None)
        password = CONFIG.get('EMAIL_LOGGER', 'PASSWORD', fallback=None)
        
        prms=[mailhost, mailport, fromaddr, toaddrs, subject, username, password]
        if all([x is not None for x in prms]):
            email_handler = handlers.SMTPHandler(
                mailhost=(
                    mailhost,
                    mailport
                ),
                fromaddr=fromaddr,
                toaddrs=toaddrs,
                subject=subject,
                credentials=(
                    username,
                    password
                ),
                secure=()
            )
            email_handler.setLevel(logging.WARNING)
            email_handler.setFormatter(formatter)
            logger.addHandler(email_handler)
        else:
            if any(x is not None for x in prms):
                logger.error("Email logger not configured properly. Please check your config file.")
    
    return logger
