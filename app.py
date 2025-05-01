from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from PIL import Image
import pytesseract
from deep_translator import GoogleTranslator
from gtts import gTTS
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from flask import g
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.secret_key = 'your_secret_key'

socketio = SocketIO(app)
DATABASE = 'vocabulary.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@socketio.on('send_message')
def handle_send_message(data):
    sender_id = session.get('user_id')
    receiver_id = data['receiver_id']
    message = data['message']

    # Save to database
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messages (sender_id, receiver_id, message)
        VALUES (?, ?, ?)
    ''', (sender_id, receiver_id, message))
    conn.commit()
    conn.close()

    # Emit to sender and receiver
    emit('receive_message', {
        'sender_id': sender_id,
        'receiver_id': receiver_id,
        'message': message
    }, room=f"user_{receiver_id}")

    emit('receive_message', {
        'sender_id': sender_id,
        'receiver_id': receiver_id,
        'message': message
    }, room=f"user_{sender_id}")

translator = GoogleTranslator(source='fr', target='en')

@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
# Initialize SQLite Database
def initialize_database():
    conn = sqlite3.connect("vocabulary.db")
    cursor = conn.cursor()
    
    # Create Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    
    # Create Vocabulary Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vocabulary (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            word TEXT,
            translation TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    # ✅ Create Friendships Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS friendships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            friend_id INTEGER NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('pending', 'accepted', 'rejected')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (friend_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

# Add word to vocabulary for a specific user
def add_to_vocabulary(user_id, word, translation):
    conn = sqlite3.connect("vocabulary.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO vocabulary (user_id, word, translation) VALUES (?, ?, ?)", (user_id, word, translation))
    conn.commit()
    conn.close()

# Get vocabulary for a specific user
def get_vocabulary(user_id):
    conn = sqlite3.connect("vocabulary.db")
    cursor = conn.cursor()
    cursor.execute("SELECT word, translation FROM vocabulary WHERE user_id = ?", (user_id,))
    vocab = cursor.fetchall()
    conn.close()
    return vocab

# User Signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect('vocabulary.db')
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()

            cursor.execute('SELECT id, username, avatar FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()

            session['user_id'] = user[0]
            session['username'] = user[1]
            session['avatar'] = user[2] if user[2] else 'static/avatars/default.png'

            conn.close()
            return redirect(url_for('index'))
        except sqlite3.IntegrityError:
            conn.close()
            return "Username already exists."

    return render_template('signup.html')

# User Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('vocabulary.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, password, avatar FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['avatar'] = user[3] if user[3] else 'static/avatars/default.png'
            print("hellllooooo")
            print(session['user_id'], session['username'])
            return redirect(url_for('index'))
        else:
            return "Invalid credentials."
        
        

    return render_template('login.html')

# User Logout
@app.route('/logout')
def logout():
    session.pop('user_id', None)  # Remove user ID from session
    return redirect(url_for('login'))

# Routes
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    image = Image.open(file.stream)
    text = pytesseract.image_to_string(image)
    return jsonify({'text': text})

@app.route('/translate', methods=['POST'])
def translate():
    data = request.get_json()
    word = data.get('word', '').strip()
    source_lang = data.get('sourceLang', 'auto')  # Default to 'auto' if not provided
    target_lang = data.get('targetLang', 'en')  # Default to English if not provided
    
    if not word:
        return jsonify({'error': 'No word provided'}), 400

    # Translate the word using the selected languages
    try:
        translation = GoogleTranslator(source=source_lang, target=target_lang).translate(word)
    except Exception as e:
        return jsonify({'error': f'Failed to translate: {str(e)}'}), 500

    return jsonify({'translation': translation})

@app.route('/pronounce', methods=['POST'])
def pronounce():
    data = request.get_json()
    word = data.get('word', '').strip()
    if not word:
        return jsonify({'error': 'No word provided'}), 400
    tts = gTTS(text=word, lang='fr')
    tts.save("static/word.mp3")
    return jsonify({'audio': 'static/word.mp3'})

@app.route('/save', methods=['POST'])
def save_word():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 400

    data = request.get_json()
    word = data.get('word', '').strip()
    translation = data.get('translation', '').strip()

    if not word or not translation:
        return jsonify({'error': 'Invalid data'}), 400

    user_id = session['user_id']
    add_to_vocabulary(user_id, word, translation)
    return jsonify({'message': 'Word saved successfully'})

@app.route('/vocabulary')
def view_vocabulary():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    vocab = get_vocabulary(user_id)
    return render_template('vocabulary.html', vocab=vocab)


@app.route('/friends', methods=['GET', 'POST'])
def friends():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()

    search_query = request.args.get('search')

    # Get accepted friends
    cursor.execute('''
        SELECT u.id, u.username FROM users u
        JOIN friendships f ON (f.friend_id = u.id OR f.user_id = u.id)
        WHERE (f.user_id = ? OR f.friend_id = ?) AND f.status = 'accepted' AND u.id != ?
    ''', (user_id, user_id, user_id))
    friends = cursor.fetchall()

    # Get pending friend requests
    cursor.execute('''
        SELECT f.id, u.username FROM friendships f
        JOIN users u ON f.user_id = u.id
        WHERE f.friend_id = ? AND f.status = 'pending'
    ''', (user_id,))
    requests = cursor.fetchall()

    # Search or show all users
    if search_query:
        cursor.execute('''
            SELECT id, username FROM users
            WHERE id != ? AND username LIKE ?
        ''', (user_id, f'%{search_query}%'))
    else:
        cursor.execute('''
            SELECT id, username FROM users
            WHERE id != ?
        ''', (user_id,))
    all_users = cursor.fetchall()

    conn.close()

    return render_template('friends.html', 
                           friends=friends,
                           requests=requests,
                           all_users=all_users,
                           search_query=search_query)

@app.route('/add_friend/<int:friend_id>')
def add_friend(friend_id):
    print("helllloooo\n")
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM friendships WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)
    ''', (user_id, friend_id, friend_id, user_id))
    existing = cursor.fetchone()

    if not existing:
        cursor.execute('''
            INSERT INTO friendships (user_id, friend_id, status)
            VALUES (?, ?, 'pending')
        ''', (user_id, friend_id))
        conn.commit()
        
    return redirect(url_for('friends'))

