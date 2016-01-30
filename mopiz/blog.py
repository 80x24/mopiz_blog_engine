from datetime import datetime
from flask import Flask, request, session, g, redirect, url_for, \
    abort, render_template, flash, _app_ctx_stack, Markup
from werkzeug import secure_filename
import hashlib, os, struct, uuid, sqlite3

# configuration
DATABASE = "database.db"
DEBUG = True
SECRET_KEY = "dont use in production"
USERNAME = "admin"
PASSWORD = "admin"
UPLOAD_FOLDER = "/path/to/upload/folder"
UPLOAD_REDIRECT = "/assets/uploads/"
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', '.gz', '.tar.gz', '.zip'])
# 16MB
MAX_CONTENT_LENGTH = 16 * 1024 * 1024

app = Flask(__name__, static_folder="assets")
app.config.from_object(__name__)
# jinja template whitespace removal
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

def log(error):
    message = str(error) + "\n"
    with open("log.txt", "a") as f:
        f.write(message)


def _parse_match_info(buf):
    """
    Internal function to parse match information from sqlite fts
    
    sqlite matchinfo returns a blob of 32bit unsigned ints for each value
    implementation using: <http://charlesleifer.com/blog/using-sqlite-full-text-search-with-python/>
    """
    bufsize = len(buf)
    return [struct.unpack("@I", buf[i:i+4])[0] for i in range(0, bufsize, 4)]

def rank(raw_match_info):
    """
    Search Rank function

    handle match_info called with default arguments based on example rank
    on sqlite fts page
    """
    try:
        match_info = _parse_match_info(raw_match_info)
    except Exception as inst:
        log(type(inst))
        log(inst.args)
        log(inst)
        x, y = inst.args
        tmpX = "x = " + str(x)
        tmpY = "y = " + str(y)
        log(tmpX)
        log(tmpY)
    score = 0.0
    p, c = match_info[:2]
    for phrase_num in range(p):
        phrase_info_idx = 2 + (phrase_num * c * 3)
        for col_num in range(c):
            col_idx = phrase_info_idx + (col_num * 3)
            x1, x2 = match_info[col_idx:col_idx + 2]
            if x1 > 0:
                score += float(x1) / x2
    return score

def get_db():
    """ Open a new database connection if there are not any for the current
    application context """
    top = _app_ctx_stack.top
    if not hasattr(top, "sqlite_db"):
        top.sqlite_db = sqlite3.connect(app.config["DATABASE"])
        top.sqlite_db.row_factory = sqlite3.Row
        # register rank function
        top.sqlite_db.create_function("rank", 1, rank)
    return top.sqlite_db

@app.teardown_request
def close_database(exception):
    """ Closes the database again at the end of the request """
    top = _app_ctx_stack.top
    if hasattr(top, "sqlite_db"):
        top.sqlite_db.close()

@app.before_request
def csrf_protect():
    """ Protect against CSRF """
    if request.method == "POST":
        token = session.pop("_csrf_token", None)
        if not token or token != request.form.get("_csrf_token"):
            abort(403)

def generate_csrf_token():
    """ Generate CSRF Token """
    if "_csrf_token" not in session:
        session["_csrf_token"] = hashlib.sha256(os.urandom(32)).hexdigest()
    return session["_csrf_token"]

app.jinja_env.globals["csrf_token"] = generate_csrf_token

def connect_db():
    """ connect to the database """
    return sqlite3.connect(app.config["DATABASE"])

def query_db(query, args=(), one=False):
    """ Query the database and return a list of dictionaries """
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv

def read_more(text):
    """
    Shortens text on the front page
    
    currently, the preview is all of the characters
    contained within the first paragraph.
    Right now the code doesn't check for something stupid
    like a <p></p> set within an <a> tag.
    
    arguments:
    text - string of blog post text.
    """
    short = text[0: text.find("</p>")]
    return short

def check_visible(id):
    """ Returns if an id is set to visible """
    isvisible = False
    query = query_db("""SELECT visible FROM posts WHERE id=?""", [id], one=True)
    try:
        visible = query["visible"]
    except:
        return False
    if visible == 1:
        isvisible = True
    return isvisible

