"""AccordionQ2 Python client library for the Hardware Management REST API."""

from .client import AccordionQ2Client
from .exceptions import AccordionQ2ApiError

__all__ = ["AccordionQ2Client", "AccordionQ2ApiError"]
__version__ = "1.0.0"
