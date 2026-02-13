import pytest
import time
from playwright.sync_api import Page, expect
from config import LOGIN_URL, BASE_URL, UI_CREDENTIALS, UI_SELECTORS, DB_LIMITS, calculate_tax, calculate_gross


class TestAuthentication:
    """Тесты авторизации - здесь авторизация в каждом тесте отдельно"""

    def test_successful_login(self, page: Page):
        """Тест успешной авторизации"""
        page.goto(LOGIN_URL)
        expect(page.locator(UI_SELECTORS["login"]["username"])).to_be_visible()
        expect(page.locator(UI_SELECTORS["login"]["password"])).to_be_visible()
        expect(page.locator(UI_SELECTORS["login"]["submit"])).to_be_visible()

        page.fill(UI_SELECTORS["login"]["username"],
                  UI_CREDENTIALS["username"])
        page.fill(UI_SELECTORS["login"]["password"],
                  UI_CREDENTIALS["password"])
        page.click(UI_SELECTORS["login"]["submit"])

        expect(page).to_have_url(BASE_URL, timeout=10000)
        expect(page.locator("h2:has-text('Услуги')")).to_be_visible()
        print("Авторизация успешна")

    def test_failed_login_wrong_username(self, page: Page):
        """Тест неудачной авторизации с неправильным логином"""
        page.goto(LOGIN_URL)
        page.fill(UI_SELECTORS["login"]["username"], "wrong_user")
        page.fill(UI_SELECTORS["login"]["password"],
                  UI_CREDENTIALS["password"])
        page.click(UI_SELECTORS["login"]["submit"])

        page.wait_for_timeout(2000)
        assert page.url == LOGIN_URL, "При неверном логине должны остаться на странице логина"
        print("При неверном логине авторизация не проходит")

    def test_failed_login_wrong_password(self, page: Page):
        """Тест неудачной авторизации с неправильным паролем"""
        page.goto(LOGIN_URL)
        page.fill(UI_SELECTORS["login"]["username"],
                  UI_CREDENTIALS["username"])
        page.fill(UI_SELECTORS["login"]["password"], "wrong_password")
        page.click(UI_SELECTORS["login"]["submit"])

        page.wait_for_timeout(2000)
        assert page.url == LOGIN_URL, "При неверном пароле должны остаться на странице логина"
        print("При неверном пароле авторизация не проходит")

    def test_failed_login_empty_credentials(self, page: Page):
        """Тест неудачной авторизации с пустыми полями"""
        page.goto(LOGIN_URL)
        page.click(UI_SELECTORS["login"]["submit"])

        page.wait_for_timeout(2000)
        assert page.url == LOGIN_URL, "При пустых полях должны остаться на странице логина"

        errors = page.locator(".invalid-feedback").count()
        assert errors > 0, "Должны быть ошибки валидации"
        print("При пустых полях авторизация не проходит")


