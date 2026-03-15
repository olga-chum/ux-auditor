"""
Модуль для статического парсинга веб-сайтов.
Выполняет обход страниц, извлечение HTML/CSS и проверку ссылок.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
from typing import Set, Dict, List, Tuple
import os
import json
from datetime import datetime


class StaticParser:
    """
    Класс для статического парсинга сайта.
    """
    
    def __init__(self, base_url: str, delay: float = 1.0):
        """
        Инициализация парсера.
        
        Args:
            base_url: Начальный URL сайта (например, https://example.com)
            delay: Задержка между запросами (чтобы не нагружать сервер)
        """
        self.base_url = base_url.rstrip('/')
        self.delay = delay
        self.visited_urls: Set[str] = set()  # Множество посещенных URL
        self.all_urls: Set[str] = set()       # Все найденные URL
        self.broken_links: List[Tuple[str, int]] = []  # Битые ссылки (url, status_code)
        self.page_data: Dict[str, dict] = {}  # Данные по каждой странице
        
        # Создаем папку для сохранения результатов
        os.makedirs('data/raw', exist_ok=True)
        os.makedirs('data/reports', exist_ok=True)
        
        print(f"🕷️  Парсер инициализирован для сайта: {self.base_url}")
    
    def is_same_domain(self, url: str) -> bool:
        """
        Проверяет, принадлежит ли URL тому же домену.
        """
        base_domain = urlparse(self.base_url).netloc
        url_domain = urlparse(url).netloc
        return base_domain == url_domain
    
    def normalize_url(self, url: str) -> str:
        """
        Приводит URL к нормальному виду (убирает якоря, лишние слеши).
        """
        parsed = urlparse(url)
        # Убираем якоря (#...)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized.rstrip('/')
    
    def extract_links(self, soup: BeautifulSoup, current_url: str) -> Set[str]:
        """
        Извлекает все ссылки со страницы.
        """
        links = set()
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            # Преобразуем относительную ссылку в абсолютную
            full_url = urljoin(current_url, href)
            normalized = self.normalize_url(full_url)
            
            # Добавляем только если это тот же домен
            if self.is_same_domain(normalized):
                links.add(normalized)
        
        return links
    
    def check_link(self, url: str) -> Tuple[bool, int]:
        """
        Проверяет, работает ли ссылка (HEAD-запрос).
        Возвращает (работает, статус_код)
        """
        try:
            # Используем HEAD для экономии трафика (не скачиваем содержимое)
            response = requests.head(url, timeout=5, allow_redirects=True)
            return response.status_code < 400, response.status_code
        except requests.RequestException:
            return False, 0
    
    def download_page(self, url: str) -> Tuple[bool, str, Dict]:
        """
        Скачивает страницу и возвращает HTML и заголовки.
        """
        try:
            response = requests.get(url, timeout=10)
            response.encoding = 'utf-8'
            
            headers = {
                'content-type': response.headers.get('content-type', ''),
                'content-length': len(response.text)
            }
            
            return True, response.text, headers
        except requests.RequestException as e:
            print(f"❌ Ошибка при скачивании {url}: {e}")
            return False, "", {}
    
    def extract_css(self, soup: BeautifulSoup) -> Dict:
        """
        Извлекает CSS-стили со страницы.
        """
        css_data = {
            'inline_styles': [],      # Стили в атрибутах style
            'style_tags': [],         # Содержимое тегов <style>
            'external_css': []        # Ссылки на внешние CSS
        }
        
        # Ищем атрибуты style
        for tag in soup.find_all(style=True):
            css_data['inline_styles'].append({
                'tag': tag.name,
                'style': tag['style']
            })
        
        # Ищем теги <style>
        for style in soup.find_all('style'):
            css_data['style_tags'].append(style.string)
        
        # Ищем ссылки на внешние CSS
        for link in soup.find_all('link', rel='stylesheet', href=True):
            css_data['external_css'].append(urljoin(self.base_url, link['href']))
        
        return css_data
    
    def crawl(self, max_pages: int = 100):
        """
        Основной метод обхода сайта (BFS - поиск в ширину).
        
        Args:
            max_pages: Максимальное количество страниц для обхода
        """
        print(f"\n🔍 Начинаем обход сайта {self.base_url}")
        print(f"Максимум страниц: {max_pages}")
        
        # Очередь URL для обхода (начинаем с базового URL)
        queue = [self.base_url]
        
        while queue and len(self.visited_urls) < max_pages:
            # Берем следующий URL из очереди
            current_url = queue.pop(0)
            
            # Пропускаем, если уже посещали
            if current_url in self.visited_urls:
                continue
            
            print(f"\n📄 Обрабатываем: {current_url}")
            
            # Скачиваем страницу
            success, html, headers = self.download_page(current_url)
            
            if not success:
                print(f"  ⚠️  Не удалось скачать, пропускаем")
                continue
            
            # Парсим HTML
            soup = BeautifulSoup(html, 'html.parser')
            
            # Извлекаем ссылки
            new_links = self.extract_links(soup, current_url)
            print(f"  🔗 Найдено ссылок: {len(new_links)}")
            
            # Добавляем новые ссылки в очередь (если не посещали)
            for link in new_links:
                if link not in self.visited_urls and link not in queue:
                    queue.append(link)
            
            # Извлекаем CSS
            css_data = self.extract_css(soup)
            
            # Сохраняем данные страницы
            self.page_data[current_url] = {
                'url': current_url,
                'title': soup.title.string if soup.title else 'Без заголовка',
                'headers': headers,
                'links': list(new_links),
                'css': css_data,
                'html_length': len(html),
                'timestamp': datetime.now().isoformat()
            }
            
            # Отмечаем как посещенную
            self.visited_urls.add(current_url)
            
            # Сохраняем HTML в файл
            filename = f"data/raw/{len(self.visited_urls)}_{urlparse(current_url).path.replace('/', '_')}.html"
            if len(filename) > 100:  # Слишком длинные имена обрезаем
                filename = filename[:50] + '.html'
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html)
            
            print(f"  💾 HTML сохранен: {filename}")
            
            # Задержка между запросами
            time.sleep(self.delay)
        
        print(f"\n✅ Обход завершен! Обработано страниц: {len(self.visited_urls)}")
    
    def check_all_links(self):
        """
        Проверяет все найденные ссылки на работоспособность.
        """
        print(f"\n🔍 Проверяем ссылки на работоспособность...")
        
        # Собираем все уникальные ссылки со всех страниц
        all_links = set()
        for page_data in self.page_data.values():
            all_links.update(page_data['links'])
        
        print(f"Всего уникальных ссылок для проверки: {len(all_links)}")
        
        broken = []
        working = []
        
        for i, link in enumerate(all_links, 1):
            print(f"  [{i}/{len(all_links)}] Проверяем: {link}")
            is_working, status = self.check_link(link)
            
            if is_working:
                working.append(link)
                print(f"    ✅ {status}")
            else:
                broken.append((link, status))
                print(f"    ❌ {status}")
            
            # Небольшая задержка
            time.sleep(0.5)
        
        self.broken_links = broken
        
        print(f"\n📊 Результаты проверки ссылок:")
        print(f"  ✅ Рабочих: {len(working)}")
        print(f"  ❌ Битых: {len(broken)}")
        
        return working, broken
    
    def save_report(self):
        """
        Сохраняет отчет о парсинге в JSON.
        """
        report = {
            'base_url': self.base_url,
            'crawl_date': datetime.now().isoformat(),
            'pages_crawled': len(self.visited_urls),
            'total_links_found': len(self.all_urls),
            'broken_links_count': len(self.broken_links),
            'broken_links': [
                {'url': url, 'status': status} for url, status in self.broken_links
            ],
            'pages': self.page_data
        }
        
        # Сохраняем в JSON
        filename = f"data/reports/parser_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 Отчет сохранен: {filename}")
        
        # Краткая статистика в консоль
        print("\n📈 КРАТКАЯ СТАТИСТИКА:")
        print(f"  Страниц обработано: {len(self.visited_urls)}")
        print(f"  Битых ссылок: {len(self.broken_links)}")
        
        if self.broken_links:
            print("\n  Примеры битых ссылок:")
            for url, status in self.broken_links[:5]:
                print(f"    • {url} (код: {status})")
        
        return filename


# Тестирование модуля (если запустить файл напрямую)
if __name__ == "__main__":
    # Тестовый запуск на небольшом сайте
    parser = StaticParser("https://example.com", delay=0.5)
    parser.crawl(max_pages=5)
    parser.check_all_links()
    parser.save_report()