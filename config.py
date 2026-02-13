"""
Конфигурация тестов с реалистичными данными
"""
import os

from dotenv import load_dotenv

load_dotenv()

# URL приложения
BASE_URL = "https://app.evgenybelkin.ru/"
LOGIN_URL = f"{BASE_URL}site/login"
SERVICES_URL = BASE_URL

# Данные для авторизации (из .env)
UI_CREDENTIALS = {
    "username": os.environ.get("UI_USERNAME", ""),
    "password": os.environ.get("UI_PASSWORD", ""),
}
# API данные
API_URL = f"{BASE_URL}api/service/"
API_HEADERS = {
    "Authorization": f"Bearer {os.environ.get('API_TOKEN', '')}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

DB_LIMITS = {
    "name_max_length": 255,
    "min_int": -2147483648,
    "max_int": 2147483647,
    "tax_rate": 0.22,

    "price_min": 1,
    "quantity_min": 1,
    "tax_min": 0.01,
    "gross_min": 0.01
}

REALISTIC_DATA = {
    "services": [
        # Типичные услуги
        {"name": "Консультация специалиста", "quantity": 1, "price": 3000},
        {"name": "Техническое обслуживание сервера", "quantity": 1,
            "price": 2147483646},  # Почти максимальное INT
        {"name": "Разработка мобильного приложения", "quantity": 1,
            "price": 2147483648},  # Превышает INT (должно быть float)
        {"name": "SEO-оптимизация сайта", "quantity": 1,
            "price": 2147483647.00},  # Максимальное INT как float
        {"name": "Обучение работе с CRM", "quantity": 10, "price": 2500},
        # Услуги с разными ценами
        {"name": "Ремонт компьютера", "quantity": 1,
            "price": -3500},  # Отрицательная цена
        {"name": "Установка Windows", "quantity": 1, "price": 2000},
        {"name": "Чистка от вирусов", "quantity": 1, "price": 1500},
        # Пример из задания
        {"name": "service", "quantity": 10, "price": 100.00},
    ],

    "scenarios": [
        {"description": "Мелкий заказ", "quantity": 1, "price": 100},
        {"description": "Средний заказ", "quantity": 5, "price": 1000},
        {"description": "Крупный заказ", "quantity": 100, "price": 500},
        {"description": "Оптовая покупка", "quantity": 50, "price": 250},
        {"description": "Мелкий опт", "quantity": 10, "price": 15000},
    ]
}
# Селекторы
UI_SELECTORS = {
    "login": {
        "username": "#loginform-username",
        "password": "#loginform-password",
        "submit": "button[name='login-button']"
    },
    "service_form": {
        "name": "#serviceform-name",
        "quantity": "#serviceform-quantity",
        "price": "#serviceform-price",
        "tax": "#serviceform-tax",
        "gross": "#serviceform-gross",
        "submit": "button[name='contact-button']",
        "error": ".invalid-feedback"
    },
    "services_list": {
        "items": ".list-group-item",
        "item_name": "h5",
        "edit_button": "a[href*='/site/index?id=']",
        "delete_button": "a[href*='/site/delete?id=']",
        "quantity_badge": ".badge.bg-primary",
        "price_badge": ".badge.bg-info",
        "tax_badge": ".badge.bg-secondary",
        "gross_badge": ".badge.bg-success"
    }
}
# Формулы расчета


def calculate_tax(price):
    """Расчет НДС по ставке 22%"""
    return round(price * DB_LIMITS["tax_rate"], 2)


def calculate_gross(price):
    """Расчет суммы с НДС"""
    tax = calculate_tax(price)
    return round(price + tax, 2)
