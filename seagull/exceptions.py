"""Collection of exceptions used by Seagull."""


class SeagullError(Exception):
    """Base seagull exception."""


class SkippedFileError(SeagullError):
    """Raised by a parser if the read file has the `skip` status."""


class InvalidObjectError(SeagullError):
    """Raised by a parser if the Seagull object creation failed."""