@app.route('/accept_friend/<int:friendship_id>')
def accept_friend(friendship_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE friendships SET status = 'accepted' WHERE id = ?
    ''', (friendship_id,))
    conn.commit()

    return redirect(url_for('friends'))

@app.route('/reject_friend/<int:friendship_id>')
def reject_friend(friendship_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE friendships SET status = 'rejected' WHERE id = ?
    ''', (friendship_id,))
    conn.commit()

    return redirect(url_for('friends'))

@app.route('/chat/<int:friend_id>')
def chat(friend_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()

    # Make sure the two users are friends
    cursor.execute('''
        SELECT * FROM friendships
        WHERE (
            (user_id = ? AND friend_id = ?) OR
            (user_id = ? AND friend_id = ?)
        ) AND status = 'accepted'
    ''', (user_id, friend_id, friend_id, user_id))
    friendship = cursor.fetchone()

    if not friendship:
        return "You are not friends with this user.", 403

    # Get chat history
    cursor.execute('''
        SELECT sender_id, message, timestamp FROM messages
        WHERE (sender_id = ? AND receiver_id = ?)
           OR (sender_id = ? AND receiver_id = ?)
        ORDER BY timestamp ASC
    ''', (user_id, friend_id, friend_id, user_id))
    chat_history = cursor.fetchall()

    # Get friend's username
    cursor.execute('SELECT username FROM users WHERE id = ?', (friend_id,))
    friend_username = cursor.fetchone()

    # ✅ Get vocabulary list to send as cards
    cursor.execute('SELECT word, translation FROM vocabulary WHERE user_id = ?', (user_id,))
    vocab_cards = cursor.fetchall()

    conn.close()

    return render_template('chat.html',
                           chat_history=chat_history,
                           friend_username=friend_username[0],
                           friend_id=friend_id,
                           vocab_cards=vocab_cards)

@app.route('/chats')
def chats():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.username FROM users u
        JOIN friendships f ON (f.friend_id = u.id OR f.user_id = u.id)
        WHERE (f.user_id = ? OR f.friend_id = ?) AND f.status = 'accepted' AND u.id != ?
    ''', (user_id, user_id, user_id))
    friends = cursor.fetchall()
    return render_template('chats.html', friends=friends)

@app.route('/profile/<int:user_id>')
def profile(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT username, avatar, about_me FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return "User not found.", 404

    return render_template('profile.html',
                           username=user[0],
                           avatar=user[1],
                           about_me=user[2],
                           user_id=user_id)


@app.route('/save_profile_field', methods=['POST'])
def save_profile_field():
    if 'user_id' not in session:
        return jsonify({'success': False}), 403

    data = request.get_json()
    field = data.get('field')
    value = data.get('value')

    if field not in ['username', 'about_me']:
        return jsonify({'success': False}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(f'''
        UPDATE users SET {field} = ?
        WHERE id = ?
    ''', (value, session['user_id']))
    conn.commit()
    conn.close()

    if field == 'username':
        session['username'] = value

    return jsonify({'success': True})

@app.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    if 'user_id' not in session:
        return jsonify({'success': False}), 403

    avatar_file = request.files.get('avatar')
    if not avatar_file or avatar_file.filename == '':
        return jsonify({'success': False}), 400

    avatar_filename = f"static/avatars/user_{session['user_id']}_{avatar_file.filename}"
    avatar_file.save(avatar_filename)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET avatar = ? WHERE id = ?', (avatar_filename, session['user_id']))
    conn.commit()
    conn.close()

    session['avatar'] = avatar_filename

    return jsonify({'success': True})

if __name__ == '__main__':
    initialize_database()
    socketio.run(app, debug=True, port=5001)