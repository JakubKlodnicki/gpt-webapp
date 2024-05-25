from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import json
import logging
from chat import handle_chat, handle_file_upload, generate_image

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['UPLOAD_FOLDER'] = 'uploads/'

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  

logging.basicConfig(level=logging.INFO)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    messages = db.Column(db.Text, nullable=True)

    user = db.relationship('User', backref=db.backref('chats', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    chats = Chat.query.filter_by(user_id=current_user.id).all()
    return render_template('index.html', chats=chats)

@app.route('/chat', methods=['POST'])
@login_required
def chat_default():
    data = request.get_json()
    user_input = data.get('user_input', '')
    gpt_version = data.get('gpt_version', 'gpt-3.5-turbo')

    active_chat_id = session.get('active_chat_id')
    if not active_chat_id:
        return jsonify({'error': 'No active chat. Please start a new chat session.'}), 400

    active_chat = db.session.get(Chat, active_chat_id)
    
    try:
        chat_history = json.loads(active_chat.messages)
    except:
        chat_history = []

    file_analysis = session.get(f'file_analysis_{current_user.id}', '')
    if file_analysis:
        chat_history.append({"role": "system", "content": f"File analysis: {file_analysis}"})
        session.pop(f'file_analysis_{current_user.id}', None)

    chat_history.append({"role": "user", "content": user_input})

    response = handle_chat(user_input, chat_history, gpt_version)
    active_chat.messages = json.dumps(response['chat_history'])
    if not active_chat.title:
        active_chat.title = user_input[:20]  
    db.session.commit()

    return jsonify({'reply': response['reply'], 'chat_history': response['chat_history'], 'new_chat_id': active_chat.id})

@app.route('/chat/<int:chat_id>', methods=['GET'])
@login_required
def chat(chat_id):
    chat = db.session.get(Chat, chat_id)
    if chat.user_id != current_user.id:
        return redirect(url_for('index'))
    try:
        messages = json.loads(chat.messages)
    except:
        messages = []
    return render_template('index.html', chats=current_user.chats, messages=messages, chat=chat)

@app.route('/chat/<int:chat_id>', methods=['POST'])
@login_required
def post_chat(chat_id):
    chat = db.session.get(Chat, chat_id)
    if chat.user_id != current_user.id:
        return redirect(url_for('index'))
    
    data = request.get_json()
    user_input = data.get('user_input')
    gpt_version = data.get('gpt_version', 'gpt-3.5-turbo')
    
    try:
        chat_history = json.loads(chat.messages)
    except:
        chat_history = []

    chat_history.append({"role": "user", "content": user_input})

    result = handle_chat(user_input, chat_history, gpt_version=gpt_version)
    
    chat.messages = json.dumps(result['chat_history'])
    if not chat.title:
        chat.title = user_input[:20]  
    db.session.commit()

    return jsonify({'reply': result['reply'], 'chat_history': result['chat_history'], 'new_chat_id': chat_id})

@app.route('/new_chat', methods=['POST'])
@login_required
def new_chat():
    active_chat = Chat(user_id=current_user.id, title='', messages='[]')
    db.session.add(active_chat)
    db.session.commit()
    session['active_chat_id'] = active_chat.id
    return jsonify({'new_chat_id': active_chat.id})

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'})
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        analysis = handle_file_upload(file_path)
        
        
        chat_id = request.form.get('chat_id') or session.get('active_chat_id')
        chat = db.session.get(Chat, chat_id)

        try:
            chat_history = json.loads(chat.messages)
        except:
            chat_history = []

        chat_history.append({"role": "assistant", "content": f"File analysis:\n{analysis}"})
        chat.messages = json.dumps(chat_history)
        db.session.commit()

        return jsonify({'analysis': analysis})
    return jsonify({'error': 'File type not allowed'})

@app.route('/reset', methods=['POST'])
@login_required
def reset():
    session.pop('chat_history', None)
    session.pop('active_chat_id', None)
    return jsonify({'message': 'Session has been reset.'})

@app.route('/delete_chat/<int:chat_id>', methods=['POST'])
@login_required
def delete_chat(chat_id):
    chat = db.session.get(Chat, chat_id)
    if chat.user_id == current_user.id:
        db.session.delete(chat)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/generate_image', methods=['POST'])
@login_required
def generate_image_route():
    data = request.get_json()
    prompt = data.get('prompt', '')
    chat_id = data.get('chat_id')

    if not chat_id:
        return jsonify({'error': 'No active chat. Please start a new chat session.'}), 400

    image_url = generate_image(prompt)

    chat = db.session.get(Chat, chat_id)
    try:
        chat_history = json.loads(chat.messages)
    except:
        chat_history = []

    chat_history.append({"role": "assistant", "content": f'<img src="{image_url}" alt="Generated Image">'})
    chat.messages = json.dumps(chat_history)
    db.session.commit()

    return jsonify({'image_url': image_url})


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'csv'}

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000, host='0.0.0.0')
