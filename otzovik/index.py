import json
import os
import re
import sys
import signal
from datetime import datetime
from typing import Any, Dict, List, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


driver = None
allReviews: List[Dict[str, Any]] = []
isShuttingDown = False


chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")

chrome_options.add_argument("--disable-web-security")
chrome_options.add_argument("--disable-features=VizDisplayCompositor")
chrome_options.add_argument("--disable-background-networking")
chrome_options.add_argument("--disable-background-timer-throttling")
chrome_options.add_argument("--disable-renderer-backgrounding")
chrome_options.add_argument("--disable-backgrounding-occluded-windows")
chrome_options.add_argument("--disable-client-side-phishing-detection")
chrome_options.add_argument("--disable-sync")
chrome_options.add_argument("--disable-default-apps")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-plugins")
chrome_options.add_argument("--disable-popup-blocking")
chrome_options.add_argument("--disable-translate")
chrome_options.add_argument("--no-first-run")
chrome_options.add_argument("--no-default-browser-check")
chrome_options.add_argument("--disable-infobars")
chrome_options.add_argument("--disable-notifications")
chrome_options.add_argument("--disable-save-password-bubble")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--ignore-certificate-errors")
chrome_options.add_argument("--ignore-ssl-errors")
chrome_options.add_argument("--allow-running-insecure-content")


def saveReviewsToFile(reviews: List[Dict[str, Any]], filename: str = "otzovik_reviews.json") -> None:
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(reviews, f, ensure_ascii=False, indent=2)
        print(f"Отзывы сохранены в файл: {filename}")
        print(f"Сохранено отзывов: {len(reviews)}")
    except Exception as error:
        print("Ошибка при сохранении файла:", str(error))


def gracefulShutdown(sig: str) -> None:
    global isShuttingDown, driver

    if isShuttingDown:
        print("\nУже в процессе завершения работы...")
        return

    isShuttingDown = True
    print(f"\nПолучен сигнал {sig}. Начинаем graceful shutdown...")

    try:
        if len(allReviews) > 0:
            print("Сохраняем собранные данные...")
            saveReviewsToFile(allReviews, "otzovik_reviews_filtered_emergency.json")
            print(f"Данные сохранены! Всего отзывов: {len(allReviews)}")

        if driver is not None:
            print("Закрываем браузер...")
            try:
                driver.quit()
            except Exception:
                pass
            print("Браузер закрыт")

        print("Graceful shutdown завершен")
        sys.exit(0)

    except Exception as error:
        print("Ошибка при graceful shutdown:", str(error))
        sys.exit(1)


def _signal_handler(signum, frame):
    name = {signal.SIGINT: "SIGINT", signal.SIGTERM: "SIGTERM"}.get(signum, str(signum))
    if hasattr(signal, "SIGHUP") and signum == getattr(signal, "SIGHUP"):
        name = "SIGHUP"
    gracefulShutdown(name)


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)
if hasattr(signal, "SIGHUP"):
    signal.signal(signal.SIGHUP, _signal_handler)


def isDateInRange(dateString: str) -> bool:
    try:
        review_date = datetime.fromisoformat(dateString.replace("Z", "+00:00")).date()
        start_date = datetime.fromisoformat("2025-01-01").date()
        end_date = datetime.fromisoformat("2026-02-08").date()
        return review_date >= start_date and review_date <= end_date
    except Exception:
        print("Ошибка при парсинге даты:", dateString)
        return False


def parseReview(reviewElement) -> Optional[Dict[str, Any]]:
    try:
        metaUrl = reviewElement.find_element(By.CSS_SELECTOR, 'meta[itemprop="url"]')
        reviewUrl = metaUrl.get_attribute("content")

        idMatch = re.search(r"review_(\d+)\.html", reviewUrl or "")
        if not idMatch:
            print("Не удалось извлечь ID из URL:", reviewUrl)
            return None

        reviewId = int(idMatch.group(1))
        reviewLink = reviewUrl

        reviewDate = None
        try:
            dateElement = reviewElement.find_element(By.CSS_SELECTOR, '.review-postdate[itemprop="datePublished"]')
            reviewDate = dateElement.get_attribute("content")
        except Exception:
            print(f"Не удалось извлечь дату для отзыва {reviewId}")
            return None

        if not isDateInRange(reviewDate):
            print(f"Отзыв {reviewId} ({reviewDate}) не в диапазоне дат - пропускаем")
            return None

        print(f"Отзыв {reviewId} ({reviewDate}) в диапазоне дат - добавляем")
        return {"id": reviewId, "link": reviewLink, "date": reviewDate}

    except Exception as error:
        print("Ошибка при парсинге отзыва:", str(error))
        return None


