import os
import json

from flask import Flask, request
from flask.views import MethodView
from flask_jwt import JWT, jwt_required, current_identity
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///podcasts.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'my-secret'
db = SQLAlchemy(app)


def authenticate(username, password):
    return Account.query.filter_by(username=username, password=password).first()


def identity(payload):
    user_id = payload['identity']
    return Account.query.filter_by(id=user_id).first()


jwt = JWT(app, authenticate, identity)


class Serializable(object):
    def serialize(self):
        return {k.name: getattr(self, k.name) for k in self.__table__.columns}


class Account(db.Model, Serializable):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return '<User %r>' % self.username


class Content(db.Model, Serializable):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))
    preview_path = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.Text)

    categories = db.relationship('Category', secondary='content_categories', lazy='subquery')

    def __repr__(self):
        return '<Content %r>' % self.file_path


class Category(db.Model, Serializable):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))

    def __repr__(self):
        return '<Category %r>' % self.title


content_categories = db.Table('content_categories',
    db.Column('category_id', db.Integer, db.ForeignKey('category.id'), primary_key=True),
    db.Column('content_id', db.Integer, db.ForeignKey('content.id'), primary_key=True)
)


class PodcastMethodView(MethodView):
    _decorators = {}

    def dispatch_request(self, *args, **kwargs):
        """Derived MethodView dispatch to allow for decorators to be
            applied to specific individual request methods - in addition
            to the standard decorator assignment.

            Example decorator use:
            decorators = [user_required] # applies to all methods
            _decorators = {
                'post': [admin_required, format_results]
            }
        """

        view = super().dispatch_request
        decorators = self._decorators.get(request.method.lower())
        if decorators:
            for decorator in decorators:
                view = decorator(view)

        return view(*args, **kwargs)


class AccountEP(PodcastMethodView):
    _decorators = {
        'get': [jwt_required()]
    }

    def get(self):
        ret = current_identity.serialize()
        del ret['password']
        return ret

    def post(self):
        account = Account(**request.get_json())
        db.session.add(account)
        db.session.commit()
        return {}, 201


class ContentEP(PodcastMethodView):
    _decorators = {
        'get': [jwt_required()]
    }

    def get(self):
        return json.dumps([c.serialize() for c in Content.query.all()])


app.add_url_rule('/account/', view_func=AccountEP.as_view('account'))
app.add_url_rule('/content/', view_func=ContentEP.as_view('content'))
