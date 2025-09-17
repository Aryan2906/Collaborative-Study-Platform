import os
import json
import time
import random
import re
from threading import Thread

from flask import Flask, request, render_template, session, redirect, url_for, flash, jsonify
from flask_socketio import join_room, leave_room, SocketIO, emit

import eventlet
eventlet.monkey_patch()

import firebase_admin
from firebase_admin import credentials, auth, firestore

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ------------------- Flask App Setup -------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# ------------------- Firebase Setup -------------------
db = None

def init_firebase():
    """Lazy Firebase initialization, safe for multiple calls."""
    global db
    if db:
        return db
    try:
        if not firebase_admin._apps:
            cred_json = os.environ.get('FIREBASE_CREDENTIALS', '{}')
            cred_dict = json.loads(cred_json)
            if not cred_dict:
                raise ValueError("Firebase credentials missing or empty")
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("[Firebase] Initialized successfully")
        return db
    except Exception as e:
        db = None
        print(f"[Firebase] Initialization failed: {e}")
        return None  # don’t crash the app

# ------------------- YouTube API -------------------
API_KEY = "AIzaSyAav6iqs8d6XyLztW2oGeiR5rv2kNJW6JI"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

def get_video_id_from_search(query: str):
    if not query.strip(): return None, "Search query cannot be empty."
    try:
        youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
        response = youtube.search().list(q=query, part="snippet", maxResults=1, type="video").execute()
        items = response.get("items", [])
        return (items[0]["id"]["videoId"], None) if items else (None, f"No results for '{query}'.")
    except HttpError as e:
        return None, f"API Error: {e.content.decode('utf-8')}"
    except Exception as e:
        return None, f"Unexpected error: {e}"

def get_video_id_from_url(url: str):
    regex = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
    match = re.search(regex, url)
    return match.group(1) if match else None

def random_room_generator():
    return "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=2)) + "".join(random.choices("0123456789", k=3))

def update_video_state(room_code, video_id):
    db_local = init_firebase()
    if not db_local:
        print("[VideoState] Firestore not available")
        return
    try:
        room_ref = db_local.collection('rooms').document(room_code)
        room_ref.update({
            'current_video': {
                'id': video_id,
                'state': 'playing',
                'time': 0,
                'last_update': time.time()
            }
        })
    except Exception as e:
        print(f"[VideoState] Failed to update video state: {e}")

# ------------------- Routes -------------------
@app.route('/')
def homepage():
    return redirect(url_for('dashboard')) if 'user' in session else render_template('index.html')

@app.route('/verify-token', methods=['POST'])
def verify_token():
    db_local = init_firebase()
    try:
        if not request.is_json:
            return jsonify({"status": "error", "message": "Request must be JSON."}), 400

        id_token = request.json.get('token')
        if not id_token:
            return jsonify({"status": "error", "message": "Token not provided."}), 400

        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token.get('uid')
        if not uid:
            return jsonify({"status": "error", "message": "Invalid token."}), 401

        user_info = {
            'id': uid,
            'name': decoded_token.get('name', ''),
            'email': decoded_token.get('email', ''),
            'picture': decoded_token.get('picture', '')
        }
        session['user'] = user_info

        def update_firestore():
            try:
                if db_local:
                    user_ref = db_local.collection('users').document(uid)
                    user_doc = user_ref.get()
                    data = {
                        'name': user_info['name'],
                        'email': user_info['email'],
                        'picture': user_info['picture'],
                    }
                    if not user_doc.exists:
                        data['rooms'] = []
                        user_ref.set(data)
                    else:
                        user_ref.update(data)
                print(f"[VERIFY] Firestore updated for user {uid}")
            except Exception as e:
                print(f"[VERIFY] Firestore update failed: {e}")

        Thread(target=update_firestore, daemon=True).start()
        return jsonify({"status": "success", "message": "User authenticated."})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Authentication failed: {e}"}), 500

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('homepage'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('homepage'))

    db_local = init_firebase()
    rooms = []
    if db_local:
        try:
            user_ref = db_local.collection('users').document(session['user']['id'])
            user_doc = user_ref.get()
            rooms = user_doc.to_dict().get('rooms', []) if user_doc.exists else []
        except Exception as e:
            flash(f"Error fetching rooms: {e}", "error")
    else:
        flash("Database not initialized. Room data unavailable.", "error")

    return render_template('dashboard.html', user=session['user'], rooms=rooms)

