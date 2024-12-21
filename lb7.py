from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import requests
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app)

# Главная страница
@app.route('/')
def index():
    """
    Обработчик для главной страницы. Рендерит шаблон index.html.
    """
    return render_template('index.html')

class CurrencyObserver:
    """
    Наблюдатель за курсами валют.  Регистрирует клиентов, уведомляет их об изменениях курсов.
    """
    def __init__(self):
        """
        Инициализирует наблюдателя со словарем для хранения зарегистрированных клиентов.
        """
        self.observers = {} # Словарь для хранения клиентов и выбранных ими валют

    def register(self, observer, currency_code):
        """
        Регистрирует нового клиента.

        Args:
            observer: Объект клиента (Client).
            currency_code: Код валюты, за которой следит клиент.
        """
        self.observers[observer.sid] = {'observer': observer, 'currency': currency_code}
        print(f"Клиент {observer.sid} подключился и выбрал валюту: {currency_code}")

    def unregister(self, observer):
        """
        Удаляет клиента из списка наблюдателей.

        Args:
            observer: Объект клиента (Client).
        """
        if observer.sid in self.observers:
            print(f"Клиент {observer.sid} отключился")
            del self.observers[observer.sid]

    def notify(self, data):
        """
        Уведомляет всех зарегистрированных клиентов об изменениях курсов валют.

        Args:
            data: Словарь с данными о курсах валют от ЦБ РФ.
        """
        for entry in self.observers.values():
            observer = entry['observer']
            currency_code = entry['currency']
            if currency_code in data['Valute']:
                currency_info = data['Valute'][currency_code]
                # Подготавливаем данные для отправки, включая текущий и предыдущий курс
                currency_data = {
                    'currency_code': currency_code,
                    'current_rate': currency_info['Value'],
                    'previous_rate': currency_info['Previous']
                }
                observer.update(currency_data)

class Client:
    """
    Представляет клиента, подключенного к сокету.
    """
    def __init__(self, sid):
        """
        Инициализирует клиента с его уникальным идентификатором сессии (sid).

        Args:

            sid: Уникальный идентификатор сессии клиента.
        """
        self.sid = sid

    def update(self, data):
        """
        Отправляет обновленные данные клиенту через сокет.

        Args:
            data: Словарь с данными о курсе валюты.
        """
        socketio.emit('update', data, room=self.sid)

def get_currency_rates():
    """
    Получает актуальные курсы валют от API ЦБ РФ.

    Returns:
        Словарь с данными о курсах валют.
    """
    response = requests.get('https://www.cbr-xml-daily.ru/daily_json.js')
    return response.json()

def currency_updater(observer):
    """
    Фоновый поток, периодически обновляющий и рассылающий курсы валют.

    Args:
        observer: Объект CurrencyObserver.
    """
    while True:
        data = get_currency_rates()
        observer.notify(data)
        time.sleep(10)

currency_observer = CurrencyObserver()

@socketio.on('connect')
def handle_connect():
    """
    Обработчик события подключения клиента. Отправляет клиенту его ID.
    """
    client_id = request.sid
    emit('client_id', {'id': client_id})

@socketio.on('select_currency')
def handle_select_currency(data):
    """
    Обработчик события выбора валюты клиентом. Регистрирует клиента у наблюдателя.

    Args:
        data: Словарь, содержащий код выбранной валюты.
    """
    currency_code = data.get('currency_code')
    client = Client(request.sid)
    currency_observer.register(client, currency_code)
    emit('currency_selected', {'message': f'You selected {currency_code}', 'id': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    """
    Обработчик события отключения клиента. Удаляет клиента из наблюдателя.
    """
    client = Client(request.sid)
    currency_observer.unregister(client)

if __name__ == "__main__":
    threading.Thread(target=currency_updater, args=(currency_observer,)).start()
    socketio.run(app, host='localhost', port=5000, allow_unsafe_werkzeug=True)