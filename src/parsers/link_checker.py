"""
Линк-чекер для аудита сайтов: обходит страницы, проверяет ссылки, создает отчет.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
from typing import Set, List, Tuple, Dict, Optional
import os
from datetime import datetime
import shutil


class LinkChecker:
    """
    Класс для проверки ссылок на сайте.
    """
    
    def __init__(self, start_url: str, delay: float = 1.0):
        """
        Инициализация чекера.
        
        Args:
            start_url: Начальный URL
            delay: Задержка между запросами (секунды)
        """
        self.start_url = start_url.rstrip('/')
        self.delay = delay
        self.visited_pages: Set[str] = set()
        
        # Структуры для хранения ссылок
        self.links_per_page: Dict[str, Set[str]] = {}           # Страница -> все ссылки на ней
        self.link_to_pages: Dict[str, Set[str]] = {}            # Ссылка -> страницы, где встречается
        
        # Статистика
        self.all_links: Set[str] = set()                         # Все уникальные ссылки
        self.broken_links: List[Tuple[str, int, str]] = []       # Битые ссылки (url, статус, тип)
        
        # Временная папка для HTML
        self.temp_html_dir = 'data/temp_html'
        
        # Заголовки для имитации реального браузера
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }
        
        print(f"\nНАЧАЛАСЬ ПРОВЕРКА САЙТА: {self.start_url}")
        print("=" * 60)
    
    def is_same_domain(self, url: str) -> bool:
        """Проверяет, ведет ли ссылка на тот же домен."""
        base_domain = urlparse(self.start_url).netloc
        url_domain = urlparse(url).netloc
        return base_domain == url_domain
    
    def normalize_url(self, url: str) -> str:
        """Приводит URL к нормальному виду (убирает якоря и концевой слеш)."""
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized
    
    def build_absolute_url(self, base_url: str, href: str) -> str:
        """
        Строит абсолютный URL из базового и относительного пути.
        """
        if href.startswith(('http://', 'https://')):
            return href
        return urljoin(base_url, href)
    
    def get_link_type(self, url: str) -> str:
        """
        Определяет тип ссылки по протоколу.
        Возвращает 'http' (для http/https) или 'other' (для всего остального).
        """
        if url.startswith(('http://', 'https://')):
            return 'http'
        else:
            return 'other'
    
    def get_page_links(self, url: str) -> Tuple[Set[str], str]:
        """
        Скачивает страницу и извлекает из нее ссылки.
        
        Returns:
            (все_ссылки_на_странице, html_содержимое)
        """
        all_page_links = set()
        html_content = ""
        
        try:
            print(f"Скачивается: {url}")
            
            # Используем сессию для сохранения куки и заголовков
            session = requests.Session()
            session.headers.update(self.headers)
            
            response = session.get(url, timeout=15)
            response.encoding = 'utf-8'
            html_content = response.text
            
            if response.status_code != 200:
                print(f"Код ответа: {response.status_code}")
                return all_page_links, html_content
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].strip()
                
                if href.startswith('#'):
                    continue
                
                full_url = self.build_absolute_url(url, href)
                
                if self.get_link_type(full_url) == 'http':
                    normalized = self.normalize_url(full_url)
                    all_page_links.add(normalized)
            
            print(f"Найдено ссылок: {len(all_page_links)}")
            
        except requests.RequestException as e:
            print(f"Ошибка при скачивании: {e}")
        
        return all_page_links, html_content
    
    def check_link_status(self, url: str) -> Tuple[bool, int]:
        """
        Проверяет, работает ли HTTP/HTTPS ссылка.
        Использует GET-запрос с полными заголовками браузера.
        """
        try:
            session = requests.Session()
            session.headers.update(self.headers)
            
            response = session.get(url, timeout=15, allow_redirects=True)
            
            # Считаем успешными коды 200-399
            is_working = response.status_code < 400
            return is_working, response.status_code
            
        except requests.Timeout:
            return False, 408  # Request Timeout
        except requests.ConnectionError:
            return False, 521  # Web Server Is Down
        except requests.RequestException:
            return False, 0
    
    def crawl_and_check(self, max_pages: Optional[int] = None):
        """
        Обходит сайт и проверяет все найденные ссылки.
        """
        queue = [self.start_url]
        
        os.makedirs(self.temp_html_dir, exist_ok=True)
        
        print("\nЭТАП 1: ОБХОД СТРАНИЦ")
        print("-" * 40)
        
        page_counter = 0
        while queue:
            if max_pages is not None and page_counter >= max_pages:
                print(f"\nДостигнут лимит страниц: {max_pages}")
                break
            
            current_url = queue.pop(0)
            
            if current_url in self.visited_pages:
                continue
            
            page_counter += 1
            print(f"\n[{page_counter}] Обрабатывается: {current_url}")
            
            links_on_page, html = self.get_page_links(current_url)
            
            if html:
                filename = f"{self.temp_html_dir}/page_{page_counter}.html"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(html)
            
            self.links_per_page[current_url] = links_on_page
            
            for link in links_on_page:
                if self.is_same_domain(link):
                    normalized = self.normalize_url(link)
                    if normalized not in self.visited_pages and normalized not in queue:
                        queue.append(normalized)
                
                if link not in self.link_to_pages:
                    self.link_to_pages[link] = set()
                self.link_to_pages[link].add(current_url)
                
                self.all_links.add(link)
            
            self.visited_pages.add(current_url)
            time.sleep(self.delay)
        
        print(f"\nОбход завершен! Обработано страниц: {len(self.visited_pages)}")
        print(f"Всего найдено уникальных ссылок: {len(self.all_links)}")
        
        print("\nЭТАП 2: ПРОВЕРКА ССЫЛОК")
        print("-" * 40)
        
        working_count = 0
        broken_count = 0
        
        total_links = len(self.all_links)
        for i, link in enumerate(sorted(self.all_links), 1):
            print(f"  [{i}/{total_links}] Проверяю: {link[:60]}...")
            
            is_working, status = self.check_link_status(link)
            
            if is_working:
                working_count += 1
                print(f"    {status} OK")
            else:
                broken_count += 1
                self.broken_links.append((link, status, 'http'))
                print(f"    {status} ОШИБКА")
            
            time.sleep(0.5)
        
        self.print_report(working_count, broken_count)
        self.save_detailed_report()
    
    def print_report(self, working: int, broken: int):
        """Выводит итоговый отчет."""
        print("\n" + "=" * 60)
        print("ИТОГОВЫЙ ОТЧЕТ")
        print("=" * 60)
        print(f"Сайт: {self.start_url}")
        print(f"Страниц обработано: {len(self.visited_pages)}")
        print(f"Всего ссылок найдено: {len(self.all_links)}")
        print(f"Рабочих ссылок: {working}")
        print(f"Битых ссылок: {broken}")
        print("=" * 60)
    
    def save_detailed_report(self):
        """Сохраняет детальный отчет."""
        os.makedirs('data/reports', exist_ok=True)
        
        filename = f"data/reports/link_check_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("ОТЧЕТ О ПРОВЕРКЕ ССЫЛОК\n")
            f.write(f"Сайт: {self.start_url}\n")
            f.write(f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            f.write("ОБЩАЯ СТАТИСТИКА:\n")
            f.write(f"  Страниц обработано: {len(self.visited_pages)}\n")
            f.write(f"  Всего ссылок найдено: {len(self.all_links)}\n")
            f.write(f"  Битых ссылок: {len(self.broken_links)}\n\n")
            
            f.write("=" * 80 + "\n")
            f.write("ДЕТАЛЬНЫЙ ОТЧЕТ ПО СТРАНИЦАМ\n")
            f.write("=" * 80 + "\n")
            
            for i, page in enumerate(sorted(self.visited_pages), 1):
                f.write(f"\n--- СТРАНИЦА {i}: {page} ---\n")
                
                broken_on_page = []
                for link, status, ltype in self.broken_links:
                    if page in self.link_to_pages.get(link, set()):
                        broken_on_page.append((link, status, ltype))
                
                if broken_on_page:
                    f.write(f"\n  БИТЫЕ ССЫЛКИ ({len(broken_on_page)}):\n")
                    for link, status, _ in broken_on_page:
                        f.write(f"    {link} [код: {status if status else 'нет ответа'}]\n")
                else:
                    f.write(f"\n  Битых ссылок не найдено\n")
                
                f.write("\n" + "-" * 40)
            
            if self.broken_links:
                f.write("\n\n" + "=" * 80 + "\n")
                f.write("ПОЛНЫЙ СПИСОК БИТЫХ ССЫЛОК\n")
                f.write("=" * 80 + "\n")
                for link, status, _ in sorted(self.broken_links):
                    pages = ", ".join(list(self.link_to_pages.get(link, set()))[:3])
                    if len(self.link_to_pages.get(link, set())) > 3:
                        pages += f" и еще {len(self.link_to_pages.get(link, set())) - 3}"
                    f.write(f"  • {link} [код: {status if status else 'нет ответа'}] (на страницах: {pages})\n")
        
        print(f"\nДетальный отчет сохранен: {filename}")
        self.cleanup_temp_files()
    
    def cleanup_temp_files(self):
        """Удаляет временные HTML-файлы."""
        try:
            if os.path.exists(self.temp_html_dir):
                shutil.rmtree(self.temp_html_dir)
                print("Временные HTML-файлы удалены")
        except Exception as e:
            print(f"Ошибка при удалении временных файлов: {e}")


def main():
    """Запрашивает URL и запускает проверку."""
    print("=" * 60)
    print("ПРОВЕРКА ССЫЛОК НА САЙТЕ")
    print("=" * 60)
    
    url = input("\nВведите URL сайта для проверки (например, https://example.com): ").strip()
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        print(f"Добавлен протокол: {url}")
    
    print("\nСколько страниц обойти?")
    print("  • Введите число (например, 20)")
    print("  • Нажмите Enter для значения по умолчанию (20)")
    print("  • Введите 0 или 'all' для проверки всего сайта")
    
    max_pages_input = input("Ваш выбор: ").strip().lower()
    
    if max_pages_input in ('0', 'all', 'все'):
        max_pages = None
        print("Будет проверен весь сайт")
    elif max_pages_input == '':
        max_pages = 20
        print("Используется значение по умолчанию: 20 страниц")
    else:
        try:
            max_pages = int(max_pages_input)
            print(f"Будет проверено максимум {max_pages} страниц")
        except ValueError:
            max_pages = 20
            print("Некорректный ввод, используется значение по умолчанию: 20")
    
    checker = LinkChecker(url, delay=1.0)
    checker.crawl_and_check(max_pages=max_pages)


if __name__ == "__main__":
    main()