@pytest.mark.usefixtures("authenticated_page")
class TestServicesForm:
    """Тесты формы услуг - одна авторизация на весь класс"""

    @pytest.fixture(autouse=True)
    def cleanup_services(self, authenticated_page: Page):
        """Очистка всех услуг перед каждым тестом"""
        page = authenticated_page
        page.on("dialog", lambda dialog: dialog.accept())
        while page.locator(UI_SELECTORS["services_list"]["delete_button"]).count() > 0:
            page.locator(UI_SELECTORS["services_list"]
                         ["delete_button"]).first.click()
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(1000)
        yield

    def test_form_elements_present(self, authenticated_page: Page):
        """Тест наличия всех элементов формы"""
        page = authenticated_page
        expect(page.locator(
            UI_SELECTORS["service_form"]["name"])).to_be_visible()
        expect(page.locator(
            UI_SELECTORS["service_form"]["quantity"])).to_be_visible()
        expect(page.locator(
            UI_SELECTORS["service_form"]["price"])).to_be_visible()
        expect(page.locator(
            UI_SELECTORS["service_form"]["tax"])).to_be_visible()
        expect(page.locator(
            UI_SELECTORS["service_form"]["gross"])).to_be_visible()
        expect(page.locator(
            UI_SELECTORS["service_form"]["submit"])).to_be_visible()
        print("Все элементы формы присутствуют")

    #  Позитивное тестирование
    def test_tax_calculation_automation(self, authenticated_page: Page):
        """Тест автоматического расчета НДС"""
        page = authenticated_page
        test_cases = [
            (100.0, 22.0, 122.0),
            (250.5, 55.11, 305.61),
            (0.01, 0.0, 0.01),
            (1000.0, 220.0, 1220.0),
            (DB_LIMITS["max_int"], calculate_tax(
                DB_LIMITS["max_int"]), calculate_gross(DB_LIMITS["max_int"])),
            (DB_LIMITS["min_int"], calculate_tax(
                DB_LIMITS["min_int"]), calculate_gross(DB_LIMITS["min_int"])),
        ]
        for price, expected_tax, expected_gross in test_cases:
            price_field = page.locator(UI_SELECTORS["service_form"]["price"])
            price_field.fill(str(price))
            page.wait_for_timeout(500)

            tax_value = float(page.locator(
                UI_SELECTORS["service_form"]["tax"]).input_value() or 0)
            gross_value = float(page.locator(
                UI_SELECTORS["service_form"]["gross"]).input_value() or 0)

            assert abs(
                tax_value - expected_tax) < 0.01, f"Для цены {price}: НДС {tax_value} != {expected_tax}"
            assert abs(
                gross_value - expected_gross) < 0.01, f"Для цены {price}: Итого {gross_value} != {expected_gross}"
            print(f"Цена {price}: НДС={tax_value}, Итого={gross_value}")
            price_field.fill("")

    @pytest.mark.parametrize("price,quantity", [
        (DB_LIMITS["price_min"], DB_LIMITS["quantity_min"]),
        (100, 10),
        (100, 11),
        (100, 99),
        (100, 100),
        (100, 999),
        (100, 1000),
        (100, 99999),
        (100, 10000),
        (100, 10001),
        (100, DB_LIMITS["max_int"]),
        (DB_LIMITS["max_int"], 1),
        (DB_LIMITS["max_int"], DB_LIMITS["max_int"]),
    ])
    
    def test_positive_boundaries_combinations(self, authenticated_page: Page, price, quantity):
        """Позитивное тестирование комбинаций граничных значений с созданием"""
        page = authenticated_page
        services_before = page.locator(
            UI_SELECTORS["services_list"]["items"]).count()

        name = f"Позитив тест price={price} qty={quantity}"
        page.fill(UI_SELECTORS["service_form"]["name"], name)
        page.fill(UI_SELECTORS["service_form"]["quantity"], str(quantity))
        page.fill(UI_SELECTORS["service_form"]["price"], str(price))

        if price > 0:
            page.wait_for_timeout(500)

        page.click(UI_SELECTORS["service_form"]["submit"])
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(2000)

        services_after = page.locator(
            UI_SELECTORS["services_list"]["items"]).count()
        assert services_after > services_before, "Услуга должна создаться"
        print(f"Позитив: price={price}, quantity={quantity} → создана")

    #  Негативное тестирование
    @pytest.mark.parametrize("price,quantity,name,expected_errors", [
        (0, 1, "Тест", ["значение «цена без ндс» должно быть не меньше 0.01"]),
        (-100, 1, "Тест",
         ["значение «цена без ндс» должно быть не меньше 0.01"]),
        (100, 0, "Тест", ["значение «количество» должно быть не меньше 1"]),
        (100, -1, "Тест", ["значение «количество» должно быть не меньше 1"]),
        (DB_LIMITS["max_int"] + 1, 1, "Тест", []),
        (DB_LIMITS["min_int"], 1, "Тест", [
         "значение «цена без ндс» должно быть не меньше 0.01"]),
        (100, 1, "", ["необходимо заполнить «наименование»"]),
        (0.009, 1, "Тест", [
         "значение «цена без ндс» должно быть не меньше 0.01"]),
    ])
    def test_negative_boundaries_combinations(self, authenticated_page: Page, price, quantity, name, expected_errors):
        """Негативное тестирование комбинаций граничных значений"""
        page = authenticated_page
        services_before = page.locator(
            UI_SELECTORS["services_list"]["items"]).count()

        page.fill(UI_SELECTORS["service_form"]["name"], name)
        page.fill(UI_SELECTORS["service_form"]["quantity"], str(quantity))
        page.fill(UI_SELECTORS["service_form"]["price"], str(price))

        if price > 0:
            page.wait_for_timeout(500)

        page.click(UI_SELECTORS["service_form"]["submit"])
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(2000)

        services_after = page.locator(
            UI_SELECTORS["services_list"]["items"]).count()
        assert services_after == services_before, "Услуга НЕ должна создаться"

        if expected_errors:
            error_text = " ".join(page.locator(
                ".invalid-feedback").all_inner_texts()).lower()
            for msg in expected_errors:
                assert msg.lower(
                ) in error_text, f"Не найдено сообщение: {msg}"

        print(
            f"Негатив: price={price}, quantity={quantity}, name='{name}' → отклонено")

    def test_name_validation(self, authenticated_page: Page):
        """Тест валидации длины имени"""
        page = authenticated_page
        test_cases = [
            ("a" * 255, True),
            ("a" * 256, False),
            ("", False),
        ]
        for name, should_pass in test_cases:
            services_before = page.locator(
                UI_SELECTORS["services_list"]["items"]).count()

            page.fill(UI_SELECTORS["service_form"]["name"], name)
            page.fill(UI_SELECTORS["service_form"]["quantity"], "1")
            page.fill(UI_SELECTORS["service_form"]["price"], "100")
            page.wait_for_timeout(500)
            page.click(UI_SELECTORS["service_form"]["submit"])
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(2000)

            services_after = page.locator(
                UI_SELECTORS["services_list"]["items"]).count()

            if should_pass:
                assert services_after > services_before, f"Имя длиной {len(name)} должно создать услугу"
            else:
                assert services_after == services_before, f"Имя длиной {len(name)} НЕ должно создать услугу"

            print(
                f"Имя длиной {len(name)}: {'принято' if services_after > services_before else 'отклонено'}")
            page.fill(UI_SELECTORS["service_form"]["name"], "")

    # Граничные значения PRICE
    @pytest.mark.parametrize("price,should_pass", [
        (0.00, False),     # Не допустимая цена
        (0.01, True),      # Минимальная допустимая цена
        (0.99, True),      # Допустимая цена
        (1.00, True),      # Допустимая цена
        (99999.99, True),  # Допустимая цена
        (100000.00, True),  # Допустимая цена
        (2147483647.00, True),  # max int
        (2147483647.99, False),  # больше max int
        (2147483648.00, False),  # больше max int
        (-0.01, False),    # Отрицательная цена
    ])
    
    def test_price_boundaries(self, authenticated_page: Page, price: float, should_pass: bool):
        """Граничные значения цены - ИСПРАВЛЕНО: 0.01 теперь True"""
        page = authenticated_page
        services_before = page.locator(
            UI_SELECTORS["services_list"]["items"]).count()

        page.fill(UI_SELECTORS["service_form"]
                  ["name"], f"Price boundary {price}")
        page.fill(UI_SELECTORS["service_form"]["quantity"], "1")
        page.fill(UI_SELECTORS["service_form"]["price"], str(price))
        page.wait_for_timeout(800)

        page.click(UI_SELECTORS["service_form"]["submit"])
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(2000)

        services_after = page.locator(
            UI_SELECTORS["services_list"]["items"]).count()

        if should_pass:
            assert services_after > services_before, f"Цена {price} должна создавать услугу"
            print(f"Price {price} → принято")
        else:
            assert services_after == services_before, f"Цена {price} НЕ должна создавать услугу"
            # Наличие сообщения об ошибке
            error_text = " ".join(page.locator(
                ".invalid-feedback").all_inner_texts()).lower()
            assert "значение «цена без ндс» должно быть не меньше 0.01" in error_text, \
                   f"Не найдено сообщение об ошибке для цены {price}"
            print(f"Price {price} → отклонено + сообщение об ошибке")


