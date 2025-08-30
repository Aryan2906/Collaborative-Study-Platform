from flask import Flask,request
import random
import re
import eventlet
from flask import render_template
from flask_socketio import join_room,leave_room,SocketIO,send,emit
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


API_KEY = "AIzaSyAav6iqs8d6XyLztW2oGeiR5rv2kNJW6JI" 
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


#initialization of flask and socketio
eventlet.monkey_patch()
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app,async_mode='eventlet', cors_allowed_origins="*")

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
        rooms[room_code]=[]
    if action == "Join" and room_code not in rooms:
        print(room_code)
        return "Room not found",404
    if action == "Join" and username not in rooms[room_code]:
        rooms[room_code].append(username)
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

@socketio.on("send_message")
def send_message(data):
    username = data['username']
    room = data['room']
    msg = data['msg']
    emit('message',{'msg':f'{username}: {msg}'},room=room)

# --- New SocketIO Handlers for YouTube ---
@socketio.on("search_video")
def handle_search_video(data):
    query = data.get("query")
    room = user_sessions[request.sid]['room'] # Get room from session
    video_id, error = get_video_id_from_search(query)
    if video_id:
        emit("play_video", {"video_id": video_id}, to=room)
    else:
        emit("error", {"message": error or "Could not find video."})

@socketio.on("play_from_url")
def handle_play_from_url(data):
    url = data.get("url")
    room = user_sessions[request.sid]['room'] # Get room from session
    video_id = get_video_id_from_url(url)
    if video_id:
        emit("play_video", {"video_id": video_id}, to=room)
    else:
        emit("error", {"message": "Invalid YouTube URL provided."})

@socketio.on("video_event")
def handle_video_event(data):
    """
    Handles video playback events (like play/pause) and broadcasts them.
    """
    event = data.get("event")
    room = user_sessions.get(request.sid, {}).get('room')
    if room:
        emit("video_event", data, to=room, skip_sid=request.sid)
        print(f"Broadcasting event '{event}' to room '{room}'")



@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid

    if sid in user_sessions:
        username = user_sessions[sid]['username']
        room = user_sessions[sid]['room']

        # Remove user from room
        if room in rooms and username in rooms[room]:
            rooms[room].remove(username)

            emit('message', {'msg': f'{username} has left the room'}, room=room)
            print(f"{username} left room {room}")

            # If the room becomes empty, delete it
            if not rooms[room]:
                del rooms[room]

        # Remove SID from sessions
        del user_sessions[sid]

    print('A user disconnected')


if __name__ == '__main__':
    socketio.run(app,host='0.0.0.0', port=5000, debug=True)