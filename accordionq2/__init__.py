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
    CalibrationChannelDto,
    CalibrationRowDto,
    CalibrationTableDto,
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
    # Exceptions
    "AccordionQ2ApiError",
    # Client
    "AccordionQ2Client",
    # Models - DTOs (read-only, frozen)
    "AppLicenseDto",
    # Enums
    "AppTypes",
    "BusActions",
    "BusTransactionResponse",
    "CalibrationChannelDto",
    "CalibrationRowDto",
    "CalibrationTableDto",
    "ChannelConfigRequest",
    "ChannelDto",
    "ChannelLookupRequest",
    "ChannelTypes",
    "ConnectionStatusDto",
    "DirectionTypes",
    "ModuleSettingsDto",
    "ModuleStatus",
    "MpioUsageTypes",
    "NumericMeasureResultDto",
    "NumericResultChannelDto",
    "PhysicalModuleDto",
    "PhysicalSystemDto",
]

from importlib.metadata import PackageNotFoundError, version as _metadata_version

try:
    __version__ = _metadata_version("accordionq2")
except PackageNotFoundError:
    __version__ = "unknown"
