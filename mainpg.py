# import eventlet
# eventlet.monkey_patch()
import os
import json
import time
import random
import re


from flask import Flask, request, render_template, session, redirect, url_for, flash, jsonify
from flask_socketio import join_room, leave_room, SocketIO, emit
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


import firebase_admin
from firebase_admin import credentials, auth,firestore

from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=5)

def run_in_executor(func, *args, **kwargs):
    future = executor.submit(func, *args, **kwargs)
    return future.result()

app = Flask(__name__)


app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

db = None

firebase_app = None
db = None

def get_firebase_app():
    global firebase_app, db
    if not firebase_app:
        config = os.environ.get("FIREBASE_CONFIG")
        cred_dict = json.loads(config)
        # Fix newline characters
        cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
        firebase_app = firebase_admin.initialize_app(credentials.Certificate(cred_dict))
        db = firestore.client()
        print("Firebase initialized")
    return firebase_app,db



API_KEY = "AIzaSyAav6iqs8d6XyLztW2oGeiR5rv2kNJW6JI"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


def random_room_generator():
    """Generates a random 5-character room code."""
    return "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=2)) + "".join(random.choices("0123456789", k=3))

def get_video_id_from_search(query: str):
    """Searches YouTube and returns (video_id, error_message)."""
    if not query.strip(): return None, "Search query cannot be empty."
    if not API_KEY or API_KEY == "YOUR_API_KEY": return None, "Server Error: YouTube API key not configured."
    try:
        youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
        response = youtube.search().list(q=query, part="snippet", maxResults=1, type="video").execute()
        items = response.get("items", [])
        return (items[0]["id"]["videoId"], None) if items else (None, f"No results for '{query}'.")
    except HttpError as e:
        return None, f"API Error: {e.content.decode('utf-8')}"
    except Exception as e:
        return None, f"An unexpected error occurred: {e}"

def get_video_id_from_url(url: str):
    """Extracts a video ID from a YouTube URL using regex."""
    if not url.strip(): return None
    regex = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
    match = re.search(regex, url)
    return match.group(1) if match else None

def update_video_state(room_code, video_id):
    """Helper to reset a room's video state in Firestore for a new video."""
    firebase_app, db = get_firebase_app()
    if not db: return
    room_ref = db.collection('rooms').document(room_code)
    room_ref.update({
        'current_video': {
            'id': video_id,
            'state': 'playing',
            'time': 0,
            'last_update': time.time()
        }
    })


@app.route('/')
def homepage():
    return redirect(url_for('dashboard')) if 'user' in session else render_template('index.html')

@app.route('/verify-token', methods=['POST'])
def verify_token():
    firebase_app, db = get_firebase_app()
    try:
        id_token = request.json.get('token')
        if not id_token:
            return jsonify({"status": "error", "message": "Token not provided."}), 400

        decoded_token = auth.verify_id_token(id_token)
        print(decoded_token)
        uid = decoded_token['uid']
        user_info = {
            'id': uid,
            'name': decoded_token.get('name'),
            'email': decoded_token.get('email'),
            'picture': decoded_token.get('picture')
        }

        if db:
            def write_user():
                user_ref = db.collection('users').document(uid)
                user_doc = user_ref.get()
                user_data_to_set = {
                    'name': user_info['name'],
                    'email': user_info['email'],
                    'picture': user_info.get('picture'),
                }
                if not user_doc.exists:
                    user_data_to_set['rooms'] = []
                    user_ref.set(user_data_to_set)
                else:
                    user_ref.update(user_data_to_set)

            run_in_executor(write_user)

        session['user'] = user_info
        return jsonify({"status": "success", "message": "User authenticated."})

    except Exception as e:
        print(f"Authentication failed: {e}")
        return jsonify({"status": "error", "message": f"Authentication failed: {e}"}), 401


@app.route('/dashboard')
def dashboard():
    firebase_app, db = get_firebase_app()
    if 'user' not in session:
        return redirect(url_for('homepage'))
    
    user_rooms = []
    if db:
        try:
            def fetch_rooms():
                user_ref = db.collection('users').document(session['user']['id'])
                user_doc = user_ref.get()
                return user_doc

            user_doc = run_in_executor(fetch_rooms)
            if user_doc.exists:
                user_data = user_doc.to_dict()
                user_rooms = user_data.get('rooms', [])
        except Exception as e:
            flash(f"An error occurred while fetching room data: {e}", "error")

    return render_template('dashboard.html', user=session['user'], rooms=user_rooms)


@app.route('/room', methods=['POST'])
def create_or_join_room():
    firebase_app, db = get_firebase_app()
    if 'user' not in session or not db:
        return redirect(url_for('homepage'))

    user_info = session['user']
    action = request.form.get('action')
    room_code = request.form.get('room_code', '').strip().upper()

    def db_action():
        nonlocal room_code
        if action == "Create":
            room_code = random_room_generator()
            db.collection('rooms').document(room_code).set({
                'created_by': user_info['id'],
                'users': [user_info['name']],
                'current_video': None
            })
        elif action == "Join":
            room_ref = db.collection('rooms').document(room_code)
            if not room_ref.get().exists:
                return False
            room_ref.update({'users': firestore.ArrayUnion([user_info['name']])})

        user_ref = db.collection('users').document(user_info['id'])
        user_ref.update({'rooms': firestore.ArrayUnion([room_code])})
        return True

    success = run_in_executor(db_action)
    if not success and action == "Join":
        flash(f"Room '{room_code}' not found.", "error")
        return redirect(url_for('dashboard'))

    return redirect(url_for('rejoin_room', room_code=room_code))


