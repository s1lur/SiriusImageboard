from flask import Flask, render_template, request, url_for, session, redirect, abort, g, flash
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import time
from jinja2 import Markup
from flask_uploads import UploadSet, configure_uploads, IMAGES
from validate_email import validate_email
from bcrypt import hashpw, gensalt
import json
from genrandomword import random_word
import passwordmeter
"""
TODO:
1.Add rating - done
2.Store user actions - done
3.Disable empty comments - done server-side
4.Settings - done
5.Email check - done
6.Username is used - done
7.Cosmetics ???
8.Password hashing - done
9.Adding images to thread description - done
"""


#----------INITIALIZATION----------

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///database.db"
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
photos = UploadSet('photos', IMAGES)
app.config['UPLOADED_PHOTOS_DEST'] = 'static/'
app.config['UPLOADED_PHOTOS_ALLOW'] = set(['png', 'jpg', 'jpeg'])
configure_uploads(app, photos)
app.secret_key = 'oh boi'


#----------INITIALIZATION ENDED----------

#----------MODELS----------


class User(db.Model):
    __tablename__ = "users"
    id = db.Column('user_id',db.Integer , primary_key=True)
    name = db.Column('name', db.String(20), unique=True , index=True)
    password = db.Column('password' , db.String(10))
    email = db.Column('email',db.String(50),unique=True , index=True)
 
    def __init__(self, name, password, email):
        self.name = name
        self.password = hashpw(password, gensalt())
        self.email = email

    def is_authenticated(self):
        return True
 
    def is_active(self):
        return True
 
    def is_anonymous(self):
        return False
 
    def get_id(self):
        return self.id
    
    def get_name(self):
        return self.name

    def __repr__(self):
        return '<User %r>' % (self.name)


class Commentary(db.Model):
    __tablename__ = "comments"
    id = db.Column('comment_id',db.Integer , primary_key=True)
    img_src = db.Column('imgsrc', db.String(20))
    author = db.Column('author', db.String(20))
    thread = db.Column('thread' , db.Integer)
    img_present = db.Column('imgpresent', db.Boolean)
    text = db.Column('text', db.String())
    def __init__(self, img_src, author, text, thread_id):
        self.author = author
        self.img_present = img_src != ""
        self.img_src = img_src
        self.text = text
        self.thread = thread_id


class Thread(db.Model):
    __tablename__ = "threads"
    id = db.Column('thread_id',db.Integer , primary_key=True)
    author = db.Column('author', db.String(20))
    title = db.Column('title', db.String(100))
    description = db.Column('description', db.String())
    img_src = db.Column('imgsrc', db.String(20))
    img_present = db.Column('imgpresent', db.Boolean)
    created_on = db.Column('created_on', db.DateTime)
    rating = db.Column('rating', db.Integer)
    def __init__(self, img_src, author, title, description):
        self.author = author
        self.description = description
        self.title = title
        self.img_src = img_src
        self.created_on = datetime.now()
        self.img_present = img_src != ""
        self.rating = 0


class UserAction(db.Model):
    _tablename__ = "useractions"
    id = db.Column('thread_id',db.Integer , primary_key=True)
    user = db.Column('user', db.String(20))
    thread = db.Column('thread', db.Integer)
    isupvote = db.Column('isupvote', db.Boolean)
    def __init__(self, user, thread, isupvote):
        self.user = user
        self.thread = thread
        self.isupvote = isupvote


#----------MODELS ENDED----------

#----------APP ROUTES & STUFF----------

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        threads = Thread.query.all()
        threads.sort(reverse=True, key=(lambda thread: thread.rating - (float(time.mktime(datetime.now().timetuple())) - float(time.mktime(thread.created_on.timetuple()))) / 86400))
        return render_template('index.html', **locals())
    if request.form.get('id', None) is not None and request.form.get('vote', None) is not None:
        thread_id = request.form['id']
        user_id = current_user.get_id()
        vote = request.form['vote']
        action = UserAction.query.filter_by(thread=thread_id, user=user_id).first()
        thread = Thread.query.filter_by(id=thread_id).first()
        if thread is None:
            return redirect(url_for('badrequest'))
        if action is not None:
            if action.isupvote and vote != 'up':
                thread.rating -= 2
                action.isupvote = False
                db.session.commit()
            elif not action.isupvote and vote == 'up':
                thread.rating += 2
                action.isupvote = True
                db.session.commit()
            else:
                return redirect(url_for('badrequest'))
        else:
            if vote == 'up':
                thread.rating += 1
                action = UserAction(user_id, thread_id, True)
                db.session.add(action)
                db.session.commit()
            elif vote == 'down':
                thread.rating -= 1
                action = UserAction(user_id, thread_id, False)
                db.session.add(action)
                db.session.commit()
            else:
                return redirect(url_for('badrequest'))
        json_str = json.dumps({"new_rating":thread.rating, "thread_id":thread.id})
        return json_str
    return redirect(url_for('badrequest'))
    

@app.route('/newpost', methods=['GET', 'POST'])
def newpost():
    if request.method == 'GET':
        if not current_user.is_authenticated:
            return redirect(url_for('index'))
        return render_template('newpost.html')
    if request.form.get('threadTitle', None) is not None and request.form.get('descText', None) is not None:
        title = request.form['threadTitle']
        if 'photo' in request.files:
            filename = photos.save(request.files['photo'], name=random_word() + ".jpg")
        else:
            filename = ""
        user_name = current_user.name
        desc = request.form['descText']
        thread = Thread(filename, user_name, title, desc)
        db.session.add(thread)
        db.session.commit()
        return redirect(url_for('index'))
    return redirect(url_for('badrequest'))


