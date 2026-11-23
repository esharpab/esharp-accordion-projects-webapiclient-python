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
from .docs import DocsList, DocsPage
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
    AccordionQ2ThrottledError,
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
from .security import (
    ApiKeyInfo,
    CallerInfo,
    CertificateInfo,
    CertificateRequest,
    CreatedApiKey,
    ExtensionCheckSummary,
    ExtensionFolder,
    ExtensionReference,
    ExtensionRelease,
    ExtensionsReport,
    FactoryResetPreview,
    FactoryResetRecord,
    FactoryResetStarted,
    HostPart,
    HostSecurity,
    HostSettings,
    LoginResponse,
    MeInfo,
    RecoveryReset,
    RecoveryWindow,
    SecurityEvent,
    SecurityEvents,
    SecurityMode,
    SecurityState,
    SshKey,
    SshKeyChange,
    StationRole,
    ThrottledClient,
    UserInfo,
)
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
    "AccordionQ2ThrottledError",
    "ApiKeyInfo",
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
    "CallerInfo",
    "CapabilitiesDto",
    "CertificateInfo",
    "CertificateRequest",
    "ChannelConfigRequest",
    "ChannelDto",
    "ChannelLookupRequest",
    "ChannelTypes",
    "ClockStatus",
    "ConnectionStatusDto",
    "CreatedApiKey",
    "DirectionTypes",
    "DocsList",
    "DocsPage",
    "DrummerModuleRef",
    "DrummerTarget",
    "EventStream",
    "ExtensionCheckSummary",
    "ExtensionFolder",
    "ExtensionReference",
    "ExtensionRelease",
    "ExtensionsReport",
    "FactoryResetPreview",
    "FactoryResetRecord",
    "FactoryResetStarted",
    "FileEntry",
    "FileListing",
    "FileRoot",
    "FirmwareRelease",
    "FirmwareReleases",
    "FirmwareSource",
    "FirmwareState",
    "FirmwareUpdateStatus",
    "HostPart",
    "HostSecurity",
    "HostSettings",
    "InstrumentDto",
    "JtagDisturbed",
    "JtagHolder",
    "JtagPort",
    "JtagPortState",
    "JtagXvc",
    "LeaseDto",
    "LoginResponse",
    "MeInfo",
    "ModulePresenceDto",
    "ModuleSettingsDto",
    "ModuleStatus",
    "MpioUsageTypes",
    "NamesCapability",
    "NumericMeasureResultDto",
    "NumericResultChannelDto",
    "PhysicalModuleDto",
    "PhysicalSystemDto",
    "RecoveryReset",
    "RecoveryWindow",
    "SecurityEvent",
    "SecurityEvents",
    "SecurityMode",
    "SecurityState",
    "ServerEvent",
    "ServiceStatus",
    "SshKey",
    "SshKeyChange",
    "StationRole",
    "SubscriptionDto",
    "ThrottledClient",
    "UserInfo",
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
