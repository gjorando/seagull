from datetime import datetime

from attrs import field

from seagull.utils import datetime_converter

from .content import Content
from .utils import seagull_object


@seagull_object
class Article(Content):
    """An article."""

    date: datetime = field(converter=datetime_converter)
    """Creation date of the object."""

    @date.default
    def _attrs_default_date(self) -> datetime:
        return datetime.now()