# ------------------- Room Routes -------------------
@app.route('/room', methods=['POST'])
def create_or_join_room():
    if 'user' not in session:
        return redirect(url_for('homepage'))

    db_local = init_firebase()
    if not db_local:
        flash("Database unavailable.", "error")
        return redirect(url_for('dashboard'))

    user_info = session['user']
    action = request.form.get('action')
    room_code = request.form.get('room_code', '').strip().upper()

    try:
        if action == "Create":
            room_code = random_room_generator()
            db_local.collection('rooms').document(room_code).set({
                'created_by': user_info['id'],
                'users': [user_info['name']],
                'current_video': None
            })
        elif action == "Join":
            if not room_code:
                flash("Please enter a room code.", "error")
                return redirect(url_for('dashboard'))

            room_ref = db_local.collection('rooms').document(room_code)
            if not room_ref.get().exists:
                flash(f"Room '{room_code}' not found.", "error")
                return redirect(url_for('dashboard'))

            room_ref.update({'users': firestore.ArrayUnion([user_info['name']])})

        db_local.collection('users').document(user_info['id']).update({'rooms': firestore.ArrayUnion([room_code])})
    except Exception as e:
        flash(f"Room operation failed: {e}", "error")
        return redirect(url_for('dashboard'))

    return redirect(url_for('rejoin_room', room_code=room_code))

@app.route('/room/<room_code>')
def rejoin_room(room_code):
    if 'user' not in session:
        return redirect(url_for('homepage'))

    db_local = init_firebase()
    if not db_local:
        flash("Database unavailable.", "error")
        return redirect(url_for('dashboard'))

    try:
        room_doc = db_local.collection('rooms').document(room_code).get()
        if not room_doc.exists:
            flash(f"Room '{room_code}' not found.", "error")
            return redirect(url_for('dashboard'))

        user_doc = db_local.collection('users').document(session['user']['id']).get()
        if user_doc.exists and room_code not in user_doc.to_dict().get('rooms', []):
            flash(f"You do not have permission to join room '{room_code}'.", "error")
            return redirect(url_for('dashboard'))
    except Exception as e:
        flash(f"Could not access room: {e}", "error")
        return redirect(url_for('dashboard'))

    return render_template('room.html', username=session['user']['name'], room_code=room_code)

@app.route('/leave_room', methods=['POST'])
def leave_room_route():
    if 'user' not in session:
        return redirect(url_for('homepage'))

    db_local = init_firebase()
    if not db_local:
        flash("Database unavailable.", "error")
        return redirect(url_for('dashboard'))

    room_code = request.form.get('room_code')
    if not room_code:
        flash("Invalid request.", "error")
        return redirect(url_for('dashboard'))

    try:
        db_local.collection('users').document(session['user']['id']).update({'rooms': firestore.ArrayRemove([room_code])})
    except Exception as e:
        flash(f"Could not leave room: {e}", "error")

    flash(f"You have left room {room_code}.", "success")
    return redirect(url_for('dashboard'))

# ------------------- SocketIO -------------------
sid_to_user = {}

def get_online_members(room_code):
    return [u['username'] for u in sid_to_user.values() if u['room'] == room_code]

@socketio.on('join_room')
def handle_join(data):
    room_code = data['room']
    username = data['username']
    sid_to_user[request.sid] = {'username': username, 'room': room_code}
    join_room(room_code)
    emit('message', {'msg': f"{username} has entered the room"}, to=room_code)

    db_local = init_firebase()
    if db_local:
        try:
            room_doc = db_local.collection('rooms').document(room_code).get()
            if room_doc.exists:
                all_members = room_doc.to_dict().get('users', [])
                emit('update_member_list', {'all_members': all_members, 'online_members': get_online_members(room_code)}, to=room_code)
        except Exception as e:
            print(f"[Socket] Failed to fetch room: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in sid_to_user:
        user = sid_to_user.pop(request.sid)
        emit('message', {'msg': f"{user['username']} has left the room"}, to=user['room'])

# ------------------- Run App -------------------
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
