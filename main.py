# Скрипт для парсинга HTML-страницы, которую создаёт "Алиса AI"
# по адресу https://alice.yandex.ru, версия 2.0.0 beta
# Автор: Михаил Качаргин


import os
import time
import pickle
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from odf.opendocument import OpenDocumentText
from odf.text import P, H, List, ListItem
from odf.style import Style, TextProperties, ParagraphProperties
from bs4 import BeautifulSoup
import logging


# Настройка логирования: вывод в консоль с уровнем INFO и форматированием
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%d.%m.%Y %H:%M:%S',
    handlers=[
        logging.FileHandler("parser.log", encoding="utf-8"),
        logging.StreamHandler()  # Вывод в консоль
    ]
)


# КОНСТАНТЫ
# TARGET_URL_TEST = ""
DRIVER_PATH = r'c:\chromedriver\chromedriver-win64\chromedriver.exe'
COOKIE_FILE = "yandex_cookies.pkl"
ODT_FILENAME = "alice_dialog.odt"
LOGIN_URL = "https://passport.yandex.ru/auth"
ALICE_URL = "https://alice.yandex.ru"
MESSAGE_SELECTOR = ".AliceChat-Message:not(.hidden):not(.loading)"
WAIT_TIMEOUT = 30  # секунды ожидания элементов
POST_LOGIN_SLEEP = 5  # секунды сна после логина
POST_LOAD_SLEEP = 10  # секунды сна после загрузки страницы чата


def create_odt_styles(doc):
    """
    Создаёт стили для ODT‑документа (заголовки, код, списки).

    Функция создаёт и регистрирует в документе ODT три стиля:
    * «Heading» — для заголовков (16 pt, жирный);
    * «Code» — для блоков кода (моноширинный шрифт, фон #f0f0f0, 8 pt);
    * «List» — для списков (отступ слева 1 см).

    Args:
        doc (OpenDocumentText): Объект документа ODT, в который будут добавлены стили.

    Returns:
        dict: Словарь со стилями для разных типов контента с ключами:
            * "heading" — стиль для заголовков;
            * "code" — стиль для блоков кода;
            * "list" — стиль для списков.
    """
    # Стиль для заголовков
    heading_style = Style(name="Heading", family="paragraph")
    heading_style.addElement(TextProperties(fontsize="16pt", fontweight="bold"))
    doc.styles.addElement(heading_style)

    # Стиль для кода (моноширинный шрифт, фон)
    code_style = Style(name="Code", family="paragraph")
    code_style.addElement(ParagraphProperties(backgroundcolor="#f0f0f0"))
    code_style.addElement(TextProperties(fontfamily="monospace", fontsize="8pt"))
    doc.styles.addElement(code_style)

    # Стиль для списков (отступ слева)
    list_style = Style(name="List", family="paragraph")
    list_style.addElement(ParagraphProperties(marginleft="1cm"))
    doc.styles.addElement(list_style)

    return {
        "heading": heading_style,
        "code": code_style,
        "list": list_style
    }


def save_structured_odt(messages, filename=ODT_FILENAME):
    """
    Сохраняет структурированные сообщения чата в формате ODT с сохранением форматирования.

    Функция обрабатывает HTML‑контент сообщений, распознаёт структурные элементы
    (заголовки, списки, код, цитаты и т. д.) и преобразует их в соответствующие
    элементы ODT с применением заранее определённых стилей. Дублирующиеся сообщения фильтруются.

    Args:
        messages (list): Список веб‑элементов Selenium, содержащих сообщения чата.
        filename (str): Имя файла для сохранения ODT‑документа. По умолчанию — "alice_dialog.odt".

    Raises:
        PermissionError: Если нет прав для записи в файл.
        OSError: При ошибках файловой системы.
        Exception: При любых других ошибках сохранения файла.
    """
    logging.info(f"Начало сохранения ODT-документа: {filename}")
    doc = OpenDocumentText()
    styles = create_odt_styles(doc)
    processed_hashes = set()  # Храним хэши обработанного текста

    for i, msg in enumerate(messages):
        logging.debug(f"Обработка сообщения {i + 1}/{len(messages)}")
        msg_html = msg.get_attribute("innerHTML")
        soup = BeautifulSoup(msg_html, 'html.parser')

        for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol', 'pre', 'code', 'blockquote']):
            text = element.get_text().strip()
            if not text:
                logging.debug("Пропущен пустой элемент")
                continue

            # Нормализуем текст для сравнения
            normalized_text = ' '.join(text.split())
            text_hash = hash(normalized_text)

            if text_hash in processed_hashes:
                logging.debug("Пропущено дублирующееся содержимое элемента")
                continue
            processed_hashes.add(text_hash)

            if element.name == 'p':
                # Обычный абзац
                p = P(text=element.get_text())
                doc.text.addElement(p)
            elif element.name in ['h1', 'h2', 'h3', 'h4']:
                # Заголовки с уровнем от 1 до 4
                level = int(element.name[1])
                h = H(outlinelevel=level, stylename="Heading", text=element.get_text())
                doc.text.addElement(h)
            elif element.name in ['ul', 'ol']:
                # Маркированные и нумерованные списки
                list_elem = List(stylename="List")
                for li in element.find_all('li'):
                    list_item = ListItem()
                    list_item.addElement(P(text=li.get_text()))
                    list_elem.addElement(list_item)
                doc.text.addElement(list_elem)
            elif element.name == 'pre' or element.name == 'code':
                # Блок кода с моноширинным шрифтом и фоном
                code_text = element.get_text()
                p = P(stylename="Code", text=f"Код:\n{code_text}")
                doc.text.addElement(p)
            elif element.name == 'blockquote':
                # Цитаты с префиксом
                quote_text = element.get_text()
                p = P(text=f"Цитата: {quote_text}")
                doc.text.addElement(p)
        try:
            doc.save(filename)
            logging.info(f"Структурированный документ сохранён как {filename}")
        except PermissionError:
            logging.error(f"Ошибка: нет прав для записи в файл {filename}")
            raise
        except OSError as e:
            logging.error(f"Ошибка файловой системы: {e}")
            raise
        except Exception as e:
            logging.error(f"Неожиданная ошибка при сохранении ODT‑файла: {e}")
            raise


