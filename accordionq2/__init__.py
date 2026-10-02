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
from .events import EventStream, ServerEvent
from .exceptions import AccordionQ2ApiError, AccordionQ2ShortReadError
from .lease import LeaseDto
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
    InstrumentDto,
    ModuleSettingsDto,
    NumericMeasureResultDto,
    NumericResultChannelDto,
    PhysicalModuleDto,
    PhysicalSystemDto,
)
from .subscriptions import SubscriptionDto

__all__ = [
    # Exceptions
    "AccordionQ2ApiError",
    # Client
    "AccordionQ2Client",
    "AccordionQ2ShortReadError",
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
    "EventStream",
    "InstrumentDto",
    "LeaseDto",
    "ModuleSettingsDto",
    "ModuleStatus",
    "MpioUsageTypes",
    "NumericMeasureResultDto",
    "NumericResultChannelDto",
    "PhysicalModuleDto",
    "PhysicalSystemDto",
    "ServerEvent",
    "SubscriptionDto",
]

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _metadata_version

try:
    __version__ = _metadata_version("accordionq2")
except PackageNotFoundError:
    __version__ = "unknown"
