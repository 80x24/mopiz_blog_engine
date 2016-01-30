BEGIN TRANSACTION;
CREATE TABLE `tags` (
	`id`	INTEGER,
	`tag`	TEXT,
	`post_id`	INTEGER,
	PRIMARY KEY(id),
	FOREIGN KEY(`post_id`) REFERENCES posts(id)
);
CREATE TABLE 'search_stat'(id INTEGER PRIMARY KEY, value BLOB);
CREATE TABLE 'search_segments'(blockid INTEGER PRIMARY KEY, block BLOB);
CREATE TABLE 'search_segdir'(level INTEGER,idx INTEGER,start_block INTEGER,leaves_end_block INTEGER,end_block INTEGER,root BLOB,PRIMARY KEY(level, idx));
CREATE TABLE 'search_docsize'(docid INTEGER PRIMARY KEY, size BLOB);
CREATE TABLE 'search_content'(docid INTEGER PRIMARY KEY, 'c0title', 'c1slug', 'c2content', 'c3date', 'c4author');
CREATE VIRTUAL TABLE search USING fts4(title, slug, content, date, author, tokenize=porter);
CREATE TABLE "posts" (
	`id`	INTEGER NOT NULL,
	`title`	TEXT,
	`slug`	TEXT UNIQUE,
	`image`	TEXT,
	`content`	TEXT,
	`date`	TEXT,
	`author`	TEXT,
	`visible`	INTEGER,
	PRIMARY KEY(id)
);
COMMIT;