@app.route('/thread/<int:thread_id>', methods=['GET', 'POST'])
def thread(thread_id):
    if request.method == 'GET':
        comments = Commentary.query.filter_by(thread=thread_id)
        thread = Thread.query.filter_by(id=thread_id).first()
        if thread is None:
            return render_template('404.html')
        return render_template('thread.html', **locals())
    if request.form.get('vote', None) is not None and request.form.get('user_id', None) is not None:
        user_id = current_user.get_id()
        vote = request.form['vote']
        action = UserAction.query.filter_by(thread=thread_id, user=user_id).first()
        thread = Thread.query.filter_by(id=thread_id).first()
        if action is not None:
            if action.isupvote and vote != 'up':
                thread.rating -= 2
                action.isupvote = False
                db.session.commit()
            elif not action.isupvote and vote == 'up':
                thread.rating += 2
                action.isupvote = True
                db.session.commit()
        else:
            if vote == 'up':
                thread.rating += 1
                action = UserAction(user_id, thread_id, True)
                db.session.add(action)
                db.session.commit()
            elif vote == 'down':
                thread.rating -= 1
                action = UserAction(user_id, thread_id, False)
                db.session.add(action)
                db.session.commit()
        json_str = json.dumps({"new_rating":thread.rating, "thread_id":thread.id})
        return json_str
    if request.form.get('comText', None) is not None:
        comText = request.form['comText']
        if 'photo' in request.files:
            filename = photos.save(request.files['photo'], name=random_word() + ".jpg")
        else:
            filename = ""
        if comText != "" or filename != "":
            com = Commentary(filename, current_user.name, comText, thread_id)
            db.session.add(com)
            db.session.commit()
        return redirect(url_for('thread', thread_id=thread_id))
    return redirect(url_for('badrequest'))


@app.route('/login',methods=['GET','POST'])
def login():
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        return render_template('login.html')
    if request.form.get('inputEmail', None) is not None and request.form.get('inputPassword', None) is not None:
        email = request.form['inputEmail']
        password = request.form['inputPassword']
        registered_user = User.query.filter_by(email=email).first()
        if registered_user is None or not hashpw(password, registered_user.password) != registered_user.password:
            flash('Email or Password is invalid')
            return redirect(url_for('login'))
        login_user(registered_user, remember=True)
        return redirect(url_for('index'))
    return redirect(url_for('badrequest'))
    
    
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'GET':
        if not current_user.is_authenticated:
            return redirect(url_for('index'))
        return render_template('settings.html') 
    if request.form.get('inputPassword', None) is not None and request.form.get('repeatPassword', None) is not None\
    and request.form.get('oldPassword', None) is not None:
        old_password = request.form['oldPassword']
        new_password = request.form['newPassword']
        strength, improvements = passwordmeter.test(old_password)
        if strength < 0.5:
            flash('Password is too weak')
            return redirect(url_for('settings')) 
        if hashpw(old_password, current_user.password):
            current_user.password = hashpw(new_password, gensalt())
            db.session.commit()
        else:
            flash('Old password is invalid')
            return redirect(url_for('settings'))
        return redirect(url_for('settings'))
    if request.form.get('oldEmail', None) is not None and request.form.get('newEmail', None) is not None:
        old_email = request.form['oldEmail']
        new_email = request.form['newEmail']
        if current_user.email == old_email:
            if User.query.filter_by(email=new_email).first() is not None:
                flash('Email already taken')
                return redirect(url_for('settings'))
            current_user.email = new_email
            db.session.commit()
        else:
            flash('Old email is invalid')
        return redirect(url_for('settings'))
    if request.form.get('inputName', None) is not None:
        new_name = redirect.form['inputName']
        if User.query.filter_by(name=new_name).first() is not None:
            flash('Username already taken')
            return redirect(url_for('settings'))
        current_user.name = new_name
        db.session.commit()
        return redirect(url_for('settings'))
    return redirect(url_for('badrequest'))


@app.route('/badrequest')
def badrequest():
    return render_template('badrequest.html')


@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        return render_template('signup.html')
    if request.form.get('inputName', None) is not None and request.form.get('inputPassword', None) is not None\
    and request.form.get('inputEmail', None) is not None and request.form.get('repeatPassword', None) is not None:
        name = request.form['inputName']
        password = request.form['inputPassword']
        email = request.form['inputEmail']
        repeat_password = request.form['repeatPassword']
        strength, improvements = passwordmeter.test(password)
        if strength < 0.5:
            flash('Password is too weak')
            return redirect(url_for('signup')) 
        if User.query.filter_by(email=email).first() is not None:
            flash('Email is already used')
            return redirect(url_for('signup'))
        if not validate_email(email, verify=True):
            flash('Email is not valid')
            return redirect(url_for('signup'))
        if User.query.filter_by(name=name).first() is not None:
            flash('Username is already taken')
            return redirect(url_for('signup'))
        if password != repeat_password:
            flash('Passwords do not match')
            return redirect(url_for('signup'))
        if len(password) < 8:
            flash('Password must be at least 8 characters long')
            return redirect(url_for('signup'))
        if len(name) >= 20:
            flash('Username must be less than 20 characters long') 
            return redirect(url_for('signup'))

        user = User(name, password, email)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return redirect(url_for('badrequest'))

@app.route('/logout')
def logout():
    if not current_user.is_authenticated:
        return redirect(url_for('index'))
    logout_user()
    return redirect(url_for('index'))


@app.before_request
def before_request():
    g.user = current_user


#----------APP ROUTES & STUFF ENDED----------

db.create_all()