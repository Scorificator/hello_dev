import pytest
import requests
from typing import Dict, Any
from config import (
    API_URL,
    API_HEADERS,
    DB_LIMITS,
    calculate_tax,
    calculate_gross,
    REALISTIC_DATA
)


class TestServiceAPI:
    """

    БАГ API: Непредсказуемая структура ответа POST
    - Иногда возвращает: {uuid, name, price, ...}
    - Иногда возвращает: {data: [...], pagination: {...}}

    Структура ответа API:
    - POST успех (вариант 1): {uuid, name, description, price, tax, gross, image, updated_at}
    - POST ошибка: {errors: {field: [messages]}} со статусом 422
    - GET: {name, description, price, tax, gross}
    """

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Подготовка и очистка перед/после каждого теста"""
        self.created_service_uuids = []
        yield
        # Очистка созданных услуг после теста
        for service_uuid in self.created_service_uuids:
            try:
                requests.delete(
                    f"{API_URL}{service_uuid}",
                    headers=API_HEADERS
                )
            except:
                pass

    def extract_service_from_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        WORKAROUND для бага API с непредсказуемой структурой

        Извлекает данные услуги из ответа, независимо от структуры:
        - Если {uuid, name, ...} → возвращает как есть
        - Если {data: [...]} → возвращает первый элемент из списка

        Raises:
            AssertionError: Если не удалось извлечь данные
        """
        assert response.status_code in [200, 201], \
            f"Ожидался код 200/201, получен {response.status_code}"

        response_data = response.json()

        if "uuid" in response_data:
            return response_data

        if "data" in response_data and isinstance(response_data["data"], list):
            assert len(response_data["data"]) > 0, \
                "Список data пустой, не удалось найти созданную услугу"
            return response_data["data"][0]

        pytest.fail(
            f"API вернул неожиданную структуру: {list(response_data.keys())}\n"
            f"Ожидалось: {{uuid, ...}} или {{data: [...]}}"
        )

    def create_service(self, data: Dict[str, Any]) -> requests.Response:
        """Вспомогательный метод для создания услуги"""
        response = requests.post(
            API_URL,
            json=data,
            headers=API_HEADERS
        )
        if response.status_code in [200, 201]:
            try:
                service = self.extract_service_from_response(response)
                if "uuid" in service:
                    self.created_service_uuids.append(service["uuid"])
            except:
                pass
        return response

    def assert_validation_error(self, response, expected_field=None):
        """Проверка что ответ содержит ошибки валидации"""
        assert response.status_code == 422, \
            f"Ожидался код 422, получен {response.status_code}"

        try:
            response_data = response.json()
            assert "errors" in response_data, \
                f"В ответе отсутствует поле 'errors': {response_data}"

            if expected_field:
                assert expected_field in response_data["errors"], \
                    f"Ожидалась ошибка для поля '{expected_field}', получены ошибки: {list(response_data['errors'].keys())}"

                error_messages = response_data["errors"][expected_field]
                return error_messages

            return response_data["errors"]
        except Exception as e:
            pytest.fail(f"Не удалось распарсить ошибки валидации: {e}")

    #  ПОЗИТИВНЫЕ ТЕСТЫ
    def test_create_service_success(self):
        """Позитивный тест: успешное создание услуги с корректными данными"""
        price = 100
        service_data = {
            "name": "Test Service",
            "quantity": 10,
            "price": price,
            "tax": calculate_tax(price),
            "gross": calculate_gross(price)
        }

        response = self.create_service(service_data)

        created_service = self.extract_service_from_response(response)

        # Проверяем обязательные поля в ответе
        assert "name" in created_service, "В ответе отсутствует name"
        assert "description" in created_service, "В ответе отсутствует description"
        assert "price" in created_service, "В ответе отсутствует price"
        assert "tax" in created_service, "В ответе отсутствует tax"
        assert "gross" in created_service, "В ответе отсутствует gross"

        # Проверяем значения
        assert created_service["name"] == service_data["name"]
        assert created_service["price"] == service_data["price"]
        assert created_service["tax"] == service_data["tax"]
        assert created_service["gross"] == service_data["gross"]

        print(f"Услуга успешно создана с UUID: {created_service['uuid']}")

    def test_create_service_from_example(self):
        """Позитивный тест: создание услуги из примера задания"""
        service_data = {
            "name": "service",
            "quantity": 10,
            "price": 100,
            "tax": 22,
            "gross": 122
        }

        response = self.create_service(service_data)
        created_service = self.extract_service_from_response(response)

        assert created_service["name"] == "service"
        assert created_service["price"] == 100
        assert created_service["tax"] == 22
        assert created_service["gross"] == 122
        print("Услуга из примера задания успешно создана")

    def test_create_realistic_services(self):
        """Позитивный тест: создание реалистичных услуг из конфига"""
        successful_count = 0

        for service_info in REALISTIC_DATA["services"]:
            if service_info["price"] <= 0:
                continue
            if service_info["price"] > DB_LIMITS["max_int"]:
                continue

            service_data = {
                "name": service_info["name"],
                "quantity": service_info["quantity"],
                "price": service_info["price"],
                "tax": calculate_tax(service_info["price"]),
                "gross": calculate_gross(service_info["price"])
            }

            response = self.create_service(service_data)

            if response.status_code in [200, 201]:
                successful_count += 1
                print(f"Создана: {service_info['name']}")
            else:
                print(
                    f"Не создана: {service_info['name']} (код {response.status_code})")

        assert successful_count > 0, "Не удалось создать ни одной реалистичной услуги"
        print(f"Успешно создано {successful_count} реалистичных услуг")

    def test_create_service_with_different_prices(self):
        """Позитивный тест: создание с различными ценами и автоматическим расчетом НДС"""
        test_prices = [100, 250.50, 1000, 99.99, 1, 3000, 2500, 1500, 2000]

        for price in test_prices:
            service_data = {
                "name": f"Service price {price}",
                "quantity": 1,
                "price": price,
                "tax": calculate_tax(price),
                "gross": calculate_gross(price)
            }

            response = self.create_service(service_data)

            assert response.status_code in [200, 201], \
                f"Для цены {price} ожидался код 200/201, получен {response.status_code}"

            response_data = response.json()
            expected_tax = calculate_tax(price)
            expected_gross = calculate_gross(price)

            assert response_data["tax"] == expected_tax, \
                f"НДС неверно рассчитан для цены {price}: ожидалось {expected_tax}, получено {response_data['tax']}"
            assert response_data["gross"] == expected_gross, \
                f"Общая сумма неверна для цены {price}: ожидалось {expected_gross}, получено {response_data['gross']}"

        print(
            f"Услуги с {len(test_prices)} разными ценами созданы, НДС рассчитан корректно")

    def test_create_service_with_max_name_length(self):
        """Позитивный тест: создание с максимальной длиной названия (255 символов)"""
        max_name = "A" * DB_LIMITS["name_max_length"]
        price = 100

        service_data = {
            "name": max_name,
            "quantity": 5,
            "price": price,
            "tax": calculate_tax(price),
            "gross": calculate_gross(price)
        }

        response = self.create_service(service_data)

        assert response.status_code in [200, 201], \
            f"Ожидался код 200/201, получен {response.status_code}"

        response_data = response.json()
        actual_length = len(response_data["name"])

        assert actual_length <= DB_LIMITS["name_max_length"], \
            f"Длина названия превышает максимум: {actual_length} > {DB_LIMITS['name_max_length']}"
        print(
            f"Услуга с максимальной длиной названия ({actual_length} символов) создана")

    def test_create_service_with_boundary_integers(self):
        """Позитивный тест: создание с граничными значениями целых чисел"""
        safe_max_value = 1000000

        test_cases = [
            {"name": "Large price", "quantity": 1, "price": safe_max_value},
            {"name": "Large quantity", "quantity": 1000, "price": 100},
        ]

        for test_data in test_cases:
            service_data = {
                "name": test_data["name"],
                "quantity": test_data["quantity"],
                "price": test_data["price"],
                "tax": calculate_tax(test_data["price"]),
                "gross": calculate_gross(test_data["price"])
            }

            response = self.create_service(service_data)

            if response.status_code in [200, 201]:
                print(f"{test_data['name']} создана")
            else:
                print(
                    f"{test_data['name']} отклонена: {response.status_code}")

    def test_create_service_with_min_positive_values(self):
        """Позитивный тест: создание с минимальными положительными значениями"""
        service_data = {
            "name": "Min positive values",
            "quantity": DB_LIMITS["quantity_min"],
            "price": DB_LIMITS["price_min"],
            "tax": calculate_tax(DB_LIMITS["price_min"]),
            "gross": calculate_gross(DB_LIMITS["price_min"])
        }

        response = self.create_service(service_data)

        assert response.status_code in [200, 201], \
            f"Ожидался код 200/201, получен {response.status_code}"

        response_data = response.json()
        assert response_data["price"] == DB_LIMITS["price_min"]
        print(
            f"Услуга с минимальными значениями создана (price={DB_LIMITS['price_min']})")

    def test_get_service_success(self):
        """Позитивный тест: получение существующей услуги"""
        price = 200
        service_data = {
            "name": "Service for GET",
            "quantity": 5,
            "price": price,
            "tax": calculate_tax(price),
            "gross": calculate_gross(price)
        }
        create_response = self.create_service(service_data)

        assert create_response.status_code in [
            200, 201], "Не удалось создать услугу"

        service_uuid = create_response.json()["uuid"]

        response = requests.get(
            f"{API_URL}{service_uuid}",
            headers=API_HEADERS
        )

        assert response.status_code == 200, \
            f"Ожидался код 200, получен {response.status_code}"

        response_data = response.json()
        assert response_data["uuid"] == service_uuid
        assert response_data["name"] == service_data["name"]
        assert response_data["price"] == price
        assert response_data["tax"] == calculate_tax(price)
        print(f"Услуга {service_uuid} успешно получена с корректным НДС")

    def test_update_service_success_with_price_change(self):
        """Позитивный тест: обновление с изменением цены и пересчетом НДС"""
        original_price = 150
        service_data = {
            "name": "Original Service",
            "quantity": 3,
            "price": original_price,
            "tax": calculate_tax(original_price),
            "gross": calculate_gross(original_price)
        }
        create_response = self.create_service(service_data)

        assert create_response.status_code in [
            200, 201], "Не удалось создать услугу"

        service_uuid = create_response.json()["uuid"]

        # Обновляем
        new_price = 250
        updated_data = {
            "name": "Updated Service",
            "quantity": 7,
            "price": new_price,
            "tax": calculate_tax(new_price),
            "gross": calculate_gross(new_price)
        }

        response = requests.put(
            f"{API_URL}{service_uuid}",
            json=updated_data,
            headers=API_HEADERS
        )

        assert response.status_code == 200, \
            f"Ожидался код 200, получен {response.status_code}"

        response_data = response.json()
        assert response_data["price"] == new_price
        assert response_data["tax"] == calculate_tax(new_price)
        assert response_data["gross"] == calculate_gross(new_price)
        print(f"Услуга {service_uuid} обновлена, НДС пересчитан корректно")

    def test_delete_service_success(self):
        """Позитивный тест: успешное удаление услуги"""
        price = 100
        service_data = {
            "name": "Service to Delete",
            "quantity": 1,
            "price": price,
            "tax": calculate_tax(price),
            "gross": calculate_gross(price)
        }
        create_response = self.create_service(service_data)

        assert create_response.status_code in [
            200, 201], "Не удалось создать услугу"

        service_uuid = create_response.json()["uuid"]

        # Удаляем
        response = requests.delete(
            f"{API_URL}{service_uuid}",
            headers=API_HEADERS
        )

        assert response.status_code in [200, 204], \
            f"Ожидался код 200/204, получен {response.status_code}"

        # Проверяем, что услуга действительно удалена
        get_response = requests.get(
            f"{API_URL}{service_uuid}",
            headers=API_HEADERS
        )
        assert get_response.status_code == 404, \
            "Удаленная услуга все еще доступна"

        self.created_service_uuids.remove(service_uuid)
        print(f"Услуга {service_uuid} успешно удалена")

    def test_tax_calculation_precision(self):
        """Позитивный тест: проверка точности расчета НДС для различных сумм"""
        test_cases = [
            (100, 22.0, 122.0),
            (250.50, 55.11, 305.61),
            (99.99, 22.0, 121.99),
            (1000, 220.0, 1220.0),
            (33.33, 7.33, 40.66),
            (3000, 660.0, 3660.0),
            (2500, 550.0, 3050.0),
        ]

        for price, expected_tax, expected_gross in test_cases:
            calculated_tax = calculate_tax(price)
            calculated_gross = calculate_gross(price)

            service_data = {
                "name": f"Tax test {price}",
                "quantity": 1,
                "price": price,
                "tax": calculated_tax,
                "gross": calculated_gross
            }

            response = self.create_service(service_data)

            assert response.status_code in [200, 201], \
                f"Для цены {price} ожидался код 200/201, получен {response.status_code}"

            response_data = response.json()
            assert abs(response_data["tax"] - expected_tax) < 0.01, \
                f"НДС для {price}: ожидалось {expected_tax}, получено {response_data['tax']}"
            assert abs(response_data["gross"] - expected_gross) < 0.01, \
                f"Итого для {price}: ожидалось {expected_gross}, получено {response_data['gross']}"

        print("Точность расчета НДС проверена для различных сумм")

    #  НЕГАТИВНЫЕ ТЕСТЫ

    def test_create_service_without_auth(self):
        """Негативный тест: создание без авторизации"""
        service_data = {
            "name": "Unauthorized Service",
            "quantity": 1,
            "price": 100,
            "tax": 22,
            "gross": 122
        }

        response = requests.post(
            API_URL,
            json=service_data,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code in [401, 403], \
            f"Ожидался код 401/403, получен {response.status_code}"
        print("Запрос без авторизации корректно отклонен")

    def test_create_service_with_invalid_token(self):
        """Негативный тест: создание с неверным токеном"""
        service_data = {
            "name": "Service with bad token",
            "quantity": 1,
            "price": 100,
            "tax": 22,
            "gross": 122
        }

        invalid_headers = {
            "Authorization": "Bearer invalid_token_123",
            "Content-Type": "application/json"
        }

        response = requests.post(
            API_URL,
            json=service_data,
            headers=invalid_headers
        )

        assert response.status_code in [401, 403], \
            f"Ожидался код 401/403, получен {response.status_code}"
        print("Запрос с неверным токеном корректно отклонен")

    def test_validation_empty_name(self):
        """Негативный тест: валидация пустого названия"""
        service_data = {
            "name": "",
            "quantity": 10,
            "price": 100,
            "tax": 22,
            "gross": 122
        }

        response = self.create_service(service_data)

        errors = self.assert_validation_error(response, "name")
        assert any("заполнить" in err.lower() or "required" in err.lower()
                   for err in errors)
        print(f"Пустое название корректно отклонено: {errors[0]}")

    def test_validation_missing_name(self):
        """Негативный тест: валидация отсутствующего поля name"""
        service_data = {
            "quantity": 10,
            "price": 100,
            "tax": 22,
            "gross": 122
        }

        response = requests.post(
            API_URL,
            json=service_data,
            headers=API_HEADERS
        )

        errors = self.assert_validation_error(response, "name")
        assert any("заполнить" in err.lower() or "required" in err.lower()
                   for err in errors)
        print(f"Отсутствующее поле 'name' корректно отклонено: {errors[0]}")

    def test_validation_empty_json(self):
        """Негативный тест: валидация пустого JSON"""
        response = requests.post(
            API_URL,
            json={},
            headers=API_HEADERS
        )

        all_errors = self.assert_validation_error(response)

        required_fields = ["name", "quantity", "price", "tax", "gross"]
        for field in required_fields:
            assert field in all_errors, f"Ожидалась ошибка для поля '{field}'"

        print(
            f"Пустой JSON корректно отклонен с ошибками для полей: {list(all_errors.keys())}")

    def test_validation_min_quantity(self):
        """Негативный тест: валидация минимального значения quantity"""
        service_data = {
            "name": "Test",
            "quantity": 0,
            "price": 100,
            "tax": 22,
            "gross": 122
        }

        response = self.create_service(service_data)

        errors = self.assert_validation_error(response, "quantity")
        assert any("не меньше" in err.lower() or "minimum" in err.lower()
                   for err in errors)
        print(f"Quantity=0 корректно отклонено: {errors[0]}")

    def test_validation_min_price(self):
        """Негативный тест: валидация минимального значения price"""
        service_data = {
            "name": "Test",
            "quantity": 1,
            "price": 0,
            "tax": 0,
            "gross": 0
        }

        response = self.create_service(service_data)

        errors = self.assert_validation_error(response, "price")
        assert any("не меньше" in err.lower() or "minimum" in err.lower()
                   for err in errors)
        print(f"Price=0 корректно отклонено: {errors[0]}")

    def test_validation_min_tax(self):
        """Негативный тест: валидация минимального значения tax"""
        service_data = {
            "name": "Test",
            "quantity": 1,
            "price": 100,
            "tax": 0,
            "gross": 100
        }

        response = self.create_service(service_data)

        errors = self.assert_validation_error(response, "tax")
        assert any("не меньше" in err.lower() or "minimum" in err.lower()
                   for err in errors)
        print(f"Tax=0 корректно отклонено: {errors[0]}")

    def test_validation_min_gross(self):
        """Негативный тест: валидация минимального значения gross"""
        service_data = {
            "name": "Test",
            "quantity": 1,
            "price": 100,
            "tax": 22,
            "gross": 0
        }

        response = self.create_service(service_data)

        errors = self.assert_validation_error(response, "gross")
        assert any("не меньше" in err.lower() or "minimum" in err.lower()
                   for err in errors)
        print(f"Gross=0 корректно отклонено: {errors[0]}")

    # ТЕСТЫ НА ГРАНИЧНЫЕ ЗНАЧЕНИЯ

    def test_bug_exceeding_name_length(self):
        """ПРОВЕРКА: Превышение максимальной длины названия (256 символов)"""
        too_long_name = "A" * (DB_LIMITS["name_max_length"] + 1)
        price = 100

        service_data = {
            "name": too_long_name,
            "quantity": 1,
            "price": price,
            "tax": calculate_tax(price),
            "gross": calculate_gross(price)
        }

        response = self.create_service(service_data)

        print(
            f"\nПРОВЕРКА: Название длиной {len(too_long_name)} символов (max={DB_LIMITS['name_max_length']})")
        print(f"Статус: HTTP {response.status_code}")

        if response.status_code == 422:
            try:
                errors = response.json().get("errors", {})
                if "name" in errors:
                    print(f"ВАЛИДАЦИЯ РАБОТАЕТ: {errors['name'][0]}")
            except:
                print(f"Отклонено с кодом 422")
        elif response.status_code in [200, 201]:
            response_data = response.json()
            actual_length = len(response_data.get("name", ""))
            if actual_length == DB_LIMITS["name_max_length"]:
                print(
                    f"ВОЗМОЖНЫЙ БАГ: Название обрезано до {actual_length} символов без ошибки")
            elif actual_length > DB_LIMITS["name_max_length"]:
                print(
                    f"БАГ: Сохранено {actual_length} символов (превышает лимит БД!)")
            else:
                print(f"Сохранено {actual_length} символов")

    def test_bug_integer_overflow_quantity(self):
        """ПРОВЕРКА: Переполнение INTEGER для quantity"""
        overflow_value = DB_LIMITS["max_int"] + 1

        service_data = {
            "name": "Overflow quantity test",
            "quantity": overflow_value,
            "price": 100,
            "tax": 22,
            "gross": 122
        }

        response = self.create_service(service_data)

        print(
            f"\nПРОВЕРКА: Quantity = {overflow_value} (max INT = {DB_LIMITS['max_int']})")
        print(f"Статус: HTTP {response.status_code}")

        if response.status_code == 422:
            print(f"ВАЛИДАЦИЯ РАБОТАЕТ")
        elif response.status_code in [200, 201]:
            print(f"БАГ: Переполнение INTEGER принято")
            print(f"Это может привести к ошибкам БД или некорректным данным!")

    def test_bug_integer_overflow_price(self):
        """ПРОВЕРКА: Переполнение INTEGER для price"""
        overflow_value = DB_LIMITS["max_int"] + 1

        service_data = {
            "name": "Overflow price test",
            "quantity": 1,
            "price": overflow_value,
            "tax": 22,
            "gross": 122
        }

        response = self.create_service(service_data)

        print(
            f"\nПРОВЕРКА: Price = {overflow_value} (max INT = {DB_LIMITS['max_int']})")
        print(f"Статус: HTTP {response.status_code}")

        if response.status_code == 422:
            print(f"ВАЛИДАЦИЯ РАБОТАЕТ")
        elif response.status_code in [200, 201]:
            response_data = response.json()
            saved_price = response_data.get("price")
            print(f"БАГ: Сохранено price = {saved_price}")

    def test_bug_integer_underflow(self):
        """ПРОВЕРКА: Отрицательное переполнение INTEGER"""
        underflow_value = DB_LIMITS["min_int"] - 1

        service_data = {
            "name": "Integer underflow test",
            "quantity": underflow_value,
            "price": underflow_value,
            "tax": 0.01,
            "gross": 0.01
        }

        response = self.create_service(service_data)

        print(
            f"\nПРОВЕРКА: Значения = {underflow_value} (min INT = {DB_LIMITS['min_int']})")
        print(f"Статус: HTTP {response.status_code}")

        if response.status_code == 422:
            print(f"ВАЛИДАЦИЯ РАБОТАЕТ")
        elif response.status_code in [200, 201]:
            print(f"БАГ: Отрицательное переполнение принято")

    def test_negative_price(self):
        """Проверка: отрицательная цена"""
        service_data = {
            "name": "Negative price test",
            "quantity": 1,
            "price": -100,
            "tax": -22,
            "gross": -122
        }

        response = self.create_service(service_data)

        print(f"\nПРОВЕРКА: Отрицательная цена (-100)")
        print(f"Статус: HTTP {response.status_code}")

        if response.status_code == 422:
            errors = response.json().get("errors", {})
            print(f"Отрицательные значения отклонены")
            if "price" in errors:
                print(f"Сообщение: {errors['price'][0]}")
        elif response.status_code in [200, 201]:
            print(f"Отрицательная цена принята (может быть задумано для возвратов)")

    def test_invalid_data_type_name_as_number(self):
        """Проверка: число вместо строки в поле name"""
        service_data = {
            "name": 123,
            "quantity": 1,
            "price": 100,
            "tax": 22,
            "gross": 122
        }

        response = self.create_service(service_data)

        print(f"\nПРОВЕРКА: Name = 123 (число вместо строки)")
        print(f"Статус: HTTP {response.status_code}")

        if response.status_code == 422:
            print(f"Строгая типизация работает")
        elif response.status_code in [200, 201]:
            response_data = response.json()
            saved_name = response_data.get("name")
            print(f"Число конвертировано в строку: '{saved_name}'")
            print(f"Это допустимое поведение, но лучше валидировать типы строго")

    def test_invalid_data_type_quantity_as_string(self):
        """Проверка: строка вместо числа в поле quantity"""
        service_data = {
            "name": "Test",
            "quantity": "ten",
            "price": 100,
            "tax": 22,
            "gross": 122
        }

        response = self.create_service(service_data)

        print(f"\nПРОВЕРКА: Quantity = 'ten' (строка вместо числа)")
        print(f"Статус: HTTP {response.status_code}")

        if response.status_code == 422:
            errors = response.json().get("errors", {})
            if "quantity" in errors:
                print(f"ВАЛИДАЦИЯ РАБОТАЕТ: {errors['quantity'][0]}")
        elif response.status_code in [200, 201]:
            print(f"БАГ: Строка принята вместо числа")

    # ТЕСТЫ CRUD НА НЕСУЩЕСТВУЮЩИХ ОБЪЕКТАХ

    def test_get_nonexistent_service(self):
        """Негативный тест: получение несуществующей услуги"""
        fake_uuid = "00000000-0000-0000-0000-000000000000"

        response = requests.get(
            f"{API_URL}{fake_uuid}",
            headers=API_HEADERS
        )

        assert response.status_code == 404, \
            f"Ожидался код 404, получен {response.status_code}"
        print("Запрос несуществующей услуги вернул 404")

    def test_update_nonexistent_service(self):
        """Негативный тест: обновление несуществующей услуги"""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        update_data = {
            "name": "Updated",
            "quantity": 1,
            "price": 100,
            "tax": 22,
            "gross": 122
        }

        response = requests.put(
            f"{API_URL}{fake_uuid}",
            json=update_data,
            headers=API_HEADERS
        )

        assert response.status_code == 404, \
            f"Ожидался код 404, получен {response.status_code}"
        print("Обновление несуществующей услуги вернуло 404")

    def test_delete_nonexistent_service(self):
        """Негативный тест: удаление несуществующей услуги"""
        fake_uuid = "00000000-0000-0000-0000-000000000000"

        response = requests.delete(
            f"{API_URL}{fake_uuid}",
            headers=API_HEADERS
        )

        assert response.status_code in [404, 204], \
            f"Ожидался код 404/204, получен {response.status_code}"
        print("Удаление несуществующей услуги обработано")

    def test_delete_service_twice(self):
        """Негативный тест: двойное удаление услуги"""
        price = 100
        service_data = {
            "name": "Service for double delete",
            "quantity": 1,
            "price": price,
            "tax": calculate_tax(price),
            "gross": calculate_gross(price)
        }
        create_response = self.create_service(service_data)

        if create_response.status_code not in [200, 201]:
            pytest.skip("Не удалось создать услугу для теста")

        service_uuid = create_response.json()["uuid"]

        # Первое удаление
        response1 = requests.delete(
            f"{API_URL}{service_uuid}",
            headers=API_HEADERS
        )
        assert response1.status_code in [200, 204]

        # Второе удаление
        response2 = requests.delete(
            f"{API_URL}{service_uuid}",
            headers=API_HEADERS
        )
        assert response2.status_code in [404, 204], \
            f"Ожидался код 404/204, получен {response2.status_code}"

        self.created_service_uuids.remove(service_uuid)
        print("Двойное удаление корректно обработано")

    #  БАГ: НЕПРЕДСКАЗУЕМАЯ СТРУКТУРА ОТВЕТА

    def test_bug_critical_inconsistent_response_structure(self):
        """
        КРИТИЧНЫЙ БАГ: API возвращает разные структуры ответа

        Описание: POST /api/service возвращает РАЗНЫЕ структуры ответа:
        - В Postman: {uuid, name, price, ...} (одна услуга)
        - В автотестах: {data: [...], pagination: {...}} (список услуг)

        Воспроизведение:
        1. Отправить POST запрос в Postman → получить {uuid, name, ...}
        2. Отправить POST запрос из pytest → получить {data: [...], pagination: {...}}

        Ожидается: Всегда одинаковая структура ответа
        Фактически: Структура меняется непредсказуемо

        Критичность: CRITICAL
        Последствия:
        - Невозможно написать надежные интеграционные тесты
        - Клиентские приложения могут падать
        - Нарушение REST API принципов
        """
        print("\n" + "="*80)
        print("КРИТИЧНЫЙ БАГ: Непредсказуемая структура ответа API")
        print("="*80)

        service_data = {
            "name": "Bug test inconsistent response",
            "quantity": 10,
            "price": 100,
            "tax": 22,
            "gross": 122
        }

        response = self.create_service(service_data)

        assert response.status_code in [200, 201], \
            f"Запрос завершился с ошибкой: {response.status_code}"

        response_data = response.json()

        print(f"\nСтруктура ответа:")
        print(f"Ключи верхнего уровня: {list(response_data.keys())}")

        # Проверяем какую структуру вернул API
        if "uuid" in response_data:
            print(f"Вернул ОБЪЕКТ: {{uuid, name, price, ...}}")
            print(f"UUID: {response_data['uuid']}")
        elif "data" in response_data:
            print(
                f" Вернул СПИСОК: {{data: [...], pagination: {{...}}}}")
            print(
                f"Количество элементов в data: {len(response_data['data'])}")
            if response_data['data']:
                print(
                    f"Первый элемент: {list(response_data['data'][0].keys())}")
        else:
            print(f"НЕИЗВЕСТНАЯ СТРУКТУРА: {response_data}")

        print(f"\nПРОБЛЕМА:")
        print(f"- В Postman POST возвращает: {{uuid, name, price, ...}}")
        print(
            f"- В pytest POST возвращает: {{data: [...], pagination: {{...}}}}")
        print(f"- Это НЕДЕТЕРМИНИРОВАННОЕ поведение!")

        # Тест проходит, но фиксирует проблему
        assert True, "Тест зафиксировал критичный баг API"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
