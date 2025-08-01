# 🎭 Финальные тестовые аккаунты

## ✅ Созданные аккаунты

### 👨‍🎤 Исполнитель
- **Номер телефона:** +7 775 418 4629
- **Пароль:** 30031986m
- **Имя:** Мирас Абильдин
- **Email:** miras.abildin@bk.ru
- **Город:** Астана
- **Компания:** TSZ Events
- **Тип услуг:** Ведущий (host)
- **Биография:** Профессиональный ведущий мероприятий с 10-летним опытом. Специализируюсь на свадьбах, корпоративах и детских праздниках. Создаю незабываемую атмосферу для каждого мероприятия!

### 👩‍💼 Заказчик
- **Номер телефона:** +7 708 161 9013
- **Пароль:** 123456
- **Имя:** Галия Муханбет
- **Email:** galya.customer@example.com
- **Город:** Астана
- **Биография:** Ищу профессиональных исполнителей для организации качественных мероприятий.

## 🔗 Ссылки для входа

### Локальная версия
- http://127.0.0.1:8000/auth/

### Продакшн версия
- https://toisozvezdoi.kz/auth/

## 📱 Процесс входа

1. Перейдите по ссылке авторизации
2. Введите номер телефона
3. Получите SMS с кодом подтверждения
4. Введите код и войдите в систему

## 🎯 Возможности аккаунтов

### Исполнитель может:
- Просматривать свой профиль
- Управлять календарем занятости
- Добавлять/редактировать портфолио
- Устанавливать тарифы
- Просматривать заявки от заказчиков
- Отвечать на заявки
- Общаться с заказчиками в чате

### Заказчик может:
- Просматривать каталог исполнителей
- Создавать заявки на мероприятия
- Бронировать исполнителей
- Просматривать свои заказы
- Общаться с исполнителями в чате
- Оставлять отзывы

## 🖼️ Изображения

Для добавления изображений к аккаунтам запустите:
```bash
python add_images_to_users.py
```

## 📊 Статус проекта

- ✅ Основные аккаунты созданы
- ✅ Данные заполнены
- ⚠️ Изображения требуют дополнительной настройки
- ✅ Система готова к тестированию

## 🔧 Технические детали

- **База данных:** SQLite (локально) / PostgreSQL (продакшн)
- **Фреймворк:** Django 3.2.25
- **Аутентификация:** OTP через SMS
- **Файлы:** Медиа файлы хранятся в папке `media/`

## 🚀 Следующие шаги

1. Протестировать вход в систему
2. Проверить функциональность календаря
3. Протестировать процесс бронирования
4. Проверить чат между пользователями
5. Добавить изображения при необходимости 