Foo tag, but secret
===================

:slug: foo-hidden
:filter: "foo" in (t.slug for t in article.tags) and article.lang == tag.lang and article.status != "draft"
:save_as: foo/hidden/index.html
:status: hidden

Showing the hidden articles!
