# Скрипт для парсинга HTML-страницы, которую создаёт "Алиса AI"
# по адресу https://alice.yandex.ru, версия 1.0.0
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


def save_structured_odt(messages, filename="alice_dialog_structured.odt"):
    doc = OpenDocumentText()

    # Стили для разных типов контента
    heading_style = Style(name="Heading", family="paragraph")
    heading_style.addElement(TextProperties(fontsize="16pt", fontweight="bold"))
    doc.styles.addElement(heading_style)

    code_style = Style(name="Code", family="paragraph")
    code_style.addElement(ParagraphProperties(backgroundcolor="#f0f0f0"))
    code_style.addElement(TextProperties(fontfamily="monospace", fontsize="10pt"))
    doc.styles.addElement(code_style)

    list_style = Style(name="List", family="paragraph")
    list_style.addElement(ParagraphProperties(marginleft="1cm"))
    doc.styles.addElement(list_style)

    for i, msg in enumerate(messages):
        # Получаем весь HTML сообщения
        msg_html = msg.get_attribute("innerHTML")

        # Парсим HTML для определения структуры
        soup = BeautifulSoup(msg_html, 'html.parser')

        for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'ul', 'ol', 'pre', 'blockquote']):
            if element.name == 'p':
                p = P(text=element.get_text())
                doc.text.addElement(p)
            elif element.name in ['h1', 'h2', 'h3']:
                level = int(element.name[1])
                h = H(outlinelevel=level, stylename="Heading", text=element.get_text())
                doc.text.addElement(h)
            elif element.name in ['ul', 'ol']:
                list_elem = List(stylename="List")
                for li in element.find_all('li'):
                    list_item = ListItem()
                    list_item.addElement(P(text=li.get_text()))
                    list_elem.addElement(list_item)
                doc.text.addElement(list_elem)
            elif element.name == 'pre':
                code_text = element.get_text()
                p = P(stylename="Code", text=f"Код:\n{code_text}")
                doc.text.addElement(p)
            elif element.name == 'blockquote':
                quote_text = element.get_text()
                p = P(text=f"Цитата: {quote_text}")
                doc.text.addElement(p)

    doc.save(filename)
    print(f"Структурированный документ сохранён как {filename}")


def login_and_save_cookies():
    """Первый запуск: войти и сохранить куки"""
    service = Service(r'c:\chromedriver\chromedriver-win64\chromedriver.exe')
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get("https://passport.yandex.ru/auth")
        input("Войдите в аккаунт вручную по своим данным, затем нажмите Enter...")

        # Сохраняем куки
        pickle.dump(driver.get_cookies(), open("yandex_cookies.pkl", "wb"))
        print("Куки сохранены в 'yandex_cookies.pkl'")
    finally:
        driver.quit()


def load_cookies_and_continue():
    service = Service(r'c:\chromedriver\chromedriver-win64\chromedriver.exe')
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=service, options=options)

    try:
        cookies = pickle.load(open("yandex_cookies.pkl", "rb"))
        driver.get("https://alice.yandex.ru")

        for cookie in cookies:
            driver.add_cookie(cookie)

        driver.refresh()
        time.sleep(5)
        driver.get(input("Вставьте ссылку страницы для парсинга: "))

        wait = WebDriverWait(driver, 30)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".AliceChat-Message, .Message")))

        time.sleep(10)
        messages = driver.find_elements(By.CSS_SELECTOR, ".AliceChat-Message, .Message")

        if not messages:
            print("Не найдено элементов с сообщениями!")
            return None

        print(f"Найдено {len(messages)} сообщений")
        if messages:
            save_structured_odt(messages)

    except Exception as e:
        print(f"Произошла ошибка: {e}")
        return None

    finally:
        driver.quit()


# Запуск программы
# Проверка: файл существует, это файл, и его размер > 0
if os.path.isfile("yandex_cookies.pkl") and os.path.getsize("yandex_cookies.pkl") > 0:
    load_cookies_and_continue()
else:
    print("Файл куки отсутствует или пустой. Запускаем первый вход...")
    login_and_save_cookies()
    load_cookies_and_continue()
