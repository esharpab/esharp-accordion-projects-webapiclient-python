"""AccordionQ2 Python client library for the Hardware Management REST API."""

from .boot import (
    BootAddress,
    BootAliasFile,
    BootConfig,
    BootModule,
    BootService,
    BootWifi,
)
from .capabilities import CapabilitiesDto, NamesCapability
from .certificates import normalize_sha256, sha256_of
from .channels import ByteStreamImage, ByteStreamLoadError, ByteStreamStatus
from .client import AccordionQ2Client
from .drummer import DrummerModuleRef, DrummerTarget
from .enums import (
    AppTypes,
    BusActions,
    ChannelTypes,
    DirectionTypes,
    ModuleStatus,
    MpioUsageTypes,
)
from .events import EventStream, ServerEvent
from .exceptions import (
    AccordionQ2ApiError,
    AccordionQ2CertificateError,
    AccordionQ2NotSupportedError,
    AccordionQ2SecurityError,
    AccordionQ2SecurityReason,
    AccordionQ2ShortReadError,
)
from .files import FileEntry, FileListing, FileRoot
from .firmware import (
    FirmwareRelease,
    FirmwareReleases,
    FirmwareSource,
    FirmwareState,
    FirmwareUpdateStatus,
)
from .jtag_ports import JtagDisturbed, JtagHolder, JtagPort, JtagPortState, JtagXvc
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
    ModulePresenceDto,
    ModuleSettingsDto,
    NumericMeasureResultDto,
    NumericResultChannelDto,
    PhysicalModuleDto,
    PhysicalSystemDto,
)
from .resources import CachedValues
from .subscriptions import SubscriptionDto
from .system import ClockStatus, ServiceStatus

__all__ = [
    # Exceptions
    "AccordionQ2ApiError",
    "AccordionQ2CertificateError",
    # Client
    "AccordionQ2Client",
    "AccordionQ2NotSupportedError",
    "AccordionQ2SecurityError",
    "AccordionQ2SecurityReason",
    "AccordionQ2ShortReadError",
    # Models - DTOs (read-only, frozen)
    "AppLicenseDto",
    # Enums
    "AppTypes",
    "BootAddress",
    "BootAliasFile",
    "BootConfig",
    "BootModule",
    "BootService",
    "BootWifi",
    "BusActions",
    "BusTransactionResponse",
    "ByteStreamImage",
    "ByteStreamLoadError",
    "ByteStreamStatus",
    "CachedValues",
    "CalibrationChannelDto",
    "CalibrationRowDto",
    "CalibrationTableDto",
    "CapabilitiesDto",
    "ChannelConfigRequest",
    "ChannelDto",
    "ChannelLookupRequest",
    "ChannelTypes",
    "ClockStatus",
    "ConnectionStatusDto",
    "DirectionTypes",
    "DrummerModuleRef",
    "DrummerTarget",
    "EventStream",
    "FileEntry",
    "FileListing",
    "FileRoot",
    "FirmwareRelease",
    "FirmwareReleases",
    "FirmwareSource",
    "FirmwareState",
    "FirmwareUpdateStatus",
    "InstrumentDto",
    "JtagDisturbed",
    "JtagHolder",
    "JtagPort",
    "JtagPortState",
    "JtagXvc",
    "LeaseDto",
    "ModulePresenceDto",
    "ModuleSettingsDto",
    "ModuleStatus",
    "MpioUsageTypes",
    "NamesCapability",
    "NumericMeasureResultDto",
    "NumericResultChannelDto",
    "PhysicalModuleDto",
    "PhysicalSystemDto",
    "ServerEvent",
    "ServiceStatus",
    "SubscriptionDto",
    # Certificate fingerprints
    "normalize_sha256",
    "sha256_of",
]

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _metadata_version

try:
    __version__ = _metadata_version("accordionq2")
except PackageNotFoundError:
    __version__ = "unknown"
