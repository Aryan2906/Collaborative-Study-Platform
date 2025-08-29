from flask import Flask,request
import random
from flask import render_template
from flask_socketio import join_room,leave_room,SocketIO,send,emit
import eventlet

eventlet.monkey_patch()

#initialization of flask and socketio
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

rooms={} #rooms dictionary temp


def random_room_generator():
    room_code = ""
    for i in range(0,2):
        room_code =room_code + chr(random.randint(65,80))
    for i in range(0,3):
        room_code = room_code + str(random.randint(1,9))
    return room_code

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
    join_room(room)
    emit('message',{'msg':f'{username} has entered the room'},room=room)
@socketio.on("send_message")
def send_message(data):
    username = data['username']
    room = data['room']
    msg = data['msg']
    emit('message',{'msg':f'{username}: {msg}'},room=room)
@socketio.on("disconnect")
def handle_disconnect():
    print('user disconnected')


if __name__ == '__main__':
    socketio.run(app,host='0.0.0.0', port=5000)