"""Integration tests for channel operations."""

import pytest

from accordionq2 import AccordionQ2ApiError
from accordionq2.enums import ChannelTypes
from tests.conftest import ANALOG_CHANNEL_ALIAS, ADC_CHANNEL_ALIAS, I2C_CHANNEL_ALIAS

pytestmark = pytest.mark.integration


def test_get_all_returns_non_empty(client):
    channels = client.channels.get_all()
    print("Channels count: {}".format(len(channels)))
    for ch in channels:
        print("  Ch {}: Alias={} | Type={} | Unit={}".format(
            ch.channel_index, ch.alias, ch.channel_type, ch.unit))
    assert channels
    assert len(channels) > 0, "Expected at least one channel"


def test_get_all_channels_have_aliases(client):
    channels = client.channels.get_all()
    for ch in channels:
        assert ch.alias, \
            "Channel index {} has no alias".format(ch.channel_index)


def test_get_channel_by_alias_analog(client):
    ch = client.channels.get_channel(alias=ANALOG_CHANNEL_ALIAS)
    print("Analog channel: Alias={} | Type={} | Unit={}".format(
        ch.alias, ch.channel_type, ch.unit))
    assert ch.alias == ANALOG_CHANNEL_ALIAS
    assert ch.channel_type & ChannelTypes.ANALOG, \
        "Expected Analog channel type, got {}".format(ch.channel_type)
    assert ch.unit == "V", "Analog voltage channel should have unit 'V'"


def test_get_channel_by_alias_adc(client):
    try:
        ch = client.channels.get_channel(alias=ADC_CHANNEL_ALIAS)
    except AccordionQ2ApiError as exc:
        if "not found" in str(exc).lower() or "no such" in str(exc).lower():
            pytest.skip("ADC channel {} not present on this hardware: {}".format(ADC_CHANNEL_ALIAS, exc))
        raise
    print("ADC channel: Alias={} | Type={} | Unit={}".format(
        ch.alias, ch.channel_type, ch.unit))
    assert ch.alias == ADC_CHANNEL_ALIAS
    assert ch.channel_type & ChannelTypes.ANALOG, \
        "ADC channel should be Analog, got {}".format(ch.channel_type)


def test_get_channel_by_alias_i2c(client):
    ch = client.channels.get_channel(alias=I2C_CHANNEL_ALIAS)
    print("I2C channel: Alias={} | Type={} | Unit={}".format(
        ch.alias, ch.channel_type, ch.unit))
    assert ch.alias == I2C_CHANNEL_ALIAS
    assert ch.channel_type & ChannelTypes.I2C, \
        "Expected I2C channel type, got {}".format(ch.channel_type)


def test_get_channel_invalid_alias_raises(client):
    with pytest.raises(AccordionQ2ApiError):
        client.channels.get_channel(alias="NonExistent.Channel.12345")
