"""
Фикстуры для pytest + Playwright
"""
import pytest
from playwright.sync_api import Page, Browser, BrowserContext, Playwright
from config import LOGIN_URL, UI_CREDENTIALS, UI_SELECTORS


@pytest.fixture(scope="session")
def playwright_instance() -> Playwright:
    """Создаем экземпляр Playwright"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture(scope="session")
def browser(playwright_instance: Playwright) -> Browser:
    """Создаем браузер"""
    browser = playwright_instance.chromium.launch(headless=False)
    yield browser
    browser.close()


@pytest.fixture
def context(browser: Browser) -> BrowserContext:
    """Создаем контекст (function scope для тестов авторизации)"""
    context = browser.new_context()
    yield context
    context.close()


@pytest.fixture
def page(context: BrowserContext) -> Page:
    """Создаем страницу (function scope)"""
    page = context.new_page()
    yield page
    page.close()


@pytest.fixture(scope="class")
def class_context(browser: Browser) -> BrowserContext:
    """Создаем контекст для класса (class scope)"""
    context = browser.new_context()
    yield context
    context.close()


@pytest.fixture(scope="class")
def class_page(class_context: BrowserContext) -> Page:
    """Создаем страницу для класса (class scope)"""
    page = class_context.new_page()
    yield page
    page.close()


@pytest.fixture(scope="class")
def authenticated_page(class_page: Page) -> Page:
    """Страница с выполненной авторизацией - один раз на класс"""
    page = class_page
    page.goto(LOGIN_URL)
    page.fill(UI_SELECTORS["login"]["username"], UI_CREDENTIALS["username"])
    page.fill(UI_SELECTORS["login"]["password"], UI_CREDENTIALS["password"])
    page.click(UI_SELECTORS["login"]["submit"])
    page.wait_for_timeout(3000)
    # Проверяем что авторизация прошла успешно
    if page.url == LOGIN_URL:
        pytest.fail("Авторизация не удалась")
    yield page
