"""Shared test configuration and fixtures for integration tests."""

import os

import pytest

from accordionq2 import AccordionQ2Client

DEFAULT_BASE_URL = "http://agent64.local:5000"

# --- Well-known resource names on agent64 hardware ---
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

# --- LED channel aliases (ESH10000355) ---
LED_CHANNELS = [
    "0.11.ESH10000355.A1",
    "0.11.ESH10000355.B1",
    "0.11.ESH10000355.C1",
    "0.11.ESH10000355.D1",
    "0.11.ESH10000355.E1",
    "0.11.ESH10000355.F1",
]

# --- Physical system expectations ---
EXPECTED_HOST_NAME = "agent64"
BASE_MODULE_PRODUCT_ID = "ESH10000158"
BASE_MODULE_NAME = "AGENT Q2 Base"


@pytest.fixture(scope="session")
def base_url():
    return os.environ.get("ACCORDIONQ2_API_URL", DEFAULT_BASE_URL)


@pytest.fixture(scope="session")
def client(base_url):
    with AccordionQ2Client(base_url) as c:
        yield c
