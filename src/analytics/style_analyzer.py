"""
Модуль для анализа стилей интерфейсных элементов веб-сайта.
Читает список страниц из отчета link_checker и анализирует стили каждой страницы.
"""

import os
import time
import json
import glob
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


class StyleAnalyzer:
    """
    Класс для анализа стилей элементов веб-страницы через Selenium.
    """
    
    # Предустановленные популярные разрешения
    POPULAR_VIEWPORTS = {
        'desktop_full_hd': (1920, 1080, 'Десктоп Full HD'),
        'desktop_hd': (1366, 768, 'Десктоп HD'),
        'desktop_small': (1280, 720, 'Десктоп малый'),
        'tablet_portrait': (768, 1024, 'Планшет (вертикально)'),
        'tablet_landscape': (1024, 768, 'Планшет (горизонтально)'),
        'mobile_iphone_se': (375, 667, 'iPhone SE/6/7/8'),
        'mobile_iphone_12': (390, 844, 'iPhone 12/13/14'),
        'mobile_pixel': (412, 915, 'Google Pixel'),
        'mobile_samsung': (360, 800, 'Samsung Galaxy')
    }
    
    # CSS-свойства для извлечения
    STYLE_PROPERTIES = [
        'color', 'background-color', 'font-size', 'font-family',
        'font-weight', 'width', 'height', 'margin', 'padding',
        'border-radius', 'box-shadow', 'display', 'position',
        'line-height', 'text-align', 'opacity', 'z-index'
    ]
    
    # CSS-селекторы для поиска элементов
    ELEMENT_SELECTORS = [
        'div', 'section', 'header', 'footer', 'main', 'article',
        'button', 'a', 'input', 'form', 'nav', 'aside', 'h1', 'h2', 'h3',
        'h4', 'h5', 'h6', 'p', 'span', 'img', 'ul', 'ol', 'li'
    ]
    
    def __init__(self, headless: bool = True):
        self.driver = None
        self.headless = headless
        self._init_driver()
    
    def _init_driver(self):
        options = Options()
        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            self.driver = webdriver.Chrome(options=options)
            print("Драйвер Chrome успешно запущен")
        except Exception as e:
            print(f"Ошибка запуска драйвера: {e}")
    
    def load_page(self, url: str):
        if not self.driver:
            self._init_driver()
        print(f"  Загружается: {url[:80]}...")
        self.driver.get(url)
        time.sleep(2)
    
    def extract_element_styles(self, element) -> Dict[str, str]:
        styles = {}
        for prop in self.STYLE_PROPERTIES:
            try:
                styles[prop] = element.value_of_css_property(prop)
            except:
                styles[prop] = None
        return styles
    
    def extract_all_elements(self) -> List[Dict[str, Any]]:
        elements = []
        
        for selector in self.ELEMENT_SELECTORS:
            try:
                found_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in found_elements:
                    try:
                        element_id = element.get_attribute('id') or ''
                        class_name = element.get_attribute('class') or ''
                        tag_name = element.tag_name
                        text = element.text[:150] if element.text else ''
                        
                        if not text and not element_id and not class_name:
                            continue
                        
                        styles = self.extract_element_styles(element)
                        
                        elements.append({
                            'tag': tag_name,
                            'id': element_id,
                            'class': class_name,
                            'text': text,
                            'styles': styles
                        })
                    except:
                        continue
            except:
                continue
        
        return elements
    
    def analyze_page(self, url: str, viewports: List[Tuple[str, int, int, str]] = None) -> Dict[str, Any]:
        self.load_page(url)
        real_url = self.driver.current_url
        
        if not viewports:
            viewports = [('desktop_full_hd', 1920, 1080, 'Десктоп Full HD')]
        
        viewports_results = []
        
        for name, width, height, description in viewports:
            print(f"    Анализ для {description} ({width}x{height})...")
            self.driver.set_window_size(width, height)
            time.sleep(1.5)
            elements = self.extract_all_elements()
            
            viewports_results.append({
                'viewport_name': name,
                'viewport_description': description,
                'width': width,
                'height': height,
                'elements_count': len(elements),
                'elements': elements
            })
        
        return {
            'url': real_url,
            'timestamp': datetime.now().isoformat(),
            'viewports': viewports_results
        }
    
    def close(self):
        if self.driver:
            self.driver.quit()
            print("Браузер закрыт")


def find_latest_report(reports_dir: str = 'data/reports') -> Optional[str]:
    """Находит самый свежий отчет link_checker."""
    report_files = glob.glob(f"{reports_dir}/link_check_report_*.txt")
    if not report_files:
        return None
    return max(report_files, key=os.path.getctime)