def login_and_save_cookies(driver_path=DRIVER_PATH):
    """
    Выполняет первый запуск: авторизация в аккаунте и сохранение куки в файл.

    Открывает страницу входа, ожидает ручной авторизации пользователя, затем сохраняет
    текущие куки браузера в файл для последующего использования.

    Args:
        driver_path (str): Путь к исполняемому файлу ChromeDriver. По умолчанию берётся из константы DRIVER_PATH.

    Raises:
        Exception: Если возникает ошибка при авторизации или сохранении куки.
    """
    logging.info("Запуск процесса авторизации и сохранения куки")
    service = Service(driver_path)
    options = webdriver.ChromeOptions()
    driver = None

    try:
        driver = webdriver.Chrome(service=service, options=options)
        logging.debug(f"Открытие страницы входа: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        input("Войдите в аккаунт вручную по своим данным, затем нажмите Enter...")

        # Сохраняем куки ДО закрытия драйвера
        logging.info("Сохранение куки в файл")
        with open(COOKIE_FILE, "wb") as f:
            pickle.dump(driver.get_cookies(), f)
        logging.info(f"Куки сохранены в '{COOKIE_FILE}'")
    except Exception as e:
        logging.error(f"Ошибка при авторизации: {e}")
        raise
    finally:
        if driver:  # проверяем, что драйвер существует
            driver.quit()


def load_cookies_and_continue(driver_path=DRIVER_PATH):
    """
    Загружает сохранённые куки и продолжает работу с авторизацией в чате Алисы.

    Загружает куки из файла, применяет их к браузеру, переходит на целевую страницу чата,
    загружает все сообщения (с прокруткой), фильтрует дубликаты и сохраняет результат.

    Args:
        driver_path (str): Путь к исполняемому файлу ChromeDriver. По умолчанию берётся из константы DRIVER_PATH.

    Returns:
        bool: True, если операция прошла успешно (сообщения найдены и сохранены),
               False в случае ошибок (файл куки не найден, сообщения не найдены и т. д.).
    """
    logging.info("Загрузка куки и продолжение работы")
    service = Service(driver_path)
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=service, options=options)

    try:
        with open(COOKIE_FILE, "rb") as f:
            cookies = pickle.load(f)
        logging.debug("Куки загружены из файла")
        driver.get(ALICE_URL)

        for cookie in cookies:
            driver.add_cookie(cookie)

        driver.refresh()
        time.sleep(POST_LOGIN_SLEEP)

        target_url = input("Вставьте ссылку страницы для парсинга: ")
        # target_url = TARGET_URL_TEST  # Тестирование одного адреса
        logging.debug(f"Переход на целевую страницу: {target_url}")
        driver.get(target_url)
        scroll_to_load_all_messages(driver, MESSAGE_SELECTOR)

        # Ждём появления сообщений
        wait = WebDriverWait(driver, WAIT_TIMEOUT)
        wait.until(EC.visibility_of_all_elements_located((By.CSS_SELECTOR, MESSAGE_SELECTOR)))
        time.sleep(POST_LOAD_SLEEP)

        messages = driver.find_elements(By.CSS_SELECTOR, MESSAGE_SELECTOR)

        if not messages:
            logging.warning("Не найдено элементов с сообщениями после прокрутки!")
            return False

        logging.info(f"Найдено {len(messages)} сообщений")

        # Фильтруем дубликаты по надёжным идентификаторам и тексту
        unique_messages = []
        seen_identifiers = set()

        for msg in messages:
            # 1. Пытаемся получить уникальный ID (data-id, id)
            msg_id = msg.get_attribute("data-id") or msg.get_attribute("id")
            if msg_id:
                if msg_id in seen_identifiers:
                    logging.debug(f"Пропущено сообщение с дублирующим ID: {msg_id}")
                    continue
                seen_identifiers.add(msg_id)
                unique_messages.append(msg)
                continue

            # 2. Если ID нет, используем хэш текста (нормализованного)
            msg_text = msg.get_attribute("textContent").strip()
            if not msg_text:
                logging.debug("Пропущен пустой элемент")
                continue

            # Нормализуем текст: убираем лишние пробелы и переносы
            normalized_text = ' '.join(msg_text.split())
            text_hash = hash(normalized_text)

            if text_hash in seen_identifiers:
                logging.debug("Пропущено сообщение с дублирующим текстом")
                continue
            seen_identifiers.add(text_hash)
            unique_messages.append(msg)

        logging.info(f"Найдено {len(messages)} сообщений, после фильтрации: {len(unique_messages)}")
        save_structured_odt(unique_messages)
        logging.info(f"Удалено дубликатов: {len(messages) - len(unique_messages)}")
        return True

    except FileNotFoundError:
        logging.error("Файл куки не найден")
        return False
    except Exception as e:
        logging.error(f"Произошла ошибка: {e}")
        return False
    finally:
        driver.quit()


