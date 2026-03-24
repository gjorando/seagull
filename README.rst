[WIP]Seagull
============

**THIS IS CURRENTLY A VERY UNSTABLE AND EXPERIMENTAL WORK. USE AT YOUR OWN RISK.**

Seagull is a static site generator written in Python_. It started off as a fork of Pelican_, a very popular static site generator. At first, I wanted to integrate the functionalities of the `I18N Subsites`_, a plugin for Pelican that creates internationalized sub-sites for the default site. I soon realized that Pelican codebase wouldn't allow me to do that easily, and that the *obvious* solution was to rewrite it from scratch.

I wanted to keep the re-implementation as compatible as possible with Pelican, but I ended up changing quite a lot of stuff, which means that Seagull is not a drop in replacement in an existing Pelican project.

I mean to use this for my personal needs; I don't expect anyone to use that over Pelican, but hey. It was a nice coding experiment for me.

Why the name "Seagull"?
-----------------------

Ok, Seagull is a fork of Pelican. Pelicans are big water birds, just like seagulls.

"Pelican" is named like that because it is an anagram of *calepin*, which means "notebook" in French. I looked it up, turns out "Seagull" is an anagram of "sullage", which according to the Merriam-Webster dictionary, is a synonym of… *Checks notes* "sewage".

Okay, but seagulls are really cool birds.

Why is the package named `seagull-sites`?
-----------------------------------------

Because there's `an old PyPI package <https://pypi.org/project/seagull/>`__ that's already named `seagull`. The author published a single release in 2014, refused to elaborate, and left. A chad move, but now I can't use the name `seagull`. :(

The imposter package -> ඞ

TO-DO
-----

- [ ] `dates` context attribute(s).
- [X] Handle `Settings` directly through the command line with click extra's config option (this would allow to use any config file format, but it would still be useful to allow for a .py settings file; I could extend click extra's config option for this).
- [ ] Allow .py config files in click.
- [ ] Implement setting file overrides for publish configuration.
- [ ] The handling of exceptions with multi-threading (when using the HTTP server) is broken for now.
- [ ] In autoreload, do not crash completely upon an exception occurring.
- [ ] Update a bunch of development files like `CONTRIBUTING.rst`.
- [ ] Better handling of generated taxonomies.
- [ ] Better handling of localized settings.
- [X] Hidden taxonomies (ie. taxonomies that are unlisted in the rendering context).
- [X] A way to generate arbitrary views of articles (like for instance, a virtual category that filters some article based on arbitrary filters).
- [X] reStructuredText's `abbr` tag.
- [X] RSS and Atom feeds.
- [X] Granular archives.
- [ ] Refactoring.
- [ ] Improve type annotations (for instance, replace `list` with `Sequence`, `dict` with `Mapping`, etc.).
- [ ] Handling of sorting in the archives: Right now I am enforcing the reverse chronological order in the granular archives, while the general archives keep the article sorting defined in the settings (by virtue of the general archives being a direct template). I think I should unify archives and granular archives (general archives have a "null" granularity), and add a setting for the sorting of archives.
- [X] Pagination.
- [ ] Attached files with `{attach}`.
- [ ] Documentation.
- [ ] Clarify the canonical order of arguments in the public API. Lessen the use of the whole `Settings` object in argument lists, instead passing the setting value(s) we need directly.
- [ ] Pygments.
- [ ] Rich logger.
- [ ] A testing suite.
- [ ] Markdown and HTML readers.
- [ ] Signals.
- [ ] Plug-ins.
- [ ] Remake github config, readthedocs config.
- [ ] Publish on Pypi?
- [ ] Deps in tox.ini
- [ ] What to do with content that doesn't exist in one language.
- [X] `quickstart tool.
- [ ] `import` and `themes` tools.
- [ ] A tool to convert a Pelican project to a Seagull one?
- [ ] A shim for compatibility with existing Pelican plugins?

Credits
-------

See the `THANKS <THANKS>`__ file for the full list of contributors to the original `Pelican`_ project, which Seagull is a fork of.

.. Links

.. _`I18N Subsites`: https://github.com/pelican-plugins/i18n-subsites
.. _Pelican: https://getpelican.com/
.. _Python: https://www.python.org/
