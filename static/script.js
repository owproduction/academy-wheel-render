document.addEventListener('DOMContentLoaded', () => {
    console.log("Скрипт загружен");

    const modalOverlay = document.getElementById('modal-overlay');
    const form = document.getElementById('registration-form');
    const wheelSection = document.getElementById('wheel-section');
    const spinBtn = document.getElementById('spin-btn');
    const wheelSvg = document.getElementById('wheel');
    const resultDisplay = document.getElementById('result-display');
    const winningPrizeText = document.getElementById('winning-prize-text');
    
    // Поля формы
    const nameInput = document.getElementById('name');
    const ageInput = document.getElementById('age');
    const phoneInput = document.getElementById('phone');
    const submitBtn = document.getElementById('submit-btn');

    let isSpinning = false;
    let currentRotation = 0;
    let hasSubmitted = false;

    // МАССИВ ПРИЗОВ НА КЛИЕНТЕ
    // ВАЖНО: Порядок должен соответствовать логике отрисовки.
    // Но для определения выигрыша мы будем искать приз по ID, который вернет сервер.
    const prizes = [
        { id: 1, name: "Бесплатный мастер класс", color: "#E91E63" },   
        { id: 2, name: "Брелок", color: "#9C27B0" },         
        { id: 3, name: "Наклейки", color: "#673AB7" },       
        { id: 4, name: "3D Стикер", color: "#3F51B5" },      
        { id: 5, name: "Пробный урок барабаны", color: "#FF5722" }    
    ];

    // --- ИНИЦИАЛИЗАЦИЯ СКРЫТИЯ РЕЗУЛЬТАТА ---
    // Убеждаемся, что блок результата точно скрыт при старте
    if (resultDisplay) {
        resultDisplay.style.display = 'none';
        resultDisplay.classList.add('hidden');
    }

    // --- ВАЛИДАЦИЯ ТЕЛЕФОНА ---
    function validatePhone(phoneStr) {
        if (!phoneStr) return false;
        const cleanNumber = phoneStr.replace(/[\s()-]/g, '');
        const regex = /^(\+7|7|8)\d{10}$/;
        return regex.test(cleanNumber);
    }

    // --- АКТИВАЦИЯ КНОПКИ ---
    function checkFormValidity() {
        const nameValid = nameInput.value.trim().length > 0;
        const ageVal = parseInt(ageInput.value);
        const ageValid = !isNaN(ageVal) && ageVal >= 5 && ageVal <= 99;
        const phoneValid = validatePhone(phoneInput.value);

        if (nameValid && ageValid && phoneValid) {
            submitBtn.disabled = false;
            submitBtn.style.opacity = "1";
        } else {
            submitBtn.disabled = true;
            submitBtn.style.opacity = "0.5";
        }
    }

    nameInput.addEventListener('input', checkFormValidity);
    ageInput.addEventListener('input', checkFormValidity);
    phoneInput.addEventListener('input', checkFormValidity);


    // 1. Отрисовка колеса
    function drawWheel() {
        const cx = 50, cy = 50, r = 48;
        const sliceAngle = 360 / prizes.length;
        
        let pathsHtml = '';
        
        prizes.forEach((prize, index) => {
            // Индекс в массиве соответствует порядку рисования
            const startAngle = (index * sliceAngle) - 90; 
            const endAngle = ((index + 1) * sliceAngle) - 90;
            
            const x1 = cx + r * Math.cos(startAngle * Math.PI / 180);
            const y1 = cy + r * Math.sin(startAngle * Math.PI / 180);
            const x2 = cx + r * Math.cos(endAngle * Math.PI / 180);
            const y2 = cy + r * Math.sin(endAngle * Math.PI / 180);
            
            const largeArcFlag = sliceAngle > 180 ? 1 : 0;
            
            const pathData = [
                `M ${cx} ${cy}`,
                `L ${x1} ${y1}`,
                `A ${r} ${r} 0 ${largeArcFlag} 1 ${x2} ${y2}`,
                `Z`
            ].join(' ');
            
            pathsHtml += `<path d="${pathData}" fill="${prize.color}" stroke="rgba(255,255,255,0.3)" stroke-width="0.5" />`;
            
            // Текст сектора
            const textAngle = startAngle + sliceAngle / 2;
            const tx = cx + (r * 0.65) * Math.cos(textAngle * Math.PI / 180);
            const ty = cy + (r * 0.65) * Math.sin(textAngle * Math.PI / 180);
            const rotation = textAngle + 90; 
            
            pathsHtml += `<text x="${tx}" y="${ty}" fill="white" font-size="2.5" font-weight="bold" text-anchor="middle" dominant-baseline="middle" transform="rotate(${rotation} ${tx} ${ty})" style="text-shadow: 1px 1px 2px rgba(0,0,0,0.5);">${prize.name}</text>`;
        });
        
        wheelSvg.innerHTML = pathsHtml;
    }

    drawWheel();

    // 2. Обработка отправки формы
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (hasSubmitted || submitBtn.disabled) return;

        const btn = submitBtn;
        btn.disabled = true;
        btn.textContent = "ОТПРАВКА...";

        const data = {
            name: nameInput.value.trim(),
            age: ageInput.value,
            phone: phoneInput.value.trim()
        };

        try {
            const response = await fetch('/api/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (response.ok) {
                hasSubmitted = true;
                modalOverlay.style.display = 'none';
                modalOverlay.classList.add('hidden');
                
                wheelSection.classList.remove('hidden');
                wheelSection.style.display = 'flex';
            } else {
                alert("Ошибка сохранения данных");
                btn.disabled = false;
                btn.textContent = "ЗАРЕГИСТРИРОВАТЬСЯ";
            }
        } catch (err) {
            console.error(err);
            alert("Сервер недоступен");
            btn.disabled = false;
            btn.textContent = "ЗАРЕГИСТРИРОВАТЬСЯ";
        }
    });

    // 3. Логика вращения
    spinBtn.addEventListener('click', async () => {
        // Защита: если уже крутится или результат уже показан
        if (isSpinning || !hasSubmitted || resultDisplay.style.display !== 'none') {
             // Если результат виден, значит уже крутили. Можно добавить сброс, но по ТЗ одно кручение.
             return;
        }
        
        isSpinning = true;
        spinBtn.disabled = true;
        spinBtn.textContent = "...";

        try {
            // Запрашиваем результат у бэкенда
            const res = await fetch('/api/spin');
            const json = await res.json();
            
            const serverPrizeId = json.prize_id; // Например, 2
            const serverPrizeName = json.prize_name;

            // Находим индекс этого приза в нашем локальном массиве prizes
            // Это критически важно для правильного расчета угла!
            const localIndex = prizes.findIndex(p => p.id === serverPrizeId);
            
            if (localIndex === -1) {
                throw new Error("Приз с таким ID не найден на клиенте!");
            }

            const sectorAngle = 360 / prizes.length;
            
            // Расчет угла остановки
            // Сектор i занимает диапазон от (i * angle) до ((i+1) * angle).
            // Его центр находится под углом: (i * angle) + (angle / 2).
            // Чтобы стрелка (которая смотрит вниз, на 0 градусов относительно верха экрана? Нет, стрелка сверху указывает вниз на 12 часов).
            // В нашей системе координат SVG:
            // 0 градусов — это право (3 часа).
            // -90 градусов — это верх (12 часов).
            // Мы рисуем сектора начиная с -90.
            // Сектор 0: от -90 до (-90 + 72). Центр: -90 + 36 = -54 градуса.
            // Чтобы сектор оказался ПОД стрелкой (сверху), нам нужно повернуть колесо так, 
            // чтобы центр сектора стал равен -90 градусам (позиции стрелки).
            // Текущий угол центра сектора: StartAngle(i) + HalfSlice.
            // Нам нужно применить поворот R, чтобы: CurrentCenter + R = TargetPosition (-90 deg).
            // R = -90 - CurrentCenter.
            
            const startAngleOfSector = (localIndex * sectorAngle) - 90;
            const centerAngleOfSector = startAngleOfSector + (sectorAngle / 2);
            
            // Целевой угол для стрелки (сверху)
            const targetArrowAngle = -90; 
            
            // Необходимый поворот колеса
            const requiredRotation = targetArrowAngle - centerAngleOfSector;
            
            // Добавляем несколько полных оборотов для эффекта (например, 5 оборотов)
            const extraRotations = 360 * 5;
            
            // Итоговый абсолютный угол поворота элемента
            // Учитываем текущую ротацию, чтобы колесо не прыгало назад
            const totalTargetRotation = currentRotation + extraRotations + requiredRotation;
            
            // Небольшой случайный джиттер внутри сектора (+/- 20 градусов), чтобы не останавливаться всегда в центре
            const jitter = (Math.random() * 20) - 10;
            const finalRotation = totalTargetRotation + jitter;

            // Применяем анимацию
            wheelSvg.style.transform = `rotate(${finalRotation}deg)`;
            currentRotation = finalRotation;

            // Ждем окончания CSS-анимации (4 секунды)
            setTimeout(() => {
                showResult(serverPrizeName);
                isSpinning = false;
            }, 4000);

        } catch (err) {
            console.error(err);
            alert("Ошибка получения результата");
            isSpinning = false;
            spinBtn.disabled = false;
            spinBtn.textContent = "КРУТИТЬ";
        }
    });

    function showResult(prizeName) {
        winningPrizeText.textContent = `Вы выиграли: ${prizeName}`;
        
        // Показываем блок
        resultDisplay.style.display = 'block';
        resultDisplay.classList.remove('hidden');
        
        // Опционально: скрываем кнопку крутить, чтобы нельзя было крутить второй раз
        spinBtn.style.visibility = 'hidden'; 
    }
});