def scroll_to_load_all_messages(driver, selector, max_scrolls=10):
    """
    Прокручивает страницу вниз для загрузки всех сообщений чата.

    Эмулирует прокрутку страницы до конца, ожидая подгрузки динамического контента.
    Останавливается, если после прокрутки высота страницы не изменилась (достигнут конец).

    Args:
        driver (webdriver.Chrome): Экземпляр драйвера Selenium.
        selector (str): CSS‑селектор для элементов сообщений, используемых для контроля загрузки.
        max_scrolls (int): Максимальное количество попыток прокрутки. По умолчанию — 10.

    """
    logging.info("Начало прокрутки для загрузки всех сообщений")
    last_height = driver.execute_script("return document.body.scrollHeight")
    actual_scrolls = 0  # счётчик реальных прокруток

    for i in range(max_scrolls):
        logging.debug(f"Прокрутка {i + 1}/{max_scrolls}")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)  # ждём подгрузки
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            logging.info("Достигнут конец страницы, прокрутка завершена")
            break
        last_height = new_height
        actual_scrolls += 1
    logging.info(f"Прокрутка завершена после {actual_scrolls} итераций")


def save_as_txt(messages, filename="alice_dialog.txt"):
    """
    Сохраняет текст сообщений чата в простом текстовом файле.

    Извлекает текстовое содержимое каждого сообщения и записывает в файл, разделяя
    сообщения линией из 50 дефисов.

    Args:
        messages (list): Список веб‑элементов Selenium с сообщениями чата.
        filename (str): Имя файла для сохранения. По умолчанию — "alice_dialog.txt".
    """
    logging.info(f"Начало сохранения в текстовый файл: {filename}")
    with open(filename, "w", encoding="utf-8") as f:
        for msg in messages:
            f.write(msg.get_attribute("textContent") + "\n" + "-" * 50 + "\n")
    logging.info(f"Текст сохранён как {filename}")


def save_as_json(messages, filename="alice_dialog.json"):
    """
    Сохраняет сообщения чата в формате JSON с сохранением HTML‑структуры.

    Для каждого сообщения сохраняются два поля: текст и полный HTML‑код.

    Args:
        messages (list): Список веб‑элементов Selenium с сообщениями чата.
        filename (str): Имя файла для сохранения. По умолчанию — "alice_dialog.json".
    """
    logging.info(f"Начало сохранения в JSON-файл: {filename}")
    import json
    data = []
    for msg in messages:
        data.append({
            "text": msg.get_attribute("textContent"),
            "html": msg.get_attribute("innerHTML")
        })
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logging.info(f"Данные сохранены как {filename}")



# Запуск программы
if __name__ == "__main__":
    logging.info("Запуск программы парсинга чата Алисы")
    if os.path.isfile(COOKIE_FILE) and os.path.getsize(COOKIE_FILE) > 0:
        logging.info("Используем сохранённые куки...")
        success = load_cookies_and_continue()
        if not success:
            logging.warning("Попытка авторизации через логин...")
            login_and_save_cookies()
            load_cookies_and_continue()  # Повторная попытка после авторизации
    else:
        logging.warning("Файл куки отсутствует или пустой. Запускаем первый вход...")
        login_and_save_cookies()
        logging.info("Теперь загружаем данные с использованием новых куки...")
        load_cookies_and_continue()
    logging.info("Программа завершена")
