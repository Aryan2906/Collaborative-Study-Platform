from flask import Flask
import random
from flask import render_template
app = Flask(__name__)
def random_room_generator():
    room_code = ""
    for i in range(0,2):
        room_code =room_code + chr(random.randint(65,80))
    for i in range(0,3):
        room_code = room_code + str(random.randint(1,9))
    return room_code


code = random_room_generator()
@app.route('/', methods = ['GET', 'POST'])
def homepage():
    return render_template('joinroom.html')

@app.route('/room', methods = ['GET', 'POST'])
def room():
    code=random_room_generator()
    return render_template('room.html',room_code = code)

if __name__ == '__main__':
    app.run(debug=True)