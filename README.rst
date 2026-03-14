[WIP]Seagull
============

Seagull is a static site generator written in Python_. It started off as a fork of Pelican_, a very popular static site generator. At first, I wanted to integrate the functionalities of the `I18N Subsites`_, a plugin for Pelican that creates internationalized sub-sites for the default site. I soon realized that Pelican codebase wouldn't allow me to do that easily, and that the *obvious* solution was to rewrite it from scratch.

I wanted to keep the re-implementation as compatible as possible with Pelican, but I ended up changing quite a lot of stuff, which means that Seagull is not a drop in replacement in an existing Pelican project.

I mean to use this for my personal needs; I don't expect anyone to use that over Pelican, but hey. It was a nice coding experiment for me.

Why the name "Seagull"?
-----------------------

Ok, Seagull is a fork of Pelican. Pelicans are big water birds, just like seagulls.

"Pelican" is named like that because it is an anagram of *calepin*, which means "notebook" in French. I looked it up, turns out "Seagull" is an anagram of "sullage", which according to the Merriam-Webster dictionary, is a synonym of... *Checks notes* "sewage".

Okay, but seagulls are really cool birds.

TO-DO
-----

- [ ] Update a bunch of development files like `CONTRIBUTING.rst`.
- [ ] Better handling of generated taxonomies.
- [ ] Hidden categories.
- [ ] reStructuredText's `abbr` tag.
- [ ] RSS and Atom feeds.
- [X] Granular archives.
- [ ] Pagination
- [ ] Documentation.
- [ ] Pygments.
- [ ] Rich logger.
- [ ] A testing suite.
- [ ] Markdown and HTML readers.
- [ ] Signals and plug-ins.
- [ ] What to do with content that doesn't exist in one language, option to disable subsites.
- [ ] `import`, `quickstart` and `themes` tools.
- [ ] A tool to convert a Pelican project to a Seagull one?
- [ ] A shim for compatibility with existing Pelican plugins?

Credits
-------

See the `THANKS <THANKS>`__ file for the full list of contributors to the original `Pelican`_ project, which Seagull is a fork of.

.. Links

.. _`I18N Subsites`: https://github.com/pelican-plugins/i18n-subsites
.. _Pelican: https://getpelican.com/
.. _Python: https://www.python.org/
