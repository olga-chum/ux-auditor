"""
Модуль для извлечения признаков интерфейсных блоков из HTML.
"""

import os
from bs4 import BeautifulSoup
from typing import Dict, List, Any
import json
from datetime import datetime


class FeatureExtractor:
    """
    Класс для извлечения характеристик интерфейсных блоков.
    """
    
    def __init__(self, html_content: str, url: str):
        """
        Инициализация.
        
        Args:
            html_content: HTML-код страницы
            url: URL страницы
        """
        self.html = html_content
        self.url = url
        self.soup = BeautifulSoup(html_content, 'html.parser')
        self.features = []
        
    def extract_blocks(self) -> List[Dict[str, Any]]:
        """
        Находит все значимые блоки на странице.
        
        Returns:
            Список словарей с характеристиками блоков
        """
        blocks = []
        
        # Ищем все значимые теги
        tags_to_extract = [
            'div', 'section', 'header', 'footer', 'main', 'article',
            'button', 'a', 'input', 'form', 'nav', 'aside'
        ]
        
        for tag_name in tags_to_extract:
            for element in self.soup.find_all(tag_name):
                block = self._extract_block_features(element, tag_name)
                if block:
                    blocks.append(block)
        
        return blocks
    
    def _extract_block_features(self, element, tag_name: str) -> Dict[str, Any]:
        """
        Извлекает характеристики одного блока.
        """
        features = {
            'url': self.url,
            'tag': tag_name,
            'class': element.get('class', []),
            'id': element.get('id', ''),
            'text': element.get_text(strip=True)[:100],  # первые 100 символов
        }
        
        # Извлекаем inline-стили
        style = element.get('style', '')
        if style:
            features['inline_styles'] = self._parse_inline_style(style)
        
        # Извлекаем цвет текста (если есть)
        if element.get('style') and 'color' in element['style']:
            features['color'] = self._extract_color(element['style'])
        
        return features
    
    def _parse_inline_style(self, style: str) -> Dict[str, str]:
        """Парсит inline-стили в словарь."""
        styles = {}
        for part in style.split(';'):
            if ':' in part:
                key, value = part.split(':', 1)
                styles[key.strip()] = value.strip()
        return styles
    
    def _extract_color(self, style: str) -> str:
        """Извлекает значение цвета из стиля."""
        for part in style.split(';'):
            if 'color' in part and ':' in part:
                return part.split(':', 1)[1].strip()
        return ''
    
    def save_features(self, output_dir: str = 'data/features'):
        """Сохраняет признаки в JSON файл."""
        os.makedirs(output_dir, exist_ok=True)
        
        blocks = self.extract_blocks()
        
        filename = f"{output_dir}/features_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(blocks, f, ensure_ascii=False, indent=2)
        
        print(f"Сохранено признаков: {len(blocks)} в {filename}")
        return filename


# Тестовый запуск
if __name__ == "__main__":
    # Загружаем сохраненную HTML-страницу
    html_file = "data/temp_html/page_1.html"  # временный файл
    if os.path.exists(html_file):
        with open(html_file, 'r', encoding='utf-8') as f:
            html = f.read()
        
        extractor = FeatureExtractor(html, "https://example.com")
        extractor.save_features()
    else:
        print("Нет сохраненных HTML-файлов. Сначала запусти link_checker.py")