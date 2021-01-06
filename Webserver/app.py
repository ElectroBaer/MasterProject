from flask import Flask, jsonify, request, render_template, redirect
from flask_httpauth import HTTPBasicAuth, HTTPTokenAuth
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import os

from config import Config
from auth_requests import *

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'zip', 'mkv', 'csv'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

basic_auth = HTTPBasicAuth()
token_auth = HTTPTokenAuth('Bearer')

config = Config()
open_auth_requests = AuthRequests()


def is_allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@token_auth.verify_token
def verify_token(token):
    print('verify: ', token)
    if token == config.client_secret:
        return 'authenticated'


@basic_auth.verify_password
def verify_password(username, password):
    if username == config.user and password == config.user_pw:
        return username


@app.route('/')
def hello_world():
    return 'Hello World!'


@app.route('/auth/request/')
def request_token():
    identifier = request.args.get('identifier')
    if identifier is None or identifier == '':
        return jsonify({'status': 'error', 'msg': 'no identifier'})

    auth_request: AuthRequest = open_auth_requests.get_request(identifier)
    if auth_request is None:
        open_auth_requests.new_request(identifier)
        return jsonify({'status': 'new', 'msg': 'created request'})

    else:
        if not auth_request.granted:
            return jsonify({'status': 'pending', 'msg': 'waiting for confirmation'})
        else:
            return jsonify({'status': 'grant', 'token': config.client_secret})


@app.route('/auth/check/')
@basic_auth.login_required
def get_open_auth_requests():
    return render_template('list_requests.html', open_requests=open_auth_requests.open_auth_requests)


@app.route('/auth/grant/<int:auth_id>/')
@basic_auth.login_required
def grant_auth_request(auth_id):
    auth_request = open_auth_requests.get_by_id(auth_id)
    if auth_request is not None:
        auth_request.granted = True
    return redirect('/auth/check/')


@app.route('/recording/new/', methods=['GET', 'POST'])
@token_auth.login_required
def new_recording():
    # secret_token = request.args.get('token')
    # if secret_token is None or secret_token != config.client_secret:
    #     return jsonify({'status': 'not authenticated'})

    print('User: ', token_auth.current_user())

    if request.method == 'GET':
        new_uuid = uuid.uuid4()
        print('Deliver new uuid:', new_uuid)
        return jsonify({'status': 'success', 'uuid': new_uuid})
    elif request.method == 'POST':
        print('Get new records')
        request_uuid = request.args.get('uuid')
        print('Id: ', request_uuid)
        if request_uuid is None or request_uuid == '':
            print('No uuid')
            return jsonify({'status': 'error, now uuid'})
        if 'file' not in request.files:
            print('No file part')
            return jsonify({'status': 'error, now file'})
        file = request.files['file']
        if file.filename == '':
            print('No selected file')
            return jsonify({'status': 'error, now selected file'})
        if file and is_allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], request_uuid)
            if not os.path.isdir(upload_path):
                os.mkdir(upload_path)
            file.save(os.path.join(upload_path, filename))
            return jsonify({'status': 'success, uploaded ' + file.filename})

        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'})


if __name__ == '__main__':
    app.run()