def check_visible_slug(slug):
    """ Returns if a slug is visible """
    isvisible = False
    query = query_db("""SELECT visible FROM posts WHERE slug=?""", [slug], one=True)
    try:
        visible = query["visible"]
    except:
        return False
    if visible == 1:
        isvisible = True
    return isvisible

@app.route("/")
def index():
    # get post
    query = query_db("""SELECT * FROM posts WHERE visible=1 ORDER BY id DESC LIMIT 10""")

    posts = [dict(idnum=row[0], title=row[1], slug=row[2], image=row[3], content=row[4], date=row[5], author=row[6]) for row in query]
    for d in posts:
        d["content"] = read_more(d["content"])

    return render_template("main.html", posts=posts)

@app.route("/p/<int:idnum>")
def old_posts(idnum):
    #contact is 41
    #about is 42
    theNumber = int(idnum)
    if(theNumber == 41):
        return redirect(url_for("contact"), code=301)
    elif(theNumber == 42):
        return redirect(url_for("about"), code=301)
    else:
        # People can guess id numbers of future posts from here.
        # Don't know if this actually matters.
        # For example for posts after 59, they can go /p/60 and will be
        # redirected to the slug for the post that didn't use the legacy /p/
        # system.
        if not check_visible(idnum):
            abort(404)
        query = query_db("""SELECT * FROM posts WHERE id=?""", [theNumber], one=True)
        if query is None:
            abort(404)
        slug = query["slug"]
        return redirect(url_for("posts", slug=slug), code=301)

@app.route("/post/<slug>")
def posts(slug):
    if not check_visible_slug(slug):
        if not session.get("logged_in"):
            # Abort 404 here instead of 401 because we do not want to
            # acknowledge the existence of this page.
            abort(404)
    query = query_db("""SELECT * FROM posts WHERE slug=?""", [slug], one=True)
    if query is None:
        abort(404)
    tagq = query_db("""SELECT tag FROM tags WHERE post_id = ?""", [query["id"]])
    tags = [row[0] for row in tagq]
    post = dict(idnum=query["id"], title=query["title"], slug=query["slug"], image=query["image"], content=query["content"], date=query["date"], author=query["author"], visibile=query["visible"])
    return render_template("post.html", post=post, title=post["title"], tags=tags)

@app.route("/archive/")
@app.route("/archive/p/<int:pagenum>")
def archive(pagenum=1):
    archiveDone = False
    pagenum = int(pagenum)
    tmax = int(10*(pagenum+1))
    query = query_db("SELECT COUNT(id) FROM posts WHERE visible=1", one=True)
    maxDict = dict(num=query[0])
    maxNum = maxDict["num"]
    maxNum = int(maxNum)

    # archiveDone determines if the link at the end of the archive should
    # point back to the beginning of the archive
    amountLeft = maxNum - (pagenum*10)
    # If the page number is greater than the number of archive pages needed
    # return a not found.
    if amountLeft < 0:
        abort(404)
    if tmax >= maxNum:
        archiveDone = True

    query = query_db("""SELECT * FROM posts ORDER BY id DESC LIMIT ?""", [tmax])
    posts = [dict(idnum=row[0], title=row[1], slug=row[2], image=row[3], content=row[4], date=row[5], author=row[6]) for row in query]
    for d in posts:
        d["content"] = read_more(d["content"])
    if amountLeft >= 10:
        posts = posts[-10:]
    else:
        posts = posts[-amountLeft:]

    archivenum = pagenum + 1

    if archiveDone:
        archivenum = 1

    return render_template("archive.html", posts=posts, archivenum=archivenum, title="Archive")

# Add tags. User won't be able to search by tags because it will complicate
# search results, but they can see all of the tags by going to /tag
@app.route("/tag")
@app.route("/tag/<name>")
def tag(name=None):
    if name:
        tagnameq = query_db("""SELECT posts.slug, posts.title FROM tags JOIN posts ON posts.id=tags.post_id WHERE tag=?""", [name])
        results = [dict(slug=row[0], title=row[1]) for row in tagnameq]
        ttitle = "Tagged With: " + name
        return render_template("one_tag.html", tag=name, results=results, title=ttitle)
    tagq = query_db("""SELECT tag, COUNT(*) FROM tags GROUP BY tag ORDER BY tag""")
    tags = [dict(name=row[0], num=row[1]) for row in tagq]
    # Here we check that the tag count is not zero in any of the tags. If
    # the tag is zero it should not show up.
    cz = check_zero(tags)
    if cz:
        tags = None
    return render_template("all_tags.html", tags=tags, title="Tags")
 