@app.route('/room/<room_code>')
def rejoin_room(room_code):
    firebase_app, db = get_firebase_app()
    if 'user' not in session or not db:
        return redirect(url_for('homepage'))

    def fetch_room_and_user():
        room_doc = db.collection('rooms').document(room_code).get()
        user_doc = db.collection('users').document(session['user']['id']).get()
        return room_doc, user_doc

    room_doc, user_doc = run_in_executor(fetch_room_and_user)

    if not room_doc.exists:
        flash(f"Room '{room_code}' could not be found.", "error")
        return redirect(url_for('dashboard'))

    if user_doc.exists:
        user_rooms = user_doc.to_dict().get('rooms', [])
        if room_code not in user_rooms:
            flash(f"You do not have permission to join room '{room_code}'.", "error")
            return redirect(url_for('dashboard'))
    else:
        flash("Could not verify your user data.", "error")
        return redirect(url_for('dashboard'))

    return render_template('room.html', username=session['user']['name'], room_code=room_code)


@app.route('/leave_room', methods=['POST'])
def leave_room_route():
    firebase_app, db = get_firebase_app()
    if 'user' not in session or not db:
        return redirect(url_for('homepage'))
        
    room_code = request.form.get('room_code')
    user_info = session['user']
    
    if not room_code:
        flash("Invalid request.", "error")
        return redirect(url_for('dashboard'))
    
    def leave():
        user_ref = db.collection('users').document(user_info['id'])
        user_ref.update({'rooms': firestore.ArrayRemove([room_code])})
    run_in_executor(leave)
    
    flash(f"You have left room {room_code}. You can rejoin anytime using the room code.", "success")
    return redirect(url_for('dashboard'))


@socketio.on('join_room')
def handle_join(data):
    firebase_app, db = get_firebase_app()
    room_code = data['room']
    username = data['username']
    
    sid_to_user[request.sid] = {'username': username, 'room': room_code}
    
    join_room(room_code)
    emit('message', {'msg': f"{username} has entered the room"}, to=room_code)

    if db:
        def fetch_room():
            return db.collection('rooms').document(room_code).get()
        room_doc = run_in_executor(fetch_room)

        if room_doc.exists:
            room_data = room_doc.to_dict()
            all_members = room_data.get('users', [])
            online_members = get_online_members(room_code)
            
            emit('update_member_list', {'all_members': all_members, 'online_members': online_members}, to=room_code)

            if room_data.get('current_video'):
                video_state = room_data['current_video']
                if video_state.get('state') == 'playing':
                    elapsed_time = time.time() - video_state.get('last_update', time.time())
                    video_state['time'] = video_state.get('time', 0) + elapsed_time
                
                emit('play_video', {
                    'video_id': video_state['id'],
                    'start_time': video_state['time'],
                    'state': video_state['state']
                }, to=request.sid)


@socketio.on('video_event')
def handle_video_event(data):
    firebase_app, db = get_firebase_app()
    user_session = sid_to_user.get(request.sid)
    if not user_session: return

    room_code = user_session['room']
    
    if db:
        def update_event():
            db.collection('rooms').document(room_code).update({
                'current_video.state': data['event'],
                'current_video.time': data['time'],
                'current_video.last_update': time.time()
            })
        run_in_executor(update_event)

    emit('video_event', data, to=room_code, skip_sid=request.sid)


@socketio.on('sync_time')
def handle_sync_time(data):
    firebase_app, db = get_firebase_app()
    user_session = sid_to_user.get(request.sid)
    if not user_session: return
    
    room_code = user_session['room']
    if db:
        def update_time():
            db.collection('rooms').document(room_code).update({
                'current_video.time': data['time'],
                'current_video.last_update': time.time()
            })
        run_in_executor(update_time)

@socketio.on('disconnect')
def handle_disconnect():
    firebase_app, db = get_firebase_app()
    if request.sid in sid_to_user:
        user_info = sid_to_user.pop(request.sid)
        username = user_info['username']
        room_code = user_info['room']
        
        emit('message', {'msg': f"{username} has left the room"}, to=room_code)

        if db:
            online_members = get_online_members(room_code)
            room_ref = db.collection('rooms').document(room_code)
            room_doc = room_ref.get()
            if room_doc.exists:
                all_members = room_doc.to_dict().get('users', [])
                emit('update_member_list', {'all_members': all_members, 'online_members': online_members}, to=room_code)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080)) 
    socketio.run(app, host='0.0.0.0', port=port, debug=False,allow_unsafe_werkzeug= True)