"""
Settings of the app
Actual settings.py file used in code. This is just an example.
"""
import logging

# Logging setup
BASE_LOG_LEVEL = logging.DEBUG
CONSOLE_LOG_LEVEL = logging.DEBUG
FILE_LOG_LEVEL = logging.INFO

# When system does not have AHU device OR
# When testing Because 2 connections sometimes hangs up the device - start on home automation PC but not on coding PC
AHU_ENABLED = False

# Data storage related
ENABLE_SQL_LITE_LOGGING = True
ENABLE_GRAFANA_CLOUD_LOGGING = True
GRAFANA_CLOUD_SOURCE_TAG = "home_data"