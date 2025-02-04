from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from PIL import Image
import pytesseract
from deep_translator import GoogleTranslator
from gtts import gTTS
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a strong secret key

translator = GoogleTranslator(source='fr', target='en')

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

        conn = sqlite3.connect("vocabulary.db")
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "Username already exists, please choose another one."

    return render_template('signup.html')

# User Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect("vocabulary.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):  # user[2] is the password column
            session['user_id'] = user[0]  # Store user ID in session
            return redirect(url_for('index'))
        else:
            return "Invalid credentials, please try again."

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

if __name__ == '__main__':
    initialize_database()
    app.run(debug=True)