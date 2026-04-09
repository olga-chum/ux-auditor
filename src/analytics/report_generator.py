"""
Генератор человекочитаемого отчета по результатам UX-аудита и проверки ссылок.
Объединяет все аспекты технического и UX-аудита с группировкой по страницам.
"""

import json
import glob
import os
import re
from datetime import datetime
from collections import defaultdict


class ReportGenerator:
    """
    Преобразует JSON-отчеты UX-аудита и битые ссылки в читаемый текстовый формат.
    """
    
    SEVERITY_NAMES = {
        'critical': 'КРИТИЧНО',
        'warning': 'ВАЖНО',
        'info': 'РЕКОМЕНДАЦИЯ'
    }
    
    def __init__(self):
        self.ux_results = []          # результаты ux_audit
        self.broken_links = []        # список битых ссылок
        self.base_url = ""
    
    def load_ux_results(self, styles_dir: str = 'data/style_analysis'):
        """Загружает все JSON-файлы ux_audit_*.json."""
        json_files = glob.glob(f"{styles_dir}/ux_audit_*.json")
        for file in json_files:
            with open(file, 'r', encoding='utf-8') as f:
                self.ux_results.append(json.load(f))
        return self.ux_results
    
    def load_broken_links(self, reports_dir: str = 'data/reports'):
        """Загружает последний отчет link_checker и извлекает битые ссылки."""
        report_files = glob.glob(f"{reports_dir}/link_check_report_*.txt")
        if not report_files:
            return
        latest = max(report_files, key=os.path.getctime)
        
        with open(latest, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Извлекаем базовый URL
        base_match = re.search(r'Сайт:\s*(https?://[^\s]+)', content)
        if base_match:
            self.base_url = base_match.group(1)
        
        # Извлекаем блок с битыми ссылками
        pattern = r"ПОЛНЫЙ СПИСОК БИТЫХ ССЫЛОК\n=+\n(.*?)(?=\n\n|\Z)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            block = match.group(1)
            for line in block.split('\n'):
                if '•' in line and 'http' in line:
                    parts = line.split('•')
                    if len(parts) < 2:
                        continue
                    rest = parts[1].strip()
                    url_match = re.search(r'(https?://[^\s\]]+)', rest)
                    code_match = re.search(r'код:\s*(\d+|нет ответа)', rest)
                    pages_match = re.search(r'на страницах:\s*(.+?)(?:\s*\)|$)', rest)
                    
                    url = url_match.group(1) if url_match else ''
                    status = code_match.group(1) if code_match else 'нет ответа'
                    pages = pages_match.group(1) if pages_match else ''
                    
                    if url:
                        self.broken_links.append({
                            'url': url,
                            'status': status,
                            'pages': pages
                        })
    
    def _get_element_key(self, element: dict) -> str:
        """Создает уникальный ключ для элемента (тег + класс + текст)."""
        tag = element.get('tag', '')
        class_name = element.get('class', '')
        text = element.get('text', '')[:50]
        return f"{tag}|{class_name}|{text}"
    
    def _deduplicate_issues(self, issues: list) -> list:
        """Удаляет дубликаты проблем на одной странице."""
        seen = set()
        unique = []
        for issue in issues:
            key = f"{issue.get('type')}|{issue.get('message')[:80]}|{issue.get('element', {}).get('text', '')[:50]}"
            if key not in seen:
                seen.add(key)
                unique.append(issue)
        return unique
    
    def generate_text_report(self, output_file: str = None) -> str:
        """Генерирует итоговый текстовый отчет с группировкой по страницам."""
        if not self.ux_results:
            self.load_ux_results()
        if not self.broken_links:
            self.load_broken_links()
        
        lines = []
        lines.append("=" * 80)
        lines.append("ИТОГОВЫЙ ОТЧЕТ ТЕХНИЧЕСКОГО И UX-АУДИТА")
        lines.append("=" * 80)
        lines.append(f"Сайт: {self.base_url or (self.ux_results[0].get('url', 'Неизвестно') if self.ux_results else 'Неизвестно')}")
        lines.append(f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        lines.append("")
        
        # ====================================================================
        # 1. БИТЫЕ ССЫЛКИ
        # ====================================================================
        lines.append("=" * 80)
        lines.append("1. БИТЫЕ ССЫЛКИ")
        lines.append("=" * 80)
        
        if self.broken_links:
            lines.append(f"Всего битых ссылок: {len(self.broken_links)}")
            lines.append("")
            for i, link in enumerate(self.broken_links, 1):
                lines.append(f"[{i}] {link['url']}")
                lines.append(f"    Код: {link['status']}")
                if link['pages']:
                    # Показываем только первые 3 страницы
                    pages_list = link['pages'].split(', ')
                    if len(pages_list) > 3:
                        pages_short = ', '.join(pages_list[:3]) + f" и еще {len(pages_list) - 3}"
                    else:
                        pages_short = link['pages']
                    lines.append(f"    Страницы: {pages_short}")
                lines.append("")
            lines.append("")
        else:
            lines.append("Битых ссылок не найдено.\n")
        
        # ====================================================================
        # 2. UX-АУДИТ (по страницам)
        # ====================================================================
        lines.append("=" * 80)
        lines.append("2. UX-АУДИТ")
        lines.append("=" * 80)
        
        # Общая статистика
        total_critical = sum(r.get('critical_count', 0) for r in self.ux_results)
        total_warning = sum(r.get('warning_count', 0) for r in self.ux_results)
        total_info = sum(r.get('info_count', 0) for r in self.ux_results)
        
        lines.append(f"Всего страниц проанализировано: {len(self.ux_results)}")
        lines.append(f"Всего проблем UX: {total_critical + total_warning + total_info}")
        lines.append(f"  КРИТИЧНО: {total_critical}")
        lines.append(f"  ВАЖНО: {total_warning}")
        lines.append(f"  РЕКОМЕНДАЦИИ: {total_info}")
        lines.append("")
        
        # Проходим по каждой странице отдельно
        for page_idx, page_result in enumerate(self.ux_results, 1):
            page_url = page_result.get('url', 'Неизвестно')
            page_issues = page_result.get('issues', [])
            
            # Пропускаем страницы без проблем
            if not page_issues:
                continue
            
            # Удаляем дубликаты на странице
            unique_issues = self._deduplicate_issues(page_issues)
            
            lines.append("-" * 80)
            lines.append(f"Страница {page_idx}: {page_url}")
            lines.append("-" * 80)
            
            # Группируем проблемы по типу на этой странице
            issues_by_type = defaultdict(list)
            for issue in unique_issues:
                issue_type = issue.get('type', 'other')
                issues_by_type[issue_type].append(issue)
            
            type_names = {
                'contrast': 'Контраст цветов',
                'clickable_size': 'Размер кликабельных элементов',
                'typography_diversity': 'Типографика',
                'layout_spacing': 'Структура страницы (отступы)',
                'headings': 'Заголовки',
                'font_legibility': 'Читаемость шрифтов',
                'text_density': 'Плотность текста'
            }
            
            for issue_type, type_issues in issues_by_type.items():
                lines.append(f"\n  --- {type_names.get(issue_type, issue_type)} ---")
                
                for issue in type_issues:
                    severity = self.SEVERITY_NAMES.get(issue.get('severity', 'warning'), '')
                    message = issue.get('message', '')
                    details = issue.get('details', {})
                    element = issue.get('element', {})
                    
                    lines.append(f"\n    [{severity}] {message}")
                    
                    # Детали
                    if 'contrast_ratio' in details:
                        lines.append(f"        Контраст: {details['contrast_ratio']}:1 (норма {details.get('required_ratio', 4.5)}:1)")
                    
                    if 'font_families' in details:
                        families = ', '.join(details['font_families'][:3])
                        if len(details['font_families']) > 3:
                            families += f" и еще {len(details['font_families']) - 3}"
                        lines.append(f"        Шрифты: {families}")
                    
                    if 'recommendation' in details:
                        lines.append(f"        Рекомендация: {details['recommendation']}")
                    
                    # Информация об элементе
                    if element:
                        elem_text = element.get('text', '')[:60]
                        elem_class = element.get('class', '')
                        elem_tag = element.get('tag', '')
                        
                        if elem_text:
                            lines.append(f"        Элемент: {elem_tag} -> \"{elem_text}\"")
                        elif elem_class:
                            lines.append(f"        Элемент: {elem_tag}.{elem_class}")
                        else:
                            lines.append(f"        Элемент: {elem_tag}")
            
            lines.append("")
        
        # ====================================================================
        # 3. СВОДНЫЕ РЕКОМЕНДАЦИИ (без привязки к страницам)
        # ====================================================================
        lines.append("=" * 80)
        lines.append("3. СВОДНЫЕ РЕКОМЕНДАЦИИ")
        lines.append("=" * 80)
        lines.append("")
        
        if total_critical > 0:
            lines.append("КРИТИЧНЫЕ проблемы (исправить в первую очередь):")
            lines.append("  1. Увеличьте контраст текста в футере (светло-серый #999999 на белом)")
            lines.append("  2. Измените цвет почти белого текста (#dadbdd) на темный")
            lines.append("  3. Увеличьте размер кликабельных элементов до 44x44px")
            lines.append("  4. Добавьте заголовок H1 на каждой странице")
            lines.append("")
        
        if total_warning > 0:
            lines.append("ВАЖНЫЕ проблемы (рекомендуется исправить):")
            lines.append("  1. Стандартизируйте размеры шрифтов (сейчас используется 8-11 разных размеров)")
            lines.append("  2. Увеличьте отступы между блоками до 16-48px")
            lines.append("  3. Увеличьте высоту строки (line-height) до 1.4-1.6")
            lines.append("  4. Исправьте иерархию заголовков (не пропускайте уровни)")
            lines.append("")
        
        lines.append("=" * 80)
        lines.append("КОНЕЦ ОТЧЕТА")
        
        report_text = "\n".join(lines)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_text)
            print(f"Отчет сохранен: {output_file}")
        
        return report_text


def main():
    print("Генерация итогового отчета...")
    gen = ReportGenerator()
    gen.load_ux_results()
    gen.load_broken_links()
    
    if not gen.ux_results and not gen.broken_links:
        print("Нет данных. Сначала запусти style_analyzer.py, ux_audit.py и link_checker.py")
        return
    
    out_file = f"data/style_analysis/full_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    gen.generate_text_report(out_file)
    print("\n" + gen.generate_text_report()[:2000] + "...\n(отчет сохранен полностью)")


if __name__ == "__main__":
    main()