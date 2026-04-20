from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'txt', 'pdf', 'doc', 'docx'}

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    # Create messages table if it doesn't exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user TEXT NOT NULL,
            to_user TEXT,
            message TEXT,
            file_path TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Check if file_path column exists (from previous step)
    c.execute("PRAGMA table_info(messages)")
    columns = [column[1] for column in c.fetchall()]
    if 'file_path' not in columns:
        c.execute('ALTER TABLE messages ADD COLUMN file_path TEXT')
    
    # Add is_read column if it doesn't exist
    if 'is_read' not in columns:
        c.execute('ALTER TABLE messages ADD COLUMN is_read INTEGER DEFAULT 0')

    conn.commit()
    conn.close()

def index():
    if 'username' not in session:
        return render_template('index.html', username=None)

    username = session['username']
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if request.method == 'POST':
        to_user = request.form.get('to_user')
        message = request.form.get('message')
        file = request.files.get('file')
        
        if not to_user:
            to_user = None

        file_path = None
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            file_path = os.path.join('uploads', filename).replace('\\', '/')

        if message or file_path:
            c.execute("INSERT INTO messages (from_user, to_user, message, file_path) VALUES (?, ?, ?, ?)",
                      (username, to_user, message, file_path))
            conn.commit()
        
        conn.close()
        
        if to_user:
            return redirect(url_for('index', to=to_user))
        return redirect(url_for('index'))

    c.execute("SELECT username FROM users WHERE username != ?", (username,))
    users = [row['username'] for row in c.fetchall()]

    active_chat = request.args.get('to')

    # Mark messages as read when viewing the chat
    if active_chat:
        c.execute("""
            UPDATE messages SET is_read = 1 
            WHERE to_user = ? AND from_user = ? AND is_read = 0
        """, (username, active_chat))
        conn.commit()
        c.execute("""
            SELECT * FROM messages 
            WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
            ORDER BY timestamp ASC
        """, (username, active_chat, active_chat, username))
    else:
        c.execute("""
            UPDATE messages SET is_read = 1 
            WHERE to_user IS NULL AND is_read = 0 AND from_user != ?
        """, (username,))
        conn.commit()
        c.execute("SELECT * FROM messages WHERE to_user IS NULL ORDER BY timestamp ASC")
    
    messages = c.fetchall()
    conn.close()
    
    return render_template('index.html', username=username, messages=messages, users=users, active_chat=active_chat)

def check_new_messages():
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    username = session['username']

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Find unread messages addressed to the current user
    c.execute("""
        SELECT from_user, to_user FROM messages 
        WHERE (to_user = ? OR to_user IS NULL) AND is_read = 0 AND from_user != ?
    """, (username, username))
    
    new_messages_info = c.fetchall()
    conn.close()

    senders = set()
    for msg in new_messages_info:
        if msg['to_user'] is None:
            senders.add('general')
        else:
            senders.add(msg['from_user'])
            
    return jsonify({'new_messages_from': list(senders)})

def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()
        
        if user:
            session['username'] = user[1]
            return redirect(url_for('index'))
        else:
            return "Неверный логин или пароль"
            
    return render_template('login.html')

def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
        except sqlite3.IntegrityError:
            return "Такой пользователь уже существует"
        finally:
            conn.close()
            
        return redirect(url_for('login'))
    return render_template('register.html')

def service_worker():
    return send_from_directory(app.static_folder, 'sw.js')

app.add_url_rule('/', 'index', index, methods=['GET', 'POST'])
app.add_url_rule('/login', 'login', login, methods=['GET', 'POST'])
app.add_url_rule('/logout', 'logout', logout)
app.add_url_rule('/register', 'register', register, methods=['GET', 'POST'])
app.add_url_rule('/check_new_messages', 'check_new_messages', check_new_messages)
app.add_url_rule('/sw.js', 'service_worker', service_worker)

if __name__ == '__main__':
    init_db()
    context = ('cert.pem', 'key.pem')
    app.run(host='0.0.0.0', port=5050, debug=True,ssl_context=context)
