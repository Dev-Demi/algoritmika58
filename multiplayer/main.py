from gevent import monkey

monkey.patch_all()  # Применяем патчи gevent для корректной работы сети и таймеров

import time
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ваш_секретный_ключ'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ИЗМЕНЕНО: async_mode теперь 'gevent'
socketio = SocketIO(app, async_mode='gevent')

# --- Игровые константы ---
TANK_SIZE = 50
BULLET_SPEED = 7
CANVAS_WIDTH = 800
CANVAS_HEIGHT = 600
INITIAL_LIVES = 3
RESPAWN_X = 100
RESPAWN_Y = 100

# --- Глобальное состояние игры ---
game_state = {}
server_bullets = []
GAME_ROOM = 'игровая_комната'


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --- Серверный игровой цикл ---
def game_loop():
    print("Игровой цикл запущен на gevent!")
    while True:
        # Обновляем пули
        for i in range(len(server_bullets) - 1, -1, -1):
            bullet = server_bullets[i]
            if bullet['direction'] == 'up':
                bullet['y'] -= BULLET_SPEED
            elif bullet['direction'] == 'down':
                bullet['y'] += BULLET_SPEED
            elif bullet['direction'] == 'left':
                bullet['x'] -= BULLET_SPEED
            elif bullet['direction'] == 'right':
                bullet['x'] += BULLET_SPEED

            hit_detected = False
            for username, tank in game_state.items():
                if bullet['owner'] != username:
                    if (bullet['x'] > tank['x'] and bullet['x'] < tank['x'] + TANK_SIZE and
                            bullet['y'] > tank['y'] and bullet['y'] < tank['y'] + TANK_SIZE):

                        tank['lives'] -= 1
                        socketio.emit('tank_hit', {'username': username, 'lives': tank['lives']}, room=GAME_ROOM)

                        if tank['lives'] <= 0:
                            socketio.emit('tank_destroyed', {'username': username}, room=GAME_ROOM)
                            tank['lives'] = INITIAL_LIVES
                            tank['x'] = RESPAWN_X
                            tank['y'] = RESPAWN_Y
                            socketio.emit('player_update', {'username': username, **tank}, room=GAME_ROOM)

                        hit_detected = True
                        break

            if hit_detected or bullet['x'] < 0 or bullet['x'] > CANVAS_WIDTH or bullet['y'] < 0 or bullet[
                'y'] > CANVAS_HEIGHT:
                server_bullets.pop(i)

        socketio.emit('bullets_update', {'bullets': server_bullets}, room=GAME_ROOM)

        # Важно: socketio.sleep позволяет другим задачам выполняться
        socketio.sleep(1 / 60)


# --- Обработчики событий SocketIO ---
@socketio.on('connect')
def handle_connect():
    if not current_user.is_authenticated:
        return False

    username = current_user.username
    sid = request.sid
    join_room(GAME_ROOM)

    game_state[username] = {
        'x': RESPAWN_X, 'y': RESPAWN_Y, 'direction': 'up', 'sid': sid, 'lives': INITIAL_LIVES
    }

    # Понятный способ подготовки данных (как обсуждали ранее)
    players_data = {}
    for user_id, info in game_state.items():
        clean_info = info.copy()
        clean_info.pop('sid', None)  # Убираем технический ID
        players_data[user_id] = clean_info

    emit('initial_game_state', {
        'username': username,
        'players': players_data
    }, room=sid)

    emit('player_update', {
        'username': username,
        'x': game_state[username]['x'],
        'y': game_state[username]['y'],
        'direction': game_state[username]['direction'],
        'lives': game_state[username]['lives']
    }, room=GAME_ROOM, include_self=False)


@socketio.on('disconnect')
def handle_disconnect():
    if not current_user.is_authenticated or current_user.username not in game_state:
        return

    username = current_user.username
    leave_room(GAME_ROOM)
    if username in game_state:
        del game_state[username]
    emit('player_disconnected', {'username': username}, room=GAME_ROOM, include_self=False)


@socketio.on('player_move')
def handle_player_move(data):
    if not current_user.is_authenticated or current_user.username not in game_state:
        return

    username = current_user.username
    tank = game_state[username]
    tank['x'] = data['x']
    tank['y'] = data['y']
    tank['direction'] = data['direction']

    emit('player_update', {
        'username': username,
        'x': data['x'],
        'y': data['y'],
        'direction': data['direction'],
        'lives': tank['lives']
    }, room=GAME_ROOM, include_self=False)


@socketio.on('player_shoot')
def handle_player_shoot(data):
    if not current_user.is_authenticated or current_user.username not in game_state:
        return

    new_bullet = {
        'x': data['x'],
        'y': data['y'],
        'direction': data['direction'],
        'owner': current_user.username
    }
    server_bullets.append(new_bullet)


# --- Маршруты Flask ---
@app.route('/')
@login_required
def index():
    return render_template('index.html', username=current_user.username)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    # Запускаем фоновую задачу через SocketIO (она подружится с gevent автоматически)
    socketio.start_background_task(game_loop)

    # Запуск сервера
    socketio.run(app, host='0.0.0.0', port=5321, debug=True)