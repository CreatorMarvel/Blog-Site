from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
# from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from sqlalchemy.orm import relationship, declarative_base, sessionmaker
from sqlalchemy import Integer, String, Text, Column, create_engine, ForeignKey
from functools import wraps
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_bcrypt import Bcrypt
import smtplib
from dotenv import load_dotenv
import os


def configure():
    load_dotenv()


configure()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('app_key')
ckeditor = CKEditor(app)
Bootstrap5(app)

# TODO: Configure Flask-Login
bcrypt = Bcrypt(app)

# CREATE DATABASE
Base = declarative_base()

# LOGIN MANAGER
login_manager = LoginManager()
login_manager.login_view = 'get_all_posts'
login_manager.init_app(app)


current_user_id = int(os.getenv('current_user_id'))
email_address = os.getenv('email_address')
email_password = os.getenv('email_password')


# admin-only decorator
def admin_only(f):
    @wraps(f)
    def decorated_fun(*args, **kwargs):
        if current_user.is_authenticated:
            if current_user.id != 100425888:
                return abort(403)
        else:
            return abort(403)
        return f(*args, **kwargs)

    return decorated_fun


# CONFIGURE TABLES
class BlogPost(Base, UserMixin):
    __tablename__ = "blog_posts"

    id = Column(Integer, primary_key=True)
    title = Column(String(250), unique=True, nullable=False)
    subtitle = Column(String(250), nullable=False)
    date = Column(String(250), nullable=False)
    body = Column(Text, nullable=False)
    img_url = Column(String(250), nullable=False)

    author_id = Column(Integer, ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")

    blog = relationship("Comment", back_populates="comments")

    def __init__(self, id, title, subtitle, date, body, author, img_url):
        self.id = id
        self.title = title
        self.author = author
        self.subtitle = subtitle
        self.body = body
        self.date = date
        self.img_url = img_url

    def __repr__(self):
        return (f' ({self.id}) ({self.title}) ({self.subtitle}) ({self.date}) ({self.body}) ({self.author})  '
                f'({self.img_url})')


class User(Base, UserMixin):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)

    posts = relationship("BlogPost", back_populates="author")

    comments = relationship("Comment", back_populates="comment_author")

    def __int__(self, id, name, email, password):
        self.id = id
        self.name = name
        self.email = email
        self.password = password

    def __repr__(self):
        return f' ({self.id}) ({self.name}) ({self.email}) ({self.password})'


class Comment(Base):
    __tablename__ = 'comments'

    id = Column(Integer, primary_key=True)
    text = Column(String, nullable=False)

    author_id = Column(Integer, ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")

    blog_id = Column(Integer, ForeignKey("blog_posts.id"))
    comments = relationship("BlogPost", back_populates="blog")

    def __init__(self, id, text):
        self.id = id
        self.text = text

    def __repr__(self):
        return f'({self.id}) ({self.text})'


engine = create_engine(os.getenv('database'))
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()


@login_manager.user_loader
def load_user(user_id):
    return session.query(User).filter(User.id == user_id).first()


# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods=['GET', 'POST'])
def register():
    global current_user_id
    form = RegisterForm()
    count = len(session.query(User).all())

    if form.validate_on_submit():
        username = form.name.data
        email = form.email.data
        password = form.password.data

        if session.query(User).filter(User.email == email).first():
            flash(message='You\'ve already sign up with that email, login instead!', category='error')
            return redirect(url_for('login'))
        else:
            count += 1
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            new_user = User(
                id=count,
                name=username,
                email=email,
                password=hashed_password
            )

            login_user(new_user, remember=True)
            current_user_id = new_user.id
            session.add(new_user)
            session.commit()

            return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods=['GET', 'POST'])
def login():
    global current_user_id
    form = LoginForm()
    user = session.query(User).filter(User.email == form.email.data)

    if current_user.is_authenticated:
        flash("You are already logged in.", "info")
        return redirect(url_for("get_all_posts"))

    if form.validate_on_submit():
        if user and bcrypt.check_password_hash(user.first().password, form.password.data):
            login_user(user.first(), remember=True)
            current_user_id = user.first().id
            return redirect(url_for('get_all_posts'))
        else:
            flash("Invalid email and/or password.", "danger")
            return render_template("login.html")
    return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    global current_user_id
    current_user_id = 0
    logout_user()
    flash("You were logged out.", category='success')
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    posts = session.query(BlogPost).all()
    return render_template("index.html", all_posts=posts, user_id=current_user_id)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
@login_required
def show_post(post_id):
    form = CommentForm()
    count = len(session.query(Comment).all())

    all_comments = session.query(Comment).all()

    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))
        else:
            count += 1
            new_comment = Comment(id=count, text=form.comment.data)
            session.add(new_comment)
            session.commit()
        return redirect(url_for('get_all_posts'))
    requested_post = session.query(BlogPost).filter(BlogPost.id == post_id).first()
    return render_template("post.html", post=requested_post, form=form, comments=all_comments)


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@login_required
@admin_only
def add_new_post():
    form = CreatePostForm()
    count = len(session.query(BlogPost).all())

    if form.validate_on_submit():
        count += 1
        new_post = BlogPost(
            id=count,
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        session.add(new_post)
        session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@login_required
@admin_only
def edit_post(post_id):
    post = session.query(BlogPost).filter(BlogPost.id == post_id).first()
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, user_id=current_user_id)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@login_required
@admin_only
def delete_post(post_id):
    session.query(BlogPost).filter(BlogPost.id == post_id).delete()
    session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=['GET', 'POST'])
def contact():
    msg_sent = False
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        message = request.form.get('message')

        with smtplib.SMTP('smtp.gmail.com') as connection:
            connection.starttls()
            connection.login(
                user=email_address,
                password=email_password
            )
            connection.sendmail(
                from_addr=email_address,
                to_addrs='Laurancemile@gmail.com',
                msg=f'Subject:Blog Mail from {name}\n\nName: {name}\nEmail: {email}\nPhone: {phone}\nMessage: {message}'
            )
        msg_sent = True
    return render_template("contact.html", msg_sent=msg_sent)


if __name__ == "__main__":
    app.run(debug=False, port=5002)