@pytest.mark.usefixtures("authenticated_page")
class TestCRUDOperations:
    """Тесты CRUD операций"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self, authenticated_page: Page):
        """Настройка перед каждым тестом в классе"""
        self.page = authenticated_page
        self.page.locator(UI_SELECTORS["service_form"]["name"]).fill("")
        self.page.locator(UI_SELECTORS["service_form"]["quantity"]).fill("")
        self.page.locator(UI_SELECTORS["service_form"]["price"]).fill("")
        yield

    def test_create_service(self):
        """Тест создания услуги"""
        services_before = self.page.locator(
            UI_SELECTORS["services_list"]["items"]).count()

        service_name = f"Тестовая услуга {int(time.time())}"
        self.page.fill(UI_SELECTORS["service_form"]["name"], service_name)
        self.page.fill(UI_SELECTORS["service_form"]["quantity"], "5")
        self.page.fill(UI_SELECTORS["service_form"]["price"], "150.50")

        self.page.wait_for_timeout(500)
        self.page.click(UI_SELECTORS["service_form"]["submit"])
        self.page.wait_for_load_state('networkidle')
        self.page.wait_for_timeout(2000)

        services_after = self.page.locator(
            UI_SELECTORS["services_list"]["items"]).count()
        assert services_after > services_before, "Количество услуг не увеличилось"
        print(f"Услуга '{service_name}' создана")

    def test_edit_service(self):
        """Тест редактирования услуги"""
        original_name = f"Для редактирования {int(time.time())}"
        self.page.fill(UI_SELECTORS["service_form"]["name"], original_name)
        self.page.fill(UI_SELECTORS["service_form"]["quantity"], "3")
        self.page.fill(UI_SELECTORS["service_form"]["price"], "200")
        self.page.click(UI_SELECTORS["service_form"]["submit"])
        self.page.wait_for_load_state('networkidle')
        self.page.wait_for_timeout(2000)

        edit_buttons = self.page.locator(
            UI_SELECTORS["services_list"]["edit_button"])
        if edit_buttons.count() > 0:
            edit_buttons.last.click()
            self.page.wait_for_timeout(1000)

            new_name = f"Отредактировано {int(time.time())}"
            self.page.fill(UI_SELECTORS["service_form"]["name"], new_name)
            self.page.click(UI_SELECTORS["service_form"]["submit"])
            self.page.wait_for_load_state('networkidle')
            self.page.wait_for_timeout(2000)
            print(f"Услуга отредактирована: {original_name} -> {new_name}")
        else:
            pytest.skip("Нет услуг для редактирования")

    def test_delete_service(self):
        """Тест удаления услуги - ИСПРАВЛЕНО: используем self.page вместо page"""
        services_before = self.page.locator(
            UI_SELECTORS["services_list"]["items"]).count()

        if services_before == 0:
            self.page.fill(UI_SELECTORS["service_form"]
                           ["name"], f"Для удаления {int(time.time())}")
            self.page.fill(UI_SELECTORS["service_form"]["quantity"], "1")
            self.page.fill(UI_SELECTORS["service_form"]["price"], "100")
            self.page.click(UI_SELECTORS["service_form"]["submit"])
            self.page.wait_for_load_state('networkidle')
            self.page.wait_for_timeout(2000)
            services_before = self.page.locator(
                UI_SELECTORS["services_list"]["items"]).count()

        if services_before > 0:
            self.page.on("dialog", lambda dialog: dialog.accept())
            self.page.locator(
                UI_SELECTORS["services_list"]["delete_button"]).first.click()
            self.page.wait_for_load_state('networkidle')
            self.page.wait_for_timeout(2000)

            services_after = self.page.locator(
                UI_SELECTORS["services_list"]["items"]).count()
            assert services_after < services_before, "Услуга не удалилась"
            print(
                f"Услуга удалена (было: {services_before}, стало: {services_after})")
        else:
            pytest.skip("Нет услуг для удаления")
