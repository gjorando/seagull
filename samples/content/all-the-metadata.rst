Many metadata
#############

:title: This overrides the title
:date: 2020-01-30
:modified: 2022-03-20
:tags: foo, bar, baz
:category: My category
:author: Alice
:authors: Bob, Charles, Danton
:summary: A brief **summary**.
:lang: en
:translation: false
:description: A description for the meta html

Wow. `A link to a category. <{category}My\ category>`__
`A link to another file (relative). <{filename}article.rst>`__
`A link to another file (absolute). <{filename}/article-fr.rst>`__
`A link to a static file (that's not in STATIC_PATHS). <{static}other/file.txt>`__
`A link to a static directory. <{static}another/>`__
`A link to the index. <{index}>`__

.. image:: {static}/images/sushi.jpg
    :alt: A cat.
