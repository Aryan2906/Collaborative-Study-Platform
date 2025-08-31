from flask import Flask,request
import random
import re
import time
from flask import render_template
from flask_socketio import join_room,leave_room,SocketIO,send,emit
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


API_KEY = "AIzaSyAav6iqs8d6XyLztW2oGeiR5rv2kNJW6JI" 
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


#initialization of flask and socketio
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

rooms={} #rooms dictionary temp
user_sessions = {}#for session ids


def random_room_generator():
    room_code = ""
    for i in range(0,2):
        room_code =room_code + chr(random.randint(65,80))
    for i in range(0,3):
        room_code = room_code + str(random.randint(1,9))
    return room_code

# --- New YouTube Helper Functions ---
def get_video_id_from_search(query: str):
    """
    Searches YouTube for a query.
    Returns (video_id, None) on success.
    Returns (None, error_message) on failure.
    """
    if not query.strip():
        return None, "Search query cannot be empty."
    if API_KEY == "YOUR_API_KEY":
        error_msg = "SERVER ERROR: The YouTube API key has not been configured."
        print(f"ERROR: {error_msg}")
        return None, error_msg
    try:
        youtube_service = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
        search_response = youtube_service.search().list(q=query, part="snippet", maxResults=1, type="video").execute()
        results = search_response.get("items", [])
        if not results:
            return None, f"No video results were found for '{query}'."
        video_id = results[0]["id"]["videoId"]
        return video_id, None
    except HttpError as e:
        error_msg = "An error occurred while communicating with the YouTube API. Check if the API key is valid."
        print(f"API HttpError: {e}")
        return None, error_msg
    except Exception as e:
        error_msg = "An unexpected server error occurred during search."
        print(f"Unexpected Error: {e}")
        return None, error_msg

def get_video_id_from_url(url: str):
    """
    Extracts the YouTube video ID from a given URL.
    Returns None if the URL is invalid.
    """
    if not url.strip():
        return None
    regex = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
    match = re.search(regex, url)
    return match.group(1) if match else None


@app.route('/')
def homepage():
    return render_template('index.html')

@app.route('/room', methods = ['POST'])
def room():
    username = request.form.get('username')
    action = request.form.get('action')
    room_code = request.form.get('room_code', '').strip().upper()

    if action == "Create":
        room_code=random_room_generator()
        # Store room state and add the creator to the user list immediately.
        rooms[room_code] = {'users': [username], 'current_video': None}

    elif action == "Join":
        if room_code not in rooms:
            return "Room not found", 404
        # Prevent users with duplicate usernames from joining the same room.
        if username in rooms[room_code]['users']:
            return f"Username '{username}' is already taken in room {room_code}. Please go back and choose a different name.", 409
        rooms[room_code]['users'].append(username)
    
    else:
        return "Invalid action. Please Create or Join a room.", 400

    print(rooms)
    return render_template('room.html',username=username,room_code=room_code)


@socketio.on('join_room')
def handle_join(data):
    username = data['username']
    room = data['room']
    sid = request.sid
    user_sessions[sid] = {'username': username, 'room': room}
    join_room(room)
    emit('message',{'msg':f'{username} has entered the room'},room=room)
    if room in rooms and rooms[room].get('current_video'):
        video_state = rooms[room]['current_video']
        start_time = video_state['time']

        # If the video was playing, calculate how far along it should be now.
        if video_state['state'] == 'playing':
            time_since_update = time.time() - video_state['last_update']
            start_time += time_since_update

        emit('play_video', {
            'video_id': video_state['id'], 
            'start_time': start_time,
            'state': video_state['state']
        }, to=sid)

@socketio.on("send_message")
def send_message(data):
    username = data['username']
    room = data['room']
    msg = data['msg']
    emit('message',{'msg':f'{username}: {msg}'},room=room)
def update_video_state(room, video_id):
    rooms[room]['current_video'] = {
        'id': video_id,
        'state': 'playing',
        'time': 0,
        'last_update': time.time()
    }

# --- New SocketIO Handlers for YouTube ---
@socketio.on("search_video")
def handle_search_video(data):
    query = data.get("query")
    room = user_sessions[request.sid]['room'] # Get room from session
    video_id, error = get_video_id_from_search(query)
    if video_id:
        emit("play_video", {"video_id": video_id, "start_time": 0}, to=room)
        if room in rooms:
            update_video_state(room, video_id)
    else:
        emit("error", {"message": error or "Could not find video."})

@socketio.on("play_from_url")
def handle_play_from_url(data):
    url = data.get("url")
    room = user_sessions[request.sid]['room'] # Get room from session
    video_id = get_video_id_from_url(url)
    if video_id:
        emit("play_video", {"video_id": video_id, "start_time": 0}, to=room)
        if room in rooms:
            update_video_state(room, video_id)
    else:
        emit("error", {"message": "Invalid YouTube URL provided."})

@socketio.on("video_event")
def handle_video_event(data):
    room = user_sessions.get(request.sid, {}).get('room')
    if room in rooms and rooms[room]['current_video']:
        event = data.get("event") # 'play' or 'pause'
        current_time = data.get("time", 0)
        
        # Update the server's state record
        rooms[room]['current_video']['state'] = 'playing' if event == 'play' else 'paused'
        rooms[room]['current_video']['time'] = current_time
        rooms[room]['current_video']['last_update'] = time.time()

        emit("video_event", data, to=room, skip_sid=request.sid)

@socketio.on("sync_time")
def handle_sync_time(data):
    """NEW function to receive time updates from the clients."""
    room = user_sessions.get(request.sid, {}).get('room')
    if room in rooms and rooms[room].get('current_video'):
        rooms[room]['current_video']['time'] = data.get('time', 0)
        rooms[room]['current_video']['last_update'] = time.time()


@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid

    if sid in user_sessions:
        username = user_sessions[sid]['username']
        room = user_sessions[sid]['room']

        # Remove user from room
        if room in rooms and username in rooms[room]['users']:
            rooms[room]['users'].remove(username)

            emit('message', {'msg': f'{username} has left the room'}, room=room)
            print(f"{username} left room {room}")

            # If the room becomes empty, delete it
            if not rooms[room]['users']:
                del rooms[room]
                print(f"Room {room} is empty and has been deleted.")
            else:
                print(f"Room {room} is NOT empty. It will not be deleted.")
        # Remove SID from sessions
        del user_sessions[sid]

    print('A user disconnected')


if __name__ == '__main__':
    socketio.run(app,host='0.0.0.0', port=5000, debug=True)