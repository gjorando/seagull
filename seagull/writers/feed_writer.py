from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urljoin

from feedgenerator import Atom1Feed, Rss201rev2Feed, get_tag_uri
from markupsafe import Markup

from seagull.contents.feed import FeedType
from seagull.writers.writer import Writer

if TYPE_CHECKING:
    from pathlib import Path

    from feedgenerator import SyndicationFeed

    from seagull.contents import Feed
    from seagull.context import Context


class FeedWriter(Writer):
    """Writer for Atom and RSS feeds."""

    FEED_CLASSES: ClassVar[dict[FeedType, type[SyndicationFeed]]] = {
        FeedType.ATOM: Atom1Feed,
        FeedType.RSS: Rss201rev2Feed,
    }

    def _parse_data(self, obj: Feed, context: Context) -> dict[Path, str | Path]:
        del context  # Unused argument
        title = obj.settings.sitename
        if obj.title:
            title += f" - {title}"
        feed = self.FEED_CLASSES[obj.feed_type](
            title=Markup("{}").format(title).striptags(),
            link=obj.settings.siteurl,
            feed_url=obj.url,
            # TODO content for feeds? Maybe put the content of the taxonomy if applicable?
            description=obj.content,
            subtitle=obj.settings.sitesubtitle,
        )
        for article in obj.articles:
            referrer = "?ref=feed" if obj.settings.feed_append_ref else ""
            url = urljoin(obj.settings.siteurl, article.url) + referrer
            # RSS feeds use a single tag for both the full content and summary; if we
            # have an ATOM feed, or rss_feed_summary_only is on, we store the summary
            summary = (
                article.summary
                if obj.feed_type == FeedType.ATOM or obj.settings.rss_feed_summary_only
                else article.content
            )
            # As a result, content is None if we have an RSS feed
            content = None if obj.feed_type == FeedType.RSS else article.content
            if summary == content and obj.feed_type == FeedType.ATOM:
                summary = None
            feed.add_item(
                title=Markup("{}").format(article.title).striptags(),
                link=url,
                unique_id=get_tag_uri(url, article.date),
                description=summary,
                content=content,
                # Categories are the category name, plus the tag names
                categories=[article.category.name, *(t.name for t in article.tags)],
                author_name=article.author,
                pubdate=article.date,
                updateddate=article.modified,
            )
        return {obj.settings.output_path / obj.save_as: feed.writeString("utf-8")}
