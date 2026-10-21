# MedFlow CRM

Прототип CRM медицинского центра: администратор ведёт пациентов и процедуры, а система ставит WhatsApp-уведомления в очередь.

## Возможности

- вход администратора;
- карточки пациентов и согласие на WhatsApp;
- создание и изменение статуса процедур;
- SQLite для локального запуска;
- очередь сообщений и отдельный WhatsApp-worker;
- адаптивная панель администратора;
- REST API для дальнейшего подключения мобильного приложения или другого интерфейса.

## Быстрый запуск

```bash
git clone URL_ВАШЕГО_РЕПОЗИТОРИЯ
cd medflow-crm
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Откройте `http://127.0.0.1:5000`. Демонстрационный вход до изменения `.env`: `admin` / `admin123`.

## WhatsApp

1. Создайте приложение и номер в официальном Meta WhatsApp Cloud API.
2. Создайте и согласуйте шаблон `appointment_reminder` с двумя параметрами: имя пациента и дата/время визита.
3. Заполните `WHATSAPP_ACCESS_TOKEN` и `WHATSAPP_PHONE_NUMBER_ID` в `.env`.
4. Запустите обработчик очереди в отдельном терминале:

```bash
python worker.py
```

Не добавляйте токены в GitHub. Файл `.env` уже исключён через `.gitignore`.

## Загрузка в GitHub

```bash
git init
git add .
git commit -m "Initial MedFlow CRM prototype"
git branch -M main
git remote add origin https://github.com/ВАШ_ЛОГИН/medflow-crm.git
git push -u origin main
```

## Важно перед реальным использованием

Это MVP, а не сертифицированная медицинская информационная система. До работы с реальными данными нужны как минимум HTTPS, PostgreSQL, резервное копирование, роли сотрудников, журнал аудита, проверка подписи webhook, политика хранения данных и юридическая проверка требований вашей страны. Не храните реальные медицинские данные в публичном репозитории.