def extract_urls_from_report(report_file: str) -> List[str]:
    """
    Извлекает URL страниц из отчета link_checker
    """
    urls = []
    with open(report_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('--- СТРАНИЦА'):
                parts = line.split(': ', 1)
                if len(parts) == 2:
                    url = parts[1].strip().split(' ---')[0]
                    urls.append(url)
    return urls


def get_viewports_from_user() -> List[Tuple[str, int, int, str]]:
    """Запрашивает у пользователя разрешения для проверки."""
    viewports = []
    
    print("\n" + "=" * 70)
    print("НАСТРОЙКА РАЗРЕШЕНИЙ ДЛЯ АНАЛИЗА СТИЛЕЙ")
    print("=" * 70)
    print("\nВыберите вариант:")
    print("  1 - Проверить одно разрешение (по умолчанию 1920x1080)")
    print("  2 - Выбрать из популярных разрешений")
    print("  3 - Задать вручную")
    
    choice = input("\nВаш выбор (1-3, Enter=1): ").strip() or '1'
    
    if choice == '1':
        print("\nДоступные разрешения по умолчанию:")
        print("  1 - Десктоп Full HD (1920x1080)")
        print("  2 - Планшет (768x1024)")
        print("  3 - Телефон (375x667)")
        print("  4 - Задать свои значения")
        
        default_choice = input("Выберите (1-4, Enter=1): ").strip() or '1'
        
        if default_choice == '1':
            viewports = [('desktop', 1920, 1080, 'Десктоп Full HD')]
        elif default_choice == '2':
            viewports = [('tablet', 768, 1024, 'Планшет (вертикально)')]
        elif default_choice == '3':
            viewports = [('mobile', 375, 667, 'Телефон iPhone SE')]
        elif default_choice == '4':
            name = input("Название: ").strip() or 'custom'
            width = int(input("Ширина (px): "))
            height = int(input("Высота (px): "))
            viewports = [(name, width, height, f"{width}x{height}")]
    
    elif choice == '2':
        print("\nПопулярные разрешения:")
        items = list(StyleAnalyzer.POPULAR_VIEWPORTS.items())
        for i, (key, (w, h, desc)) in enumerate(items, 1):
            print(f"  {i}. {desc} ({w}x{h})")
        print(f"  {len(items) + 1}. Выбрать несколько")
        
        preset_choice = input(f"\nВыберите номер (1-{len(items)}, Enter=1): ").strip() or '1'
        
        if preset_choice == str(len(items) + 1):
            print("\nВводите номера через запятую (например: 1,3,5)")
            multi_choice = input("Ваш выбор: ").strip()
            indices = [int(x.strip()) for x in multi_choice.split(',')]
            for idx in indices:
                if 1 <= idx <= len(items):
                    key, (w, h, desc) = items[idx - 1]
                    viewports.append((key, w, h, desc))
        else:
            idx = int(preset_choice)
            if 1 <= idx <= len(items):
                key, (w, h, desc) = items[idx - 1]
                viewports.append((key, w, h, desc))
    
    elif choice == '3':
        print("\nВведите разрешения. Для завершения оставьте название пустым.")
        while True:
            name = input("\nНазвание разрешения (например, desktop, mobile): ").strip()
            if not name:
                break
            try:
                width = int(input("Ширина (px): "))
                height = int(input("Высота (px): "))
                viewports.append((name, width, height, f"{name} ({width}x{height})"))
                print(f"  Добавлено: {width}x{height}")
            except ValueError:
                print("  Ошибка! Ширина и высота должны быть числами.")
    
    print(f"\nБудет проверено разрешений: {len(viewports)}")
    for _, w, h, desc in viewports:
        print(f"  • {desc} ({w}x{h})")
    
    return viewports


def main():
    print("=" * 70)
    print("АНАЛИЗ СТИЛЕЙ ВЕБ-СТРАНИЦ")
    print("=" * 70)
    
    # 1. Находим последний отчет link_checker
    report_file = find_latest_report()
    if not report_file:
        print("\nОшибка: Не найден отчет link_checker в папке data/reports/")
        print("Сначала запусти link_checker.py для сбора страниц.")
        return
    
    print(f"\nНайден отчет: {os.path.basename(report_file)}")
    
    # 2. Извлекаем URL страниц из отчета
    urls = extract_urls_from_report(report_file)
    if not urls:
        print("\nОшибка: Не удалось извлечь URL страниц из отчета.")
        return
    
    print(f"Найдено страниц: {len(urls)}")
    
    # 3. Запрашиваем разрешения
    viewports = get_viewports_from_user()
    
    # 4. Анализируем каждую страницу
    os.makedirs('data/style_analysis', exist_ok=True)
    analyzer = StyleAnalyzer(headless=True)
    
    try:
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] Анализ страницы:")
            result = analyzer.analyze_page(url, viewports=viewports)
            all_results.append(result)
            
            # Сохраняем результат каждой страницы
            domain = urlparse(url).netloc.replace('.', '_')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            page_file = f"data/style_analysis/page_{i}_{timestamp}.json"
            with open(page_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"    Сохранено: {page_file}")
    
    finally:
        analyzer.close()
    
    print("\n" + "=" * 70)
    print("АНАЛИЗ ЗАВЕРШЕН")
    print("=" * 70)
    print(f"Проанализировано страниц: {len(all_results)}")
    print(f"Результаты сохранены в: data/style_analysis/")


if __name__ == "__main__":
    main()