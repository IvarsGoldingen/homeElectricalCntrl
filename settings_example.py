"""
Settings of the app
Actual settings.py file used in code. This is just an example.
"""
import logging

# Because 2 connections sometimes hangs up the device - start on home automation PC but not on coding PC
AHU_ENABLED = False

# Logging setup
BASE_LOG_LEVEL = logging.DEBUG
CONSOLE_LOG_LEVEL = logging.DEBUG
FILE_LOG_LEVEL = logging.INFO