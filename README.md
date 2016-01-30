Blog Engine
============

This is the source for the blog engine that power mopiz.com
It is written in Python and Flask, and uses Sqlite for the
database.

Features
----------
- Full Text Search
- Online Adding and Editing of Posts
- Image and Document upload
- Tagging System 


DOCUMENTATION
==============

## Configuration
In order to get the blog up and running you will need to edit the
configuration values found in blog.py. You will also need to
create a sqlite3 database using the schema provided.


### Notes on specific implementation details.
The search uses SQLite FTS.
The tokenizer is porter.
I am escaping the html before sending it to the search database,
which means that whitespace is normalized to one. You won't be
able to search for a post with more than one whitespace because
it is truncated to one in the db. I'm not sure if this matters.

Each post content must have a <p> and </p> and there can't be another
<p> or </p> emdedded withing a <p></p>. This follows the normal rules of html.

Creating the search database

CREATE VIRTUAL TABLE search USING fts4(title, slug, content, date, author, tokenize=porter)

Note that the search database needs to have its integrity checked
every once in a while.

To do that look at the documentation here under section 7
https://www.sqlite.org/fts3.html