def parsePage(driverInstance, pageNum: int) -> List[Dict[str, Any]]:
    try:
        if isShuttingDown:
            print("Прерывание парсинга из-за shutdown")
            return []

        url = f"https://otzovik.com/reviews/bank_gazprombank_russia/{pageNum}"
        print(f"Обрабатываем страницу {pageNum}: {url}")

        driverInstance.get(url)

        print("Ожидаем загрузки контейнера с отзывами...")
        try:
            WebDriverWait(driverInstance, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".review-list-2.review-list-chunk"))
            )
            print("Контейнер найден")
        except Exception:
            print(f"Контейнер с отзывами не найден на странице {pageNum} (timeout)")
            return []

        print("Ожидаем загрузки отзывов...")
        try:
            WebDriverWait(driverInstance, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '.review-list-2.review-list-chunk .item[itemprop="review"]')
                )
            )

            previousCount = 0
            stableCount = 0
            maxStableChecks = 1

            while stableCount < maxStableChecks:
                currentElements = driverInstance.find_elements(
                    By.CSS_SELECTOR, '.review-list-2.review-list-chunk .item[itemprop="review"]'
                )
                currentCount = len(currentElements)

                if currentCount == previousCount and currentCount > 0:
                    stableCount += 1
                    print(f"DOM стабилен: {currentCount} отзывов (проверка {stableCount}/{maxStableChecks})")
                else:
                    stableCount = 0
                    print(f"Загружается: {currentCount} отзывов")

                previousCount = currentCount

                if isShuttingDown:
                    print("Прерывание ожидания из-за shutdown")
                    return []

        except Exception:
            print(f"Отзывы не загрузились на странице {pageNum}")
            return []

        reviewElements = driverInstance.find_elements(
            By.CSS_SELECTOR, '.review-list-2.review-list-chunk .item[itemprop="review"]'
        )
        print(f"Финальное количество отзывов: {len(reviewElements)}")

        pageReviews: List[Dict[str, Any]] = []

        for i in range(len(reviewElements)):
            if isShuttingDown:
                print("Прерывание парсинга отзывов из-за shutdown")
                break

            try:
                review = parseReview(reviewElements[i])
                if review:
                    pageReviews.append(review)
                    print(f"Отзыв {review['id']} успешно обработан")
            except Exception as error:
                print(f"Ошибка при обработке отзыва {i + 1}: {str(error)}")

        print(f"Страница {pageNum} завершена: собрано {len(pageReviews)} отзывов")
        return pageReviews

    except Exception as error:
        print(f"Ошибка при обработке страницы {pageNum}: {str(error)}")
        return []


def parseOtzovikGazprombank() -> List[Dict[str, Any]]:
    global driver

    try:
        print("Запуск парсера Otzovik.com для Газпромбанка (отзывы 01.01.2024 - 31.05.2025)...")
        print("Для остановки используйте Ctrl+C (данные будут сохранены)")

        driver = webdriver.Chrome(options=chrome_options)
        print("Chrome драйвер запущен")

        startPage = 1
        endPage = 48

        for pageNum in range(startPage, endPage + 1):
            if isShuttingDown:
                print("Прерывание парсинга из-за shutdown")
                break

            try:
                pageReviews = parsePage(driver, pageNum)
                allReviews.extend(pageReviews)

                print(f"Страница {pageNum}/{endPage} завершена. Всего отзывов: {len(allReviews)}")

                if pageNum % 10 == 0:
                    print(f"Промежуточное сохранение после {pageNum} страниц...")
                    saveReviewsToFile(allReviews, f"otzovik_reviews_filtered_page_{pageNum}.json")

            except Exception as error:
                print(f"Критическая ошибка на странице {pageNum}:", str(error))
                continue

        if not isShuttingDown:
            print("\nПарсинг завершен!")
            print(f"Общее количество найденных отзывов: {len(allReviews)}")
            saveReviewsToFile(allReviews, "otzovik_reviews_filtered_2024-2025.json")

        return allReviews

    except Exception as error:
        print("Критическая ошибка парсера:", str(error))
        raise
    finally:
        if driver is not None and not isShuttingDown:
            print("Закрытие браузера...")
            try:
                driver.quit()
            except Exception:
                pass
            driver = None


if __name__ == "__main__":
    try:
        reviews = parseOtzovikGazprombank()
        if not isShuttingDown:
            print("Парсер успешно завершен")
            print(f"Итоговый результат: {len(reviews)} отзывов")
    except Exception as error:
        if not isShuttingDown:
            print("Парсер завершен с ошибкой:", str(error))
            sys.exit(1)


__all__ = ["parseOtzovikGazprombank"]