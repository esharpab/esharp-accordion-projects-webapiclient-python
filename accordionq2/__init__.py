"""AccordionQ2 Python client library for the Hardware Management REST API."""

from .client import AccordionQ2Client
from .enums import (
    AppTypes,
    BusActions,
    ChannelTypes,
    DirectionTypes,
    ModuleStatus,
    MpioUsageTypes,
)
from .exceptions import AccordionQ2ApiError
from .models import (
    AppLicenseDto,
    BusTransactionResponse,
    ChannelConfigRequest,
    ChannelDto,
    ChannelLookupRequest,
    ConnectionStatusDto,
    ModuleSettingsDto,
    NumericMeasureResultDto,
    NumericResultChannelDto,
    PhysicalModuleDto,
    PhysicalSystemDto,
)

__all__ = [
    # Client
    "AccordionQ2Client",
    # Exceptions
    "AccordionQ2ApiError",
    # Enums
    "AppTypes",
    "BusActions",
    "ChannelTypes",
    "DirectionTypes",
    "ModuleStatus",
    "MpioUsageTypes",
    # Models – DTOs (read-only, frozen)
    "AppLicenseDto",
    "BusTransactionResponse",
    "ChannelDto",
    "ConnectionStatusDto",
    "ModuleSettingsDto",
    "NumericMeasureResultDto",
    "NumericResultChannelDto",
    "PhysicalModuleDto",
    "PhysicalSystemDto",
    # Models – request objects (mutable)
    "ChannelConfigRequest",
    "ChannelLookupRequest",
]
__version__ = "2.0.0"

