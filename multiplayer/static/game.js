// game.js
document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('gameCanvas');
    const ctx = canvas.getContext('2d');

    canvas.width = 800;
    canvas.height = 600;

    const РАЗМЕР_ТАНКА = 50;
    const СКОРОСТЬ_ТАНКА = 3;
    const РАДИУС_ПУЛИ = 5;

    // Состояние игры
    let танкИгрока = {
        x: canvas.width / 2 - РАЗМЕР_ТАНКА / 2,
        y: canvas.height / 2 - РАЗМЕР_ТАНКА / 2,
        direction: 'up', // 'up', 'down', 'left', 'right'
        lives: 3, // Жизни
        username: '', // Имя пользователя, будет установлено после подключения
        isMoving: false // Движется ли танк
    };

    let другиеИгроки = {}; // Хранит танки других игроков
    let всеПули = []; // Все пули теперь управляются сервером
    let клавиши = {}; // Отслеживает нажатые клавиши
    let socket; // Соединение Socket.IO
    let кадрАнимации = 0; // Для анимации

    // --- Настройка Socket.IO ---
    function подключитьСокет() {
        socket = io(); // Подключаемся к текущему хосту

        socket.on('connect', () => console.log('Подключено к серверу Socket.IO!'));
        socket.on('disconnect', () => console.log('Отключено от сервера Socket.IO.'));
        socket.on('status', (data) => console.log('Статус сервера:', data.msg));

        socket.on('initial_game_state', (data) => {
            танкИгрока.username = data.username;
            // Устанавливаем начальное состояние собственного танка с сервера
            if (data.players[танкИгрока.username]) {
                Object.assign(танкИгрока, data.players[танкИгрока.username]);
            }
            console.log(`Мое имя пользователя: ${танкИгрока.username}`);

            // Заполняем другиеИгроки существующими игроками
            for (const username in data.players) {
                if (username !== танкИгрока.username) {
                    другиеИгроки[username] = data.players[username];
                    другиеИгроки[username].username = username;
                }
            }
        });

        socket.on('player_update', (data) => {
            const этоСвойТанк = data.username === танкИгрока.username;
            const танк = этоСвойТанк ? танкИгрока : другиеИгроки[data.username];

            if (!танк) return;

            // Проверяем движение для обновления метки времени анимации
            if (!этоСвойТанк && (танк.x !== data.x || танк.y !== data.y)) {
                танк.lastMoveTime = Date.now(); // Время последнего движения
            }

            Object.assign(танк, data);
            if (!этоСвойТанк) {
                танк.username = data.username;
            }
        });

        socket.on('player_disconnected', (data) => {
            console.log(`${data.username} отключился.`);
            delete другиеИгроки[data.username];
        });

        // Сервер отправляет все позиции пуль за один раз
        socket.on('bullets_update', (data) => {
            всеПули = data.bullets;
        });

        socket.on('tank_hit', (data) => {
            const танк = data.username === танкИгрока.username ? танкИгрока : другиеИгроки[data.username];
            if (танк) {
                танк.lives = data.lives;
                if (танк.username === танкИгрока.username) {
                    console.log(`Меня подбили! Осталось жизней: ${танкИгрока.lives}`);
                }
            }
        });

        socket.on('tank_destroyed', (data) => {
            console.log(`${data.username} был уничтожен!`);
            // Сервер сам обработает возрождение и отправит player_update
        });
    }

    // --- Функции отрисовки ---
    function рисоватьТанк(танк) {
        if (!танк || танк.lives <= 0) return; // Не рисуем, если танка нет или он уничтожен

        const этоСвойТанк = танк.username === танкИгрока.username;
        const цветКорпуса = этоСвойТанк ? '#005c99' : '#3d8c3d'; // Темно-синий / Зеленый
        const цветГусениц = этоСвойТанк ? '#003366' : '#224d22'; // Еще темнее
        const цветБашни = этоСвойТанк ? '#004488' : '#2e6b2e'; // Средний
        const цветПушки = '#333'; // Темно-серый

        const x = танк.x;
        const y = танк.y;
        const size = РАЗМЕР_ТАНКА;

        // Определяем, движется ли танк для анимации
        let движется = false;
        if (этоСвойТанк) {
            движется = танк.isMoving;
        } else {
            // Анимируем, если последнее обновление было недавно
            движется = танк.lastMoveTime && (Date.now() - танк.lastMoveTime < 200);
        }

        ctx.save();
        ctx.translate(x + size / 2, y + size / 2); // Перемещаем начало координат в центр танка

        // Поворачиваем в зависимости от направления
        let угол = 0;
        if (танк.direction === 'down') угол = Math.PI;
        if (танк.direction === 'left') угол = -Math.PI / 2;
        if (танк.direction === 'right') угол = Math.PI / 2;
        ctx.rotate(угол);

        // --- Рисуем корпус танка ---
        const ширинаКорпуса = size * 0.7;
        const высотаКорпуса = size;
        const ширинаГусениц = size * 0.15;

        // Рисуем гусеницы
        ctx.fillStyle = цветГусениц;
        ctx.fillRect(-size / 2, -size / 2, ширинаГусениц, size); // Левая гусеница
        ctx.fillRect(size / 2 - ширинаГусениц, -size / 2, ширинаГусениц, size); // Правая гусеница

        // Анимируем гусеницы
        if (движется) {
            ctx.fillStyle = '#555'; // Светлые линии гусениц
            const смещениеАнимации = кадрАнимации % 10;
            for (let i = -size / 2 + смещениеАнимации; i < size / 2; i += 10) {
                ctx.fillRect(-size / 2, i, ширинаГусениц, 5);
                ctx.fillRect(size / 2 - ширинаГусениц, i, ширинаГусениц, 5);
            }
        }

        // Рисуем основной корпус
        ctx.fillStyle = цветКорпуса;
        ctx.fillRect(-ширинаКорпуса / 2, -size / 2, ширинаКорпуса, size);

        // Рисуем башню
        ctx.fillStyle = цветБашни;
        ctx.beginPath();
        ctx.arc(0, 0, ширинаКорпуса / 2, 0, 2 * Math.PI);
        ctx.fill();

        // Рисуем пушку
        ctx.fillStyle = цветПушки;
        ctx.fillRect(-3, -size * 0.8, 6, size * 0.6);

        ctx.restore(); // Восстанавливаем контекст в исходное состояние

        // Рисуем имя пользователя и жизни (не повернутые)
        ctx.fillStyle = 'black';
        ctx.font = '12px Arial';
        ctx.textAlign = 'center';
        ctx.fillText(`${танк.username} [${танк.lives}]`, x + size / 2, y - 15);
    }

    function рисоватьПулю(bullet) {
        ctx.fillStyle = 'orange';
        ctx.beginPath();
        ctx.arc(bullet.x, bullet.y, РАДИУС_ПУЛИ, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = 'red';
        ctx.stroke();
    }

    // --- Игровая логика ---
    let последнееСостояниеИгрока = {};

    function обновитьСостояние() {
        танкИгрока.isMoving = false;
        if (клавиши['KeyW']) { танкИгрока.y -= СКОРОСТЬ_ТАНКА; танкИгрока.direction = 'up'; танкИгрока.isMoving = true; }
        if (клавиши['KeyS']) { танкИгрока.y += СКОРОСТЬ_ТАНКА; танкИгрока.direction = 'down'; танкИгрока.isMoving = true; }
        if (клавиши['KeyA']) { танкИгрока.x -= СКОРОСТЬ_ТАНКА; танкИгрока.direction = 'left'; танкИгрока.isMoving = true; }
        if (клавиши['KeyD']) { танкИгрока.x += СКОРОСТЬ_ТАНКА; танкИгрока.direction = 'right'; танкИгрока.isMoving = true; }

        // Удерживаем танк в пределах холста
        танкИгрока.x = Math.max(0, Math.min(canvas.width - РАЗМЕР_ТАНКА, танкИгрока.x));
        танкИгрока.y = Math.max(0, Math.min(canvas.height - РАЗМЕР_ТАНКА, танкИгрока.y));

        // Отправляем player_move, если позиция или направление изменились
        if (socket && (танкИгрока.x !== последнееСостояниеИгрока.x || танкИгрока.y !== последнееСостояниеИгрока.y || танкИгрока.direction !== последнееСостояниеИгрока.direction)) {
            socket.emit('player_move', { x: танкИгрока.x, y: танкИгрока.y, direction: танкИгрока.direction });
            последнееСостояниеИгрока = { ...танкИгрока };
        }

        // Стрельба (только один выстрел за нажатие клавиши)
        if (клавиши['Space'] && !танкИгрока.isFiring) {
            let bulletX = танкИгрока.x + РАЗМЕР_ТАНКА / 2;
            let bulletY = танкИгрока.y + РАЗМЕР_ТАНКА / 2;

            // Корректируем начальную позицию пули в зависимости от направления танка
            switch (танкИгрока.direction) {
                case 'up': bulletY = танкИгрока.y - РАДИУС_ПУЛИ; break;
                case 'down': bulletY = танкИгрока.y + РАЗМЕР_ТАНКА + РАДИУС_ПУЛИ; break;
                case 'left': bulletX = танкИгрока.x - РАДИУС_ПУЛИ; break;
                case 'right': bulletX = танкИгрока.x + РАЗМЕР_ТАНКА + РАДИУС_ПУЛИ; break;
            }

            // Сообщаем серверу, что мы выстрелили
            if (socket) {
                socket.emit('player_shoot', { x: bulletX, y: bulletY, direction: танкИгрока.direction });
            }
            танкИгрока.isFiring = true; // Предотвращаем непрерывную стрельбу
        } else if (!клавиши['Space']) {
            танкИгрока.isFiring = false; // Сбрасываем состояние стрельбы, когда пробел отпущен
        }
    }

    function отрисовать() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#c2b280'; // Песчаный фон
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        рисоватьТанк(танкИгрока);
        for (const username in другиеИгроки) {
            рисоватьТанк(другиеИгроки[username]);
        }
        всеПули.forEach(рисоватьПулю);

        ctx.fillStyle = 'black';
        ctx.font = '16px Arial';
        ctx.textAlign = 'left';
        ctx.fillText(`Жизни: ${танкИгрока.lives}`, 10, 20);
    }

    // Игровой цикл
    function игровойЦикл() {
        кадрАнимации++;
        обновитьСостояние();
        отрисовать();
        requestAnimationFrame(игровойЦикл);
    }

    // --- Инициализация ---
    document.addEventListener('keydown', (e) => { клавиши[e.code] = true; });
    document.addEventListener('keyup', (e) => { клавиши[e.code] = false; });

    подключитьСокет();
    игровойЦикл();
});