def check_zero(tags):
    for t in tags:
        try:
            if t["num"] == 0:
                return True
        except KeyError:
            return False
    return False

@app.route("/search")
def search():
    query = request.args["q"]
    if not query:
        abort(400)
    # NOTE: THE OFFEST 0 in that query may need to be changed depending on which db column I need
    q = query_db("""SELECT title, slug, snippet(search), rank(matchinfo(search)) AS score
        FROM search
        WHERE search MATCH ?
        ORDER BY score DESC""", [query])
    results = [dict(title=row[0], slug=row[1], snippet=row[2], score=row[3]) for row in q]
    #log(results)
    num_results = int(len(results))
    return render_template("search.html", results=results, query=query, num_results=num_results, title="Search Mopiz")

@app.route("/add", methods=["GET", "POST"])
def add():
    # SOME NOTES ON THE FORM
    # everything in the first <p></p> tag will be the preview of the post
    # on the front page. There must be a <p></p> tag and there cannot be
    # a <p> tag within another <p> tag. This follows the normal rules for html.
    # There must be a title and a slug. The slug must be unique

    # NOTE: NOT SURE WHAT HAPPENS IF USER SUBMITS A NOT UNIQUE SLUG
    error = None
    if not session.get("logged_in"):
        abort(401)
    if request.method == "POST":
        if request.form["title"] == "":
            error = "You must add a title"
        elif request.form["slug"] == "":
            error = "You must add a url slug"
        else:
            isvisible = False
            if request.form.get("visible"):
                isvisible = True
                visible = 1
            else:
                visible = 0
            date = datetime.now().strftime("%A, %B %d, %Y")
            title = request.form["title"]
            slug = request.form["slug"]
            image = request.form["image"]
            content = request.form["content"]
            author = request.form["author"]

            if not title:
                title = None
            elif not image:
                image = None
            elif not content:
                content = "<p></p>"
            elif not author:
                author = None

            db = get_db()
            db.execute("""INSERT INTO posts (title, slug, image, content, date, author, visible) VALUES (?, ?, ?, ?, ?, ?, ?)""", [title, slug, image, content, date, author, visible])
            db.commit()

            # Add the post tag.
            # Currently limited to only adding one tag per add / edit.
            tag = request.form["tag-add"]
            if tag:
                # get the id of the recently added post
                pidq = query_db("""SELECT id FROM posts WHERE slug=?""", [request.form["slug"]], one=True)
                pid = pidq["id"]
                db.execute("""INSERT INTO tags (tag, post_id) VALUES (?, ?)""", [tag, pid])
                db.commit()

            # update search
            # update the search index
            # strip tags so that search doesn't store in database.
            # whitespace is normalized to one here.
            if isvisible:
                sTitle = Markup(request.form["title"]).striptags()
                sSlug = Markup(request.form["slug"]).striptags()
                sContent = Markup(request.form["content"]).striptags()
                sAuthor = Markup(request.form["author"]).striptags()
                db.execute("""INSERT INTO search (title, slug, content, date, author) VALUES (?, ?, ?, ?, ?)""", [sTitle, sSlug, sContent, date, sAuthor])
                db.commit()
            return redirect(url_for("index"))
    return render_template("add_post.html", error=error, title="Add Post")

@app.route("/upload", methods=["GET", "POST"])
def upload_file():
    if not session.get("logged_in"):
        abort(401)
    if request.method == "POST":
        file = request.files["file"]
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filename = uuid.uuid4().hex + "-" + filename
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            return redirect("http://" + app.config["UPLOAD_REDIRECT"] + filename)
        else:
            abort(415)
    return render_template("upload_file.html", title="Upload")

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1] in ALLOWED_EXTENSIONS 

@app.route("/edit/<slug>", methods=["GET", "POST"])
def edit(slug):
    error = None
    if not session.get("logged_in"):
        abort(401)
    if request.method == "POST":
        isvisible = False
        visible = 0
        value = request.form.get("visible")
        if value:
            isvisible = True
            visible = 1
        # I'm not doing any data validation here.
        # I'm also doing 4 db writes here so it is pretty slow,

        # get the current visible value before we update it so that I know
        # what to do with the search
        pastquery = query_db("""SELECT visible FROM posts WHERE slug=?""", [slug], one=True)
        past_visible = pastquery["visible"]

        tags = request.form.getlist("tag-delete")
        # get post id
        pidq = query_db("""SELECT id FROM posts WHERE slug=?""", [slug], one=True)
        pid = pidq["id"]
        db = get_db()
        if tags:
            # post ids
            pids = [pid for t in tags]
            # zip the value and id into a tuple so that we can executemany
            tagdata = zip(tags, ids)
            db.executemany("""DELETE FROM tags WHERE tag = ? AND post_id = ?""", tagdata)
            db.commit()

        title = request.form["title"]
        image = request.form["image"]
        content = request.form["content"]
        author = request.form["author"]
        if not title:
            title = None
        elif not image:
            image = None
        elif not content:
            content = "<p></p>"
        elif not author:
            author = None

        db.execute("""UPDATE posts SET title=?, slug=?, image=?, content=?, author=?, visible=? WHERE slug=?""", [title, slug, image, content, author, visible, slug])
        db.commit()

        # add a tag if there was one
        addtag = request.form["tag-add"]
        if addtag:
            db.execute("""INSERT INTO tags (tag, post_id) VALUES (?, ?)""", [addtag, pid])
            db.commit()

        # update the search index
        # strip tags so that search doesn't store in database.
        # whitespace is normalized to one here.
        if isvisible:
            sTitle = Markup(request.form["title"]).striptags()
            sSlug = Markup(request.form["slug"]).striptags()
            sContent = Markup(request.form["content"]).striptags()
            sAuthor = Markup(request.form["author"]).striptags()
            # should be 1
            if past_visible == 1:
                db.execute("""UPDATE search SET title=?, slug=?, content=?, author=? WHERE slug=?""", [sTitle, sSlug, sContent, sAuthor, slug])
                db.commit()
            else:
                # get the date. It's in the database but isn't supplied in
                # the edit form
                dateq = query_db("""SELECT date FROM posts WHERE slug=?""", [slug], one=True)
                date = dateq["date"]
                db.execute("""INSERT INTO search (title, slug, content, date, author) VALUES (?, ?, ?, ?, ?)""", [sTitle, sSlug, sContent, date, sAuthor])
                db.commit()
        elif not isvisible:
            # Update the search index so that the invisible posts don't show in
            # the search.
            db.execute("""DELETE FROM search WHERE slug=?""", [slug])
            db.commit()
            db.execute("""INSERT INTO search(search) VALUES('rebuild')""")
            db.commit()
            db.execute("""INSERT INTO search(search) VALUES('optimize')""")
            db.commit()
        return redirect(url_for("posts", slug=slug))
    query = query_db("""SELECT * FROM posts WHERE slug=?""", [slug], one=True)
    # get id of the slug
    tagsq = query_db("""SELECT tag FROM tags WHERE post_id = ?""", [query["id"]])
    tags = [row[0] for row in tagsq]
    post = dict(title=query["title"], slug=query["slug"], author=query["author"], image=query["image"], content=query["content"], visible=query["visible"])
    return render_template("edit_post.html", tags=tags, post=post, error=error, title="Edit Post")

@app.route("/invisible")
def invisible():
    """ Get a list of the posts that are invisible """
    if not session.get("logged_in"):
        abort(401)
    query = query_db("""SELECT title, slug FROM posts WHERE visible=0""")
    posts = [dict(title=row[0], slug=row[1]) for row in query]
    return render_template("invisible.html", posts=posts, title="Invisible Posts")

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        if request.form["username"] != app.config["USERNAME"]:
            error = "Invalid username or password"
        elif request.form["password"] != app.config["PASSWORD"]:
            error = "Invalid password or password"
        else:
            session["logged_in"] = True
            return redirect(url_for("index"))
    return render_template("login.html", error=error, title="Login")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("index"))

@app.route("/about")
def about():
    return render_template("about.html", title="About")

@app.route("/contact")
def contact():
    return render_template("contact.html", title="Contact")

if __name__ == "__main__":
    app.run()
