class SeagullException(Exception):
    """Base seagull exception."""


class DiscardMetadataException(SeagullException):
    """Raised by a metadata processor if the metadata key is to be discarded."""


class SkippedFileException(SeagullException):
    """Raised by a reader if the read file has the `skip` status."""


class InvalidObject(SeagullException):
    """Raise during the initialization of a seagull object if it is invalid.

    Typically, this happens if some mandatory metadata are missing.
    """
