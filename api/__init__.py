# [S3_BUCKET]
# # 
# ENDPOINT_S2=

# [COPERNICUS]
# REST_API_ENDPOINT_S2=

from configparser import ConfigParser
import sys


CONFIG = ConfigParser()

args=sys.argv[1:]
args=["config.ini"]

try:
    with open(args[0]) as config_file:
        CONFIG.read_file(config_file)
except Exception:
    print("Configuration file not found. Aborting.")
    quit()