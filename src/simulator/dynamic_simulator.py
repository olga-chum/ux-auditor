from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

def init_driver():
    """
    Создает и возвращает настроенный экземпляр веб-драйвера
    """
    try:
        # Вариант 1: с webdriver-manager (сам качает драйвер)
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service)
        
        # Вариант 2: если драйвер уже скачан и лежит в папке проекта
        # driver = webdriver.Chrome(executable_path='./chromedriver.exe')
        
        driver.maximize_window()  # открыть на весь экран
        return driver
    except Exception as e:
        print(f"Ошибка при запуске драйвера: {e}")
        return None

# Проверка (можно запустить этот файл для теста)
if __name__ == "__main__":
    driver = init_driver()
    if driver:
        driver.get("https://example.com")
        print("Заголовок страницы:", driver.title)
        driver.quit()