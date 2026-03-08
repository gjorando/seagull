class SeagullError(Exception):
    """Base seagull exception."""


class DiscardMetadataError(SeagullError):
    """Raised by a metadata processor if the metadata key is to be discarded."""


class SkippedFileError(SeagullError):
    """Raised by a reader if the read file has the `skip` status."""


class InvalidObjectError(SeagullError):
    """Raise during the initialization of a seagull object if it is invalid.

    Typically, this happens if some mandatory metadata are missing.
    """
