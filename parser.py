from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time
import json
import re
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class YandexMapsParser:
    def __init__(self, headless: bool = True):
        self.setup_driver(headless)
        
    def setup_driver(self, headless: bool = True):
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
    def search_organizations(self, query: str, city: str = "", limit: int = 50) -> List[Dict]:
        """Поиск организаций по запросу"""
        try:
            url = f"https://yandex.ru/maps/"
            self.driver.get(url)
            time.sleep(2)
            
            # Ввод поискового запроса
            search_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='поиск']"))
            )
            search_query = f"{query} {city}".strip()
            search_box.clear()
            search_box.send_keys(search_query)
            
            # Нажатие кнопки поиска
            search_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            search_button.click()
            time.sleep(3)
            
            # Ожидание загрузки результатов
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='search-list-view']"))
            )
            
            organizations = []
            processed_ids = set()
            
            # Парсинг результатов
            for i in range(min(limit, 100)):
                try:
                    # Прокрутка для загрузки новых элементов
                    if i % 10 == 0:
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(1)
                    
                    # Поиск элементов организаций
                    org_elements = self.driver.find_elements(By.CSS_SELECTOR, "[class*='search-snippet-view']")
                    
                    if i >= len(org_elements):
                        break
                    
                    org_element = org_elements[i]
                    org_data = self.parse_organization_element(org_element)
                    
                    if org_data and org_data['id'] not in processed_ids:
                        organizations.append(org_data)
                        processed_ids.add(org_data['id'])
                        
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.warning(f"Ошибка при парсинге элемента {i}: {e}")
                    continue
                    
            return organizations
            
        except Exception as e:
            logger.error(f"Ошибка при поиске организаций: {e}")
            return []
    
    def parse_organization_element(self, element) -> Dict:
        """Парсинг данных организации из элемента"""
        try:
            org_data = {}
            
            # ID организации
            try:
                link_element = element.find_element(By.CSS_SELECTOR, "a")
                href = link_element.get_attribute('href')
                org_id = re.search(r'org/(\d+)', href)
                org_data['id'] = org_id.group(1) if org_id else None
            except:
                org_data['id'] = None
            
            # Название
            try:
                name_element = element.find_element(By.CSS_SELECTOR, "[class*='orgpage-header-title']")
                org_data['name'] = name_element.text
            except:
                try:
                    name_element = element.find_element(By.CSS_SELECTOR, "h1, h2, h3")
                    org_data['name'] = name_element.text
                except:
                    org_data['name'] = ""
            
            # Категории
            try:
                category_element = element.find_element(By.CSS_SELECTOR, "[class*='business-categories']")
                org_data['categories'] = category_element.text
            except:
                org_data['categories'] = ""
            
            # Рейтинг
            try:
                rating_element = element.find_element(By.CSS_SELECTOR, "[class*='business-rating-badge']")
                org_data['rating'] = rating_element.text
            except:
                org_data['rating'] = ""
            
            # Количество отзывов
            try:
                reviews_element = element.find_element(By.CSS_SELECTOR, "[class*='business-review-count']")
                org_data['reviews_count'] = reviews_element.text
            except:
                org_data['reviews_count'] = "0"
            
            # Адрес
            try:
                address_element = element.find_element(By.CSS_SELECTOR, "[class*='business-address']")
                org_data['address'] = address_element.text
            except:
                org_data['address'] = ""
            
            # Телефоны
            try:
                phone_element = element.find_element(By.CSS_SELECTOR, "[class*='business-phone']")
                org_data['phones'] = phone_element.text
            except:
                org_data['phones'] = ""
            
            return org_data
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге элемента организации: {e}")
            return None
    
    def get_organization_details(self, org_id: str) -> Dict:
        """Получение детальной информации об организации"""
        try:
            url = f"https://yandex.ru/maps/org/{org_id}/"
            self.driver.get(url)
            time.sleep(3)
            
            details = {'id': org_id}
            
            # Название
            try:
                name_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
                )
                details['name'] = name_element.text
            except:
                details['name'] = ""
            
            # Рейтинг и отзывы
            try:
                rating_element = self.driver.find_element(By.CSS_SELECTOR, "[class*='business-rating-badge-view__rating']")
                details['rating'] = rating_element.text
            except:
                details['rating'] = ""
            
            try:
                reviews_element = self.driver.find_element(By.CSS_SELECTOR, "[class*='business-rating-amount']")
                details['reviews_count'] = reviews_element.text
            except:
                details['reviews_count'] = "0"
            
            # Адрес
            try:
                address_element = self.driver.find_element(By.CSS_SELECTOR, "[class*='card-address']")
                details['address'] = address_element.text
            except:
                details['address'] = ""
            
            # Телефоны
            try:
                phone_elements = self.driver.find_elements(By.CSS_SELECTOR, "[class*='business-phones-view__phone-number']")
                details['phones'] = ";".join([phone.text for phone in phone_elements])
            except:
                details['phones'] = ""
            
            # Сайт
            try:
                website_element = self.driver.find_element(By.CSS_SELECTOR, "[class*='business-urls-view__link']")
                details['website'] = website_element.get_attribute('href')
            except:
                details['website'] = ""
            
            # График работы
            try:
                schedule_element = self.driver.find_element(By.CSS_SELECTOR, "[class*='business-schedule-view']")
                details['schedule'] = schedule_element.text
            except:
                details['schedule'] = ""
            
            return details
            
        except Exception as e:
            logger.error(f"Ошибка при получении деталей организации {org_id}: {e}")
            return None
    
    def close(self):
        """Закрытие драйвера"""
        if self.driver:
            self.driver.quit()
