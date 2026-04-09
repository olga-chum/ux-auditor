"""
Полный модуль UX-аудита веб-страницы.
Объединяет проверки контраста, размеров, шрифтов, заголовков, отступов,
разнообразия шрифтов, плотности текста.
Нормы по стандартам WCAG 2.2, Material Design, Apple HIG.
"""

import json
import glob
import re
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime


class UXAudit:
    """
    Класс для комплексной оценки пользовательского опыта.
    """
    
    # ========================================================================
    # КОНСТАНТЫ (нормы и правила)
    # ========================================================================
    
    # Контраст (WCAG 2.2)
    CONTRAST_AA_NORMAL = 4.5
    CONTRAST_AA_LARGE = 3.0
    CONTRAST_AAA_NORMAL = 7.0
    CONTRAST_AAA_LARGE = 4.5
    
    # Размер кликабельных элементов (Apple HIG, Material Design)
    MIN_CLICKABLE_WIDTH = 44
    MIN_CLICKABLE_HEIGHT = 44
    
    # Шрифты
    MIN_FONT_SIZE = 12          # минимальный размер шрифта в px
    MIN_LINE_HEIGHT = 1.4       # минимальная высота строки (множитель)
    MAX_LINE_HEIGHT = 1.6       # максимальная высота строки
    
    # Типографика
    MAX_FONT_FAMILIES = 4       # максимум разных семейств шрифтов
    MAX_FONT_SIZES = 6          # максимум разных размеров шрифта
    
    # Структура страницы
    MIN_SPACING = 16            # минимальный отступ между блоками (px)
    MAX_SPACING = 48            # максимальный отступ между блоками (px)
    MAX_TEXT_DENSITY = 80       # максимальная ширина текста в % от экрана
    
    # Список тегов для проверки размеров
    CLICKABLE_TAGS = ['button', 'a', 'input', 'select', 'textarea']
    
    # Список тегов заголовков
    HEADING_TAGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
    
    # ========================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ (цвета, яркость)
    # ========================================================================
    
    def rgba_to_rgb(self, rgba: str, default_rgb: Tuple[int, int, int] = (255, 255, 255)) -> Tuple[int, int, int]:
        """
        Преобразует RGBA в RGB с учетом альфа-канала.
        """
        if not rgba or rgba == 'rgba(0, 0, 0, 0)':
            return default_rgb
        
        match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)', rgba)
        if not match:
            return default_rgb
        
        r, g, b = int(match[1]), int(match[2]), int(match[3])
        alpha = float(match[4]) if match[4] else 1.0
        
        # Смешиваем с фоном
        r = int(r * alpha + default_rgb[0] * (1 - alpha))
        g = int(g * alpha + default_rgb[1] * (1 - alpha))
        b = int(b * alpha + default_rgb[2] * (1 - alpha))
        
        return (r, g, b)
    
    def get_relative_luminance(self, rgb: Tuple[int, int, int]) -> float:
        """
        Вычисляет относительную яркость цвета (формула WCAG).
        """
        def linearize(c):
            c = c / 255.0
            if c <= 0.03928:
                return c / 12.92
            return ((c + 0.055) / 1.055) ** 2.4
        
        r_lin = linearize(rgb[0])
        g_lin = linearize(rgb[1])
        b_lin = linearize(rgb[2])
        
        return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin
    
    def calculate_contrast(self, text_rgb: Tuple[int, int, int], bg_rgb: Tuple[int, int, int]) -> float:
        """Вычисляет коэффициент контраста."""
        L1 = self.get_relative_luminance(text_rgb)
        L2 = self.get_relative_luminance(bg_rgb)
        
        lighter = max(L1, L2)
        darker = min(L1, L2)
        
        return (lighter + 0.05) / (darker + 0.05)
    
    def get_real_background_color(self, element: Dict) -> Tuple[int, int, int]:
        """
        Возвращает реальный цвет фона элемента.
        Если цвет прозрачный, рекурсивно поднимается к родительскому блоку.
        (Упрощенная версия: пока возвращаем белый, т.к. нет parent в JSON)
        """
        bg_color = element.get('styles', {}).get('background-color', '')
        if bg_color and bg_color != 'rgba(0, 0, 0, 0)':
            return self.rgba_to_rgb(bg_color)
        return (255, 255, 255)
    
    # ========================================================================
    # МЕТОДЫ ПРОВЕРОК
    # ========================================================================
    
    def check_contrast(self, element: Dict, viewport: str) -> Optional[Dict]:
        """
        Проверка контраста текста и фона.
        """
        styles = element.get('styles', {})
        text_color = styles.get('color', '')
        font_size = styles.get('font-size', '14px')
        font_weight = styles.get('font-weight', '400')
        text = element.get('text', '')[:80]
        
        if not text:
            return None
        if not text_color or text_color == 'rgba(0, 0, 0, 0)':
            return None
        
        bg_rgb = self.get_real_background_color(element)
        text_rgb = self.rgba_to_rgb(text_color)
        
        if text_rgb == bg_rgb:
            return {
                'type': 'contrast',
                'severity': 'critical',
                'viewport': viewport,
                'element': {
                    'tag': element.get('tag'),
                    'id': element.get('id'),
                    'class': element.get('class'),
                    'text': text
                },
                'message': f"Текст '{text}' сливается с фоном (цвета совпадают)",
                'details': {
                    'text_color': text_color,
                    'background_color': f"rgb({bg_rgb[0]}, {bg_rgb[1]}, {bg_rgb[2]})"
                }
            }
        
        contrast = self.calculate_contrast(text_rgb, bg_rgb)
        
        try:
            size = float(font_size.replace('px', ''))
            weight = int(font_weight) if font_weight.isdigit() else 400
            is_large = (size >= 18) or (size >= 14 and weight >= 700)
        except:
            is_large = False
        
        required = self.CONTRAST_AA_LARGE if is_large else self.CONTRAST_AA_NORMAL
        
        if contrast < required:
            severity = 'critical' if contrast < 3 else 'warning'
            return {
                'type': 'contrast',
                'severity': severity,
                'viewport': viewport,
                'element': {
                    'tag': element.get('tag'),
                    'id': element.get('id'),
                    'class': element.get('class'),
                    'text': text
                },
                'message': f"Контраст {contrast:.2f}:1 ниже нормы {required}:1",
                'details': {
                    'text_color': text_color,
                    'background_color': f"rgb({bg_rgb[0]}, {bg_rgb[1]}, {bg_rgb[2]})",
                    'contrast_ratio': round(contrast, 2),
                    'required_ratio': required,
                    'font_size': font_size,
                    'is_large_text': is_large
                }
            }
        return None
    
    def check_clickable_size(self, element: Dict, viewport: str) -> Optional[Dict]:
        """Проверка размера кликабельных элементов."""
        tag = element.get('tag')
        if tag not in self.CLICKABLE_TAGS:
            return None
        
        styles = element.get('styles', {})
        width_str = styles.get('width', '0px')
        height_str = styles.get('height', '0px')
        
        try:
            width = float(width_str.replace('px', ''))
            height = float(height_str.replace('px', ''))
        except:
            return None
        
        if width < self.MIN_CLICKABLE_WIDTH or height < self.MIN_CLICKABLE_HEIGHT:
            text = element.get('text', '')[:50]
            severity = 'critical' if (width < 30 or height < 30) else 'warning'
            return {
                'type': 'clickable_size',
                'severity': severity,
                'viewport': viewport,
                'element': {
                    'tag': tag,
                    'id': element.get('id'),
                    'class': element.get('class'),
                    'text': text
                },
                'message': f"Элемент '{text or tag}' имеет размер {width:.0f}x{height:.0f}px (мин. {self.MIN_CLICKABLE_WIDTH}x{self.MIN_CLICKABLE_HEIGHT}px)",
                'details': {
                    'width': width,
                    'height': height,
                    'min_required': f"{self.MIN_CLICKABLE_WIDTH}x{self.MIN_CLICKABLE_HEIGHT}"
                }
            }
        return None
    
    def check_font_legibility(self, element: Dict, viewport: str) -> Optional[Dict]:
        """Проверка читаемости шрифта (размер, line-height)."""
        styles = element.get('styles', {})
        font_size_str = styles.get('font-size', '14px')
        line_height_str = styles.get('line-height', 'normal')
        text = element.get('text', '')[:80]
        
        if not text:
            return None
        
        try:
            font_size = float(font_size_str.replace('px', ''))
        except:
            font_size = 14
        
        issues = []
        if font_size < self.MIN_FONT_SIZE:
            issues.append(f"размер шрифта {font_size}px (мин. {self.MIN_FONT_SIZE}px)")
        
        if line_height_str != 'normal':
            try:
                if 'px' in line_height_str:
                    line_height = float(line_height_str.replace('px', ''))
                    line_height_ratio = line_height / font_size if font_size else 1.4
                else:
                    line_height_ratio = float(line_height_str)
                
                if line_height_ratio < self.MIN_LINE_HEIGHT or line_height_ratio > self.MAX_LINE_HEIGHT:
                    issues.append(f"высота строки {line_height_ratio:.1f} (рекомендуется {self.MIN_LINE_HEIGHT}-{self.MAX_LINE_HEIGHT})")
            except:
                pass
        
        if issues:
            return {
                'type': 'font_legibility',
                'severity': 'warning',
                'viewport': viewport,
                'element': {
                    'tag': element.get('tag'),
                    'id': element.get('id'),
                    'class': element.get('class'),
                    'text': text
                },
                'message': f"Проблемы с читаемостью: {', '.join(issues)}",
                'details': {
                    'font_size': font_size_str,
                    'line_height': line_height_str,
                    'recommendation': f"Увеличьте шрифт до {self.MIN_FONT_SIZE}px, line-height {self.MIN_LINE_HEIGHT}-{self.MAX_LINE_HEIGHT}"
                }
            }
        return None
    
    def check_headings(self, elements: List[Dict], viewport: str) -> List[Dict]:
        """Проверка иерархии заголовков."""
        issues = []
        headings = []
        for element in elements:
            tag = element.get('tag')
            if tag in self.HEADING_TAGS:
                level = int(tag[1])
                text = element.get('text', '')[:80]
                headings.append({'level': level, 'text': text, 'element': element})
        
        if not headings:
            return []
        
        h1_count = sum(1 for h in headings if h['level'] == 1)
        if h1_count == 0:
            issues.append({
                'type': 'headings',
                'severity': 'critical',
                'viewport': viewport,
                'message': "На странице отсутствует заголовок H1 (важно для SEO и доступности)"
            })
        elif h1_count > 1:
            issues.append({
                'type': 'headings',
                'severity': 'warning',
                'viewport': viewport,
                'message': f"Найдено {h1_count} заголовков H1 (рекомендуется один)"
            })
        
        prev_level = 1
        for h in headings:
            if h['level'] > prev_level + 1:
                issues.append({
                    'type': 'headings',
                    'severity': 'warning',
                    'viewport': viewport,
                    'message': f"Пропущен уровень заголовка: H{prev_level+1} перед '{h['text']}' (H{h['level']})"
                })
            prev_level = h['level']
        return issues
    
    def check_typography_diversity(self, elements: List[Dict], viewport: str) -> List[Dict]:
        """Проверка разнообразия шрифтов и размеров."""
        issues = []
        font_families = set()
        font_sizes = set()
        
        for element in elements:
            styles = element.get('styles', {})
            font_family = styles.get('font-family', '')
            font_size = styles.get('font-size', '')
            
            if font_family and font_family != 'inherit':
                clean = font_family.split(',')[0].strip().strip("'\"")
                font_families.add(clean)
            
            if font_size and 'px' in font_size:
                try:
                    size = float(font_size.replace('px', ''))
                    font_sizes.add(round(size))
                except:
                    pass
        
        if len(font_families) > self.MAX_FONT_FAMILIES:
            issues.append({
                'type': 'typography_diversity',
                'severity': 'warning',
                'viewport': viewport,
                'message': f"Найдено {len(font_families)} разных семейств шрифтов (рекомендуется ≤{self.MAX_FONT_FAMILIES})",
                'details': {
                    'font_families': list(font_families),
                    'count': len(font_families),
                    'recommendation': 'Используйте не более 2-3 шрифтов на сайте'
                }
            })
        
        if len(font_sizes) > self.MAX_FONT_SIZES:
            issues.append({
                'type': 'typography_diversity',
                'severity': 'info',
                'viewport': viewport,
                'message': f"Найдено {len(font_sizes)} разных размеров шрифта (рекомендуется ≤{self.MAX_FONT_SIZES})",
                'details': {
                    'font_sizes': sorted(list(font_sizes)),
                    'count': len(font_sizes),
                    'recommendation': 'Стандартизируйте размеры: 14px, 16px, 18px, 24px, 32px'
                }
            })
        return issues
    
    def check_layout_spacing(self, elements: List[Dict], viewport: str) -> List[Dict]:
        """Проверка отступов между блоками."""
        issues = []
        margins = []
        
        for element in elements:
            styles = element.get('styles', {})
            margin = styles.get('margin', '')
            if margin and 'px' in margin:
                try:
                    parts = margin.split()
                    val = float(parts[0].replace('px', '')) if parts else float(margin.replace('px', ''))
                    if 0 < val < 200:
                        margins.append(val)
                except:
                    pass
        
        if margins:
            avg_margin = sum(margins) / len(margins)
            if avg_margin < self.MIN_SPACING:
                issues.append({
                    'type': 'layout_spacing',
                    'severity': 'warning',
                    'viewport': viewport,
                    'message': f"Средний отступ между блоками {avg_margin:.0f}px (рекомендуется {self.MIN_SPACING}-{self.MAX_SPACING}px)",
                    'details': {
                        'avg_margin': round(avg_margin),
                        'min_margin': min(margins),
                        'max_margin': max(margins),
                        'recommendation': f'Увеличьте отступы между блоками до {self.MIN_SPACING}px'
                    }
                })
            elif avg_margin > self.MAX_SPACING:
                issues.append({
                    'type': 'layout_spacing',
                    'severity': 'info',
                    'viewport': viewport,
                    'message': f"Средний отступ {avg_margin:.0f}px (возможно, слишком много пустого пространства)",
                    'details': {
                        'avg_margin': round(avg_margin),
                        'recommendation': f'Уменьшите отступы до {self.MAX_SPACING}px'
                    }
                })
        return issues
    
    def check_text_density(self, elements: List[Dict], viewport: str) -> List[Dict]:
        """Проверка плотности текста (слишком широкие строки)."""
        issues = []
        screen_width = 1920  # предположение, можно брать из viewport
        
        for element in elements:
            tag = element.get('tag')
            if tag in ['p', 'div', 'span', 'li']:
                text = element.get('text', '')
                if len(text) > 100:
                    styles = element.get('styles', {})
                    width_str = styles.get('width', '')
                    if width_str and 'px' in width_str:
                        try:
                            width = float(width_str.replace('px', ''))
                            density = (width / screen_width) * 100
                            if density > self.MAX_TEXT_DENSITY:
                                issues.append({
                                    'type': 'text_density',
                                    'severity': 'info',
                                    'viewport': viewport,
                                    'element': {
                                        'tag': tag,
                                        'class': element.get('class'),
                                        'text': text[:50]
                                    },
                                    'message': f"Текст занимает {density:.0f}% ширины экрана (рекомендуется ≤{self.MAX_TEXT_DENSITY}%)",
                                    'details': {
                                        'width': width,
                                        'screen_width': screen_width,
                                        'density_percent': round(density),
                                        'recommendation': 'Ограничьте ширину текста 60-80% для лучшей читаемости'
                                    }
                                })
                                break  # одно предупреждение на страницу
                        except:
                            pass
        return issues
    
    def analyze_page(self, page_data: Dict) -> Dict:
        """
        Полный анализ страницы.
        """
        url = page_data.get('url')
        all_issues = []
        
        for viewport_data in page_data.get('viewports', []):
            viewport = viewport_data.get('viewport_name')
            elements = viewport_data.get('elements', [])
            
            # Поелементные проверки
            for element in elements:
                issue = self.check_contrast(element, viewport)
                if issue:
                    all_issues.append(issue)
                issue = self.check_clickable_size(element, viewport)
                if issue:
                    all_issues.append(issue)
                issue = self.check_font_legibility(element, viewport)
                if issue:
                    all_issues.append(issue)
            
            # Проверки уровня страницы
            all_issues.extend(self.check_headings(elements, viewport))
            all_issues.extend(self.check_typography_diversity(elements, viewport))
            all_issues.extend(self.check_layout_spacing(elements, viewport))
            all_issues.extend(self.check_text_density(elements, viewport))
        
        severity_order = {'critical': 0, 'warning': 1, 'info': 2}
        all_issues.sort(key=lambda x: severity_order.get(x.get('severity', 'warning'), 2))
        
        return {
            'url': url,
            'timestamp': datetime.now().isoformat(),
            'total_issues': len(all_issues),
            'critical_count': sum(1 for i in all_issues if i.get('severity') == 'critical'),
            'warning_count': sum(1 for i in all_issues if i.get('severity') == 'warning'),
            'info_count': sum(1 for i in all_issues if i.get('severity') == 'info'),
            'issues': all_issues
        }


def analyze_all_pages(styles_dir: str = 'data/style_analysis'):
    """Анализирует все страницы и сохраняет результаты."""
    json_files = glob.glob(f"{styles_dir}/page_*.json")
    if not json_files:
        print("Файлы не найдены. Сначала запусти style_analyzer.py")
        return
    
    print(f"Найдено файлов: {len(json_files)}")
    auditor = UXAudit()
    
    for file in json_files:
        print(f"\nАнализируем: {file}")
        with open(file, 'r', encoding='utf-8') as f:
            page_data = json.load(f)
        result = auditor.analyze_page(page_data)
        output_file = file.replace('page_', 'ux_audit_')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  Проблем: {result['total_issues']} (critical: {result['critical_count']}, warning: {result['warning_count']}, info: {result['info_count']})")


if __name__ == "__main__":
    analyze_all_pages()