"""Shared test configuration and fixtures for integration tests."""

import os
from urllib.parse import urlparse

import pytest

from accordionq2 import AccordionQ2Client

# --- Well-known resource names
CPU_TEMP_RESOURCE = "TempRegulator.CPU_TEMP"
MON_3V3_RESOURCE = "0.1.ESH10000158.MON_3V3"
MON_1V8_RESOURCE = "0.1.ESH10000158.MON_1V8"
EXT_VOLT_5V_RESOURCE = "0.7.ESH10000183.5V_EXT_VOLT"
EXT_CURR_5V_RESOURCE = "0.7.ESH10000183.5V_EXT_CURR"
UPTIME_RESOURCE = "Engine.Uptime"
FIRMWARE_RESOURCE = "Engine.FirmwareRev"

# --- Well-known channel aliases ---
ANALOG_CHANNEL_ALIAS = "0.1.ESH10000158.MON_3V3"
ADC_CHANNEL_ALIAS = "0.8.ESH10000590.ADC01"
I2C_CHANNEL_ALIAS = "0.ESH10000023.I2C09"

# --- Bus transaction device names ---
I2C_DEVICE_NAME = "0.ESH10000023.I2C09"

# --- LED channel aliases (ESH10000355) ---
LED_CHANNELS = [
    "0.11.ESH10000355.A1",
    "0.11.ESH10000355.B1",
    "0.11.ESH10000355.C1",
    "0.11.ESH10000355.D1",
    "0.11.ESH10000355.E1",
    "0.11.ESH10000355.F1",
]

# --- Physical system expectations (derived from ACCORDIONQ2_API_URL host) ---
def _expected_host_name():
    url = os.environ.get("ACCORDIONQ2_API_URL", "")
    hostname = urlparse(url).hostname or ""
    # Strip the .local mDNS suffix if present
    return hostname.replace(".local", "")

EXPECTED_HOST_NAME = _expected_host_name()
BASE_MODULE_PRODUCT_ID = "ESH10000158"
BASE_MODULE_NAME = "AGENT Q2 Base"


@pytest.fixture(scope="session")
def base_url():
    url = os.environ.get("ACCORDIONQ2_API_URL")
    if not url:
        pytest.exit("ACCORDIONQ2_API_URL environment variable must be set (e.g. http://mjsagent.local:5000)", returncode=1)
    return url


@pytest.fixture(scope="session")
def client(base_url):
    with AccordionQ2Client(base_url) as c:
        yield c
