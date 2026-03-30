"""Exception types for the AccordionQ2 client."""


class AccordionQ2ApiError(Exception):
    """Raised when the AccordionQ2 API returns a non-success HTTP status code."""

    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code

    def __repr__(self):
        return "AccordionQ2ApiError({}, {!r})".format(self.status_code, self.args[0])
