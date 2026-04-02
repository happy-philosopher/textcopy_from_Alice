# Утилита преобразования неудобочитаемого HTML-файла (unreadable HTML code)
# в форматированный HTML, версия 1.0.0
# Автор: Михаил Качаргин


from bs4 import BeautifulSoup


def format_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    # Функция для рекурсивного форматирования тегов
    def format_tag(tag, level=0):
        # Форматируем отступы
        indent = '  ' * level

        # Получаем имя тега
        tag_name = f'<{tag.name}>'

        # Если есть атрибуты, добавляем их
        if tag.attrs:
            attrs = ' '.join(f'{k}="{v}"' for k, v in tag.attrs.items())
            tag_name = f'<{tag.name} {attrs}>'

        # Формируем закрывающий тег
        close_tag = f'</{tag.name}>'

        # Если тег пустой, возвращаем его сразу
        if not tag.contents:
            return f'{indent}{tag_name}{close_tag}\n'

        # Форматируем содержимое
        formatted_content = ''
        for content in tag.contents:
            if content.name:
                # Рекурсивно форматируем вложенные теги
                formatted_content += format_tag(content, level + 1)
            else:
                # Форматируем текст
                text = str(content).strip()
                if text:
                    formatted_content += f'{indent}  {text}\n'

        return f'{indent}{tag_name}\n{formatted_content}{indent}{close_tag}\n'

    # Форматируем весь документ
    formatted_html = ''
    for child in soup.children:
        if child.name:
            formatted_html += format_tag(child)

    return formatted_html


def process_file(input_file, output_file):
    try:
        with open(input_file, 'r', encoding='utf-8') as file:
            html_content = file.read()

        formatted_content = format_html(html_content)

        with open(output_file, 'w', encoding='utf-8') as file:
            file.write(formatted_content)

        print(f"Файл успешно преобразован и сохранен как {output_file}")

    except FileNotFoundError:
        print(f"Ошибка: файл {input_file} не найден")
    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")


if __name__ == "__main__":
    process_file('message_test.html', 'message_html_formatted.html')
