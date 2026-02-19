from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_file, send_from_directory
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_wtf import CSRFProtect
import secrets
import uuid
import html

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE='Strict'
)

csrf = CSRFProtect(app)
    
# Initialize database
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
             username TEXT, 
             email TEXT, 
             password TEXT, 
             phone TEXT,
             profile_photo TEXT)''')  
    
    c.execute('''CREATE TABLE IF NOT EXISTS posts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 title TEXT,
                 content TEXT,
                 user_id INTEGER)''')

    c.execute('''CREATE TABLE IF NOT EXISTS comments (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             comment_text TEXT NOT NULL,
             user_id INTEGER,
             post_id INTEGER
             )''')    
    
    # Add some sample data if empty
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        
        admin_pw = generate_password_hash('admin123')
        user1_pw = generate_password_hash('user123')
        
        c.execute("INSERT INTO users (username, email, password, phone) VALUES (?, ?, ?, ?)",
                  ('admin', 'admin@example.com', admin_pw, '1234567890'))
        c.execute("INSERT INTO users (username, email, password, phone) VALUES (?, ?, ?, ?)",
                  ('user1', 'user1@example.com', user1_pw, '0987654321'))
        
    c.execute("SELECT COUNT(*) FROM posts")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO posts (title, content, user_id) VALUES (?, ?, ?)",
                  ('First Post', 'This is the first blog post content.', 1))
        c.execute("INSERT INTO posts (title, content, user_id) VALUES (?, ?, ?)",
                  ('Second Post', 'This is the second blog post content.', 2))
    
    conn.commit()
    conn.close()

init_db()

# ----------------------------------------------------------------------------------------------------

def get_user_by_id(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_posts():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("""
        SELECT posts.*, users.username, users.profile_photo 
        FROM posts 
        JOIN users ON posts.user_id = users.id
    """)
    posts = c.fetchall()
    conn.close()
    return posts

def search_posts(query):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # The SQL string stays clean of variables
    sql = """
        SELECT posts.*, users.username 
        FROM posts 
        JOIN users ON posts.user_id = users.id 
        WHERE posts.title LIKE ? OR posts.content LIKE ?
        ORDER BY posts.id DESC
    """
    # Wrap the query in % for the LIKE operator
    search_param = f"%{query}%"
    c.execute(sql, (search_param, search_param))
    posts = c.fetchall()
    conn.close()
    return posts

def update_password(user_id, new_password):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, user_id))
    conn.commit()
    conn.close()

def create_user(username, email, password, phone):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()    
    c.execute("INSERT INTO users (username, email, password, phone) VALUES (?, ?, ?, ?)", (username, email, password, phone))
    conn.commit()
    user_id = c.lastrowid
    conn.close()
    return user_id


def add_post(title, content, user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO posts (title, content, user_id) VALUES (?, ?, ?)",
              (title, content, user_id))
    conn.commit()
    conn.close()


def add_comment(comment_text, user_id, post_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO comments (comment_text, user_id, post_id) VALUES (?, ?, ?)",
              (comment_text, user_id, post_id))
    conn.commit()
    conn.close()


def get_comments(post_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("""
        SELECT comments.comment_text, users.username, users.profile_photo 
        FROM comments 
        JOIN users ON comments.user_id = users.id 
        WHERE comments.post_id = ?
    """, (post_id,))
    comments = c.fetchall()
    conn.close()
    return comments

# ----------------------------------------------------------------------------------------------------

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        
        hashed_pw = generate_password_hash(password)

        user_id = create_user(username, email, hashed_pw, phone)
        flash('Registration successful!', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        flash('User not found. Please login again.', 'error')
        return redirect(url_for('login'))
    
    posts = get_posts()
    
    return render_template('dashboard.html', user=user, posts=posts)

@app.route('/profile/<int:user_id>')
def profile(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = get_user_by_id(user_id)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('dashboard'))

    # Only show sensitive fields to the profile owner
    is_owner = session['user_id'] == user_id

    # Sanitize profile photo filename to prevent path traversal
    user_list = list(user)
    user_list[5] = secure_filename(user_list[5]) if user_list[5] else None

    if not is_owner:
        # Hide email and phone from other users
        user_list[2] = None  # email
        user_list[4] = None  # phone

    user = tuple(user_list)
    return render_template('profile.html', user=user, is_owner=is_owner)

@app.route('/upload', methods=['POST'])
@csrf.exempt
def upload_file():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    file = request.files.get('file')
    if file and file.filename != '':
        # Clean the filename to prevent path traversal
        original_name = secure_filename(file.filename)
        extension = original_name.rsplit('.', 1)[1].lower() if '.' in original_name else 'jpg'
        
        # Unique name based on user ID
        new_filename = f"user_{session['user_id']}.{extension}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))
        
        # Update DB... (same as your code)
        flash('Photo updated!', 'success')
        
    return redirect(url_for('profile', user_id=session['user_id']))

@app.route('/static/uploads/<filename>')
def serve_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], secure_filename(filename))

@app.route('/login', methods=['GET', 'POST'])
@csrf.exempt
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # 1. Fetch by username only (Safe)
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        # 2. Secure verification
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['session_id'] = str(uuid.uuid4()) # Your UUID library
            flash('Welcome back!', 'success')
            return redirect(url_for('dashboard'))
        
        flash('Invalid credentials.', 'error')
    return render_template('login.html')

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Hash the new password before storing it!
    new_password = request.form['new_password']
    hashed_pw = generate_password_hash(new_password)
    
    update_password(session['user_id'], hashed_pw)
    
    flash('Password updated safely!', 'success')
    return redirect(url_for('profile', user_id=session['user_id']))

@app.route('/search')
def search():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    raw_query = request.args.get('q', '')

    sanitized_query = html.escape(raw_query).strip()

    if sanitized_query:
        posts = search_posts(sanitized_query)
    else:
        posts = []
    
    return render_template('search.html', posts=posts, query=sanitized_query)
@app.route('/images')
def get_image():
    # Grab the filename from the URL
    image = request.args.get('image', '')
    
    # SENIOR FIX: Clean the filename! 
    # This turns "../../../etc/passwd" into "etc_passwd"
    safe_image_name = secure_filename(image)
    
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_image_name)
    
    if safe_image_name and os.path.isfile(image_path):
        return send_file(image_path)

    return abort(404, "Image not found")

@app.route('/create_post', methods=['GET', 'POST'])
def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        add_post(title, content, session['user_id'])
        flash('Post created!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('create_post.html')


@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("""
        SELECT posts.*, users.username, users.profile_photo 
        FROM posts 
        JOIN users ON posts.user_id = users.id 
        WHERE posts.id = ?""", (post_id,))
    post = c.fetchone()
    conn.close()

    if not post:
        flash('Post not found.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        content = request.form['comment']
        add_comment(content, session['user_id'], post_id)
        flash('Comment added!', 'success')
        return redirect(url_for('view_post', post_id=post_id))

    comments = get_comments(post_id)
    return render_template('view_post.html', post=post, comments=comments)


@app.route('/comment/<int:post_id>', methods=['POST'])
@csrf.exempt
def add_comment(post_id):
    if 'user_id' not in session:
        flash('You must be logged in to comment.', 'error')
        return redirect(url_for('login'))

    comment_text = request.form.get('comment_text')

    if not comment_text:
        flash('Comment cannot be empty.', 'error')
        return redirect(url_for('view_post', post_id=post_id))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO comments (comment_text, user_id, post_id) VALUES (?, ?, ?)", 
              (comment_text, session['user_id'], post_id))
    conn.commit()
    conn.close()

    flash('Comment added successfully.', 'success')
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/feedback')
def feedback():
    return render_template('feedback.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
