from flask import Flask, render_template, redirect, url_for, flash, abort, request
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, UserForm, LoginForm, CommentForm
from functools import wraps
from flask_gravatar import Gravatar
import smtplib
import os

app = Flask(__name__)
# app.config['SECRET_KEY'] = os.environ.get('8BYkEfBA6O6donzWlSihBXox7C0sKR6b')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
ckeditor = CKEditor(app)
Bootstrap(app)

## Gravatar
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

##CONNECT TO DB
uri = os.environ.get('DATABASE_URL')
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri, 'sqlite:///blog1.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)


##CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = "User"
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(1000), nullable=False)
    email = db.Column(db.String(250), nullable=False)
    password = db.Column(db.String(250), nullable=False)

    ## blogpost is random name for posts, "Name: BlogPost in bracket is name of child"
    ## back_populates='author' this value defined in child class BlogPost
    # blogpost = relationship('BlogPost', back_populates='author')
    comments = relationship('Comment', back_populates='comment_author')


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    ## In User.id User = "__tablename__ = "User"" from class User
    ## Id of associated user or owner of post
    # author_id = db.Column(db.Integer, db.ForeignKey('User.id'))

    # author = db.Column(db.String(250), nullable=False)
    ## In author "User" in bracket is parent and
    ## back_populates='blogpost' value defined in parent class User
    # author = relationship('User', back_populates='blogpost')
    author = db.Column(db.String(250), nullable=False)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship('Comment', back_populates='parent_post')


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('User.id'))
    comment_author = relationship('User', back_populates='comments')
    text = db.Column(db.Text, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))
    parent_post = relationship('BlogPost', back_populates='comments')


# db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_anonymous or current_user.id != 1:
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts,
                           current_user=current_user)


@app.route('/register', methods=['GET', 'POST'])
def register():
    user_form = UserForm()
    if user_form.validate_on_submit():
        user_exist = User.query.filter_by(email=user_form.email.data).first()
        if user_exist:
            flash('User already registered using this email id, Login Instead!!')
            return redirect(url_for('login'))
        else:
            new_user = User(user=user_form.name.data,
                            email=user_form.email.data,
                            password=generate_password_hash(user_form.password.data,
                                                            method='pbkdf2:sha256',
                                                            salt_length=8)
                            )
            db.session.add(new_user)
            db.session.commit()
            flash('New User Created Successfully!')
            login_user(new_user)
            return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=user_form, current_user=current_user)


@app.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        user_login = User.query.filter_by(email=login_form.email.data).first()
        if user_login:
            if check_password_hash(user_login.password, login_form.password.data):
                login_user(user_login)
                return redirect(url_for('get_all_posts'))
            else:
                flash('Incorrect Password, Please try again!!')
        else:
            flash('No user found with email id, Please register to log in!!')
            return redirect(url_for('register'))
    return render_template("login.html", form=login_form, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    comments = CommentForm()
    requested_post = BlogPost.query.get(post_id)
    all_comments = Comment.query.filter_by(post_id=post_id).all()
    if comments.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comment(text=comments.comment.data,
                                  comment_author=current_user,
                                  parent_post=requested_post
                                  )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for('show_post', post_id=post_id))
        else:
            flash("Please log in to comment!!")
            return redirect(url_for('login'))

    return render_template("post.html", post=requested_post,
                           current_user=current_user,
                           comment_form=comments,
                           show_comments=all_comments
                           )


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        message = request.form.get('message')
        print(f'{name}\n{email}\n{phone}\n{message}')
        with smtplib.SMTP('smtp.gmail.com') as gmail_connection:
            gmail_connection.starttls()
            gmail_connection.login('SENDER ID', 'SENDER PASSWORD')
            gmail_connection.sendmail(from_addr='SENDER ID',
                                      to_addrs='RECEIVER ID',
                                      msg=f'Subject:You have received new email from {name}\n\n'
                                          f'Name: {name}\nEmail: {email}\nPhone: {phone}\nMessage= {message}'
                                      )
        flash('Message sent successfully!!')
        return redirect(url_for('contact'))
    return render_template("contact.html")


@app.route("/new-post", methods=['GET', 'POST'])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=form.author.data,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
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
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host="0.0.0.0")
