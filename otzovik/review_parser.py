# -*- coding: utf-8 -*-

import json
import os
import re
import signal
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


driver: Optional[webdriver.Chrome] = None
all_reviews: List[Dict[str, Any]] = []
is_shutting_down: bool = False
processed_count: int = 0


def build_chrome_options() -> webdriver.ChromeOptions:
    options = webdriver.ChromeOptions()

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-client-side-phishing-detection")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-translate")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-save-password-bubble")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors")
    options.add_argument("--allow-running-insecure-content")

    return options


def save_reviews_to_file(reviews: List[Dict[str, Any]], filename: str = "otzovik_detailed_reviews.json") -> None:
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(reviews, f, ensure_ascii=False, indent=2)
        print(f"Отзывы сохранены в файл: {filename}")
        print(f"Сохранено отзывов: {len(reviews)}")
    except Exception as e:
        print(f"Ошибка при сохранении файла: {e}")


def load_json_file(filename: str) -> Optional[List[Dict[str, Any]]]:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return None
    except Exception:
        return None


def find_last_processed_id() -> Tuple[Optional[str], List[Dict[str, Any]], Optional[str]]:
    emergency_file = "otzovik_detailed_reviews_emergency.json"

    reviews = load_json_file(emergency_file)
    if reviews and len(reviews) > 0 and "id" in reviews[-1]:
        last_id = reviews[-1]["id"]
        print(f"Найден emergency файл {emergency_file} с {len(reviews)} отзывами. Последний ID: {last_id}")
        return last_id, reviews, emergency_file
    else:
        print("Emergency файл не найден, ищем промежуточные файлы...")

    try:
        files = [p.name for p in Path(".").iterdir() if p.is_file()]
        inter = [fn for fn in files if re.match(r"^otzovik_detailed_reviews_\d+\.json$", fn)]
        inter.sort(key=lambda x: int(re.search(r"\d+", x).group(0)), reverse=True)

        print(f"Найдено промежуточных файлов: {len(inter)}")
        if inter:
            preview = ", ".join(inter[:3]) + ("..." if len(inter) > 3 else "")
            print(f"Проверяем файлы: {preview}")

        for fn in inter:
            r = load_json_file(fn)
            if r and len(r) > 0 and "id" in r[-1]:
                last_id = r[-1]["id"]
                print(f"Найден файл {fn} с {len(r)} отзывами. Последний ID: {last_id}")
                return last_id, r, fn
            elif fn in inter:
                if r is None:
                    print(f"Файл {fn} поврежден или недоступен, пропускаем")
    except Exception as e:
        print(f"Ошибка при чтении директории: {e}")

    main_file = "otzovik_detailed_reviews.json"
    reviews = load_json_file(main_file)
    if reviews and len(reviews) > 0 and "id" in reviews[-1]:
        last_id = reviews[-1]["id"]
        print(f"Найден основной файл {main_file} с {len(reviews)} отзывами. Последний ID: {last_id}")
        return last_id, reviews, main_file

    print("Предыдущих результатов не найдено, начинаем с начала")
    return None, [], None


def load_source_reviews(filename: str = "otzovik_reviews_filtered_2024-2025.json") -> List[Dict[str, Any]]:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            reviews = json.load(f)
        if not isinstance(reviews, list):
            raise ValueError("Source file must contain a JSON array")
        print(f"Загружено {len(reviews)} отзывов для обработки")
        return reviews
    except Exception as e:
        print(f"Ошибка при загрузке исходного файла: {e}")
        raise


def filter_source_reviews_from_id(source_reviews: List[Dict[str, Any]], last_processed_id: Optional[str]) -> List[Dict[str, Any]]:
    if not last_processed_id:
        return source_reviews

    last_index = next((i for i, r in enumerate(source_reviews) if r.get("id") == last_processed_id), -1)
    if last_index == -1:
        print(f"Последний обработанный ID {last_processed_id} не найден в исходных данных")
        return source_reviews

    remaining = source_reviews[last_index + 1 :]
    print(f"Продолжаем с позиции {last_index + 1}, осталось обработать: {len(remaining)} отзывов")
    return remaining


def clean_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = re.sub(r"\s+", " ", text).strip()
    return t or None


def extract_city(location_text: Optional[str]) -> Optional[str]:
    if not location_text:
        return None
    m = re.search(r"(?:Россия,\s*)?(.+?)$", location_text)
    if m and m.group(1):
        return clean_text(m.group(1).upper())
    return None


def parse_detailed_review(driver_instance: webdriver.Chrome, review_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        rid = review_data.get("id")
        link = review_data.get("link")
        print(f"Парсим отзыв {rid}...")

        driver_instance.get(link)

        try:
            review_container = WebDriverWait(driver_instance, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.review-contents[itemprop="review"]'))
            )
        except Exception:
            print(f"Контейнер отзыва не найден для ID {rid}")
            return None

        review: Dict[str, Any] = {
            "id": rid,
            "link": link,
            "date": None,
            "title": None,
            "text": None,
            "rating": None,
            "status": None,
            "product": None,
            "city": None,
        }

        try:
            date_el = review_container.find_element(By.CSS_SELECTOR, 'meta[itemprop="datePublished"]')
            review["date"] = date_el.get_attribute("content")
        except Exception:
            print(f"Дата не найдена для отзыва {rid}")

        try:
            title_el = review_container.find_element(By.CSS_SELECTOR, "h1")
            title_text = title_el.text
            review["title"] = clean_text(re.sub(r"^Отзыв:\s*", "", title_text))
        except Exception:
            print(f"Заголовок не найден для отзыва {rid}")

        try:
            text_parts: List[str] = []

            try:
                plus_el = review_container.find_element(By.CSS_SELECTOR, ".review-plus")
                plus_text = plus_el.text
                if plus_text:
                    ct = clean_text(plus_text)
                    if ct:
                        text_parts.append(ct)
            except Exception:
                pass

            try:
                minus_el = review_container.find_element(By.CSS_SELECTOR, ".review-minus")
                minus_text = minus_el.text
                if minus_text:
                    ct = clean_text(minus_text)
                    if ct:
                        text_parts.append(ct)
            except Exception:
                pass

            try:
                body_el = review_container.find_element(
                    By.CSS_SELECTOR, '.review-body.description[itemprop="description"]'
                )
                body_text = body_el.text
                if body_text:
                    ct = clean_text(body_text)
                    if ct:
                        text_parts.append(ct)
            except Exception:
                pass

            review["text"] = "\n\n".join(text_parts) if text_parts else None
        except Exception:
            print(f"Текст отзыва не найден для ID {rid}")

        try:
            rating_el = review_container.find_element(By.CSS_SELECTOR, 'meta[itemprop="ratingValue"]')
            review["rating"] = rating_el.get_attribute("content")
        except Exception:
            try:
                rating_span = review_container.find_element(By.CSS_SELECTOR, ".rating-score span")
                review["rating"] = rating_span.text
            except Exception:
                print(f"Рейтинг не найден для отзыва {rid}")

        try:
            loc_el = review_container.find_element(By.CSS_SELECTOR, ".user-location")
            review["city"] = extract_city(loc_el.text)
        except Exception:
            print(f"Город не найден для отзыва {rid}")

        review["status"] = None
        review["product"] = None

        print(f"Отзыв {rid} успешно обработан")
        return review

    except Exception as e:
        rid = review_data.get("id")
        print(f"Ошибка при парсинге отзыва {rid}: {e}")
        return None


def graceful_shutdown(sig_name: str) -> None:
    global is_shutting_down, driver, all_reviews

    if is_shutting_down:
        print("\nУже в процессе завершения работы...")
        return

    is_shutting_down = True
    print(f"\nПолучен сигнал {sig_name}. Начинаем graceful shutdown...")

    try:
        if len(all_reviews) > 0:
            print("Сохраняем собранные данные...")
            save_reviews_to_file(all_reviews, "otzovik_detailed_reviews_emergency.json")
            print(f"Данные сохранены! Всего отзывов: {len(all_reviews)}")

        if driver is not None:
            print("Закрываем браузер...")
            try:
                driver.quit()
            except Exception:
                pass
            driver = None
            print("Браузер закрыт")

        print("Graceful shutdown завершен")
        sys.exit(0)

    except Exception as e:
        print(f"Ошибка при graceful shutdown: {e}")
        sys.exit(1)


def _signal_handler(signum, frame) -> None:
    name = {
        getattr(signal, "SIGINT", None): "SIGINT",
        getattr(signal, "SIGTERM", None): "SIGTERM",
        getattr(signal, "SIGHUP", None): "SIGHUP",
    }.get(signum, str(signum))
    graceful_shutdown(name)


def install_signal_handlers() -> None:
    signal.signal(signal.SIGINT, _signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _signal_handler)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, _signal_handler)


def parse_detailed_reviews(source_filename: str = "otzovik_reviews_filtered_2024-2025.json") -> List[Dict[str, Any]]:
    global driver, all_reviews, processed_count, is_shutting_down

    try:
        print("Запуск парсера детальной информации отзывов Otzovik...")
        print("Для остановки используйте Ctrl+C (данные будут сохранены)")

        last_id, existing_reviews, existing_file = find_last_processed_id()
        all_reviews.extend(existing_reviews)

        all_source_reviews = load_source_reviews(source_filename)
        source_reviews = filter_source_reviews_from_id(all_source_reviews, last_id)

        if len(source_reviews) == 0:
            print("Все отзывы уже обработаны!")
            return all_reviews

        options = build_chrome_options()
        driver = webdriver.Chrome(options=options)
        print("Chrome драйвер запущен")

        total_reviews = len(source_reviews)
        already_processed = len(all_reviews)

        print(f"Уже обработано: {already_processed} отзывов")
        print(f"Осталось обработать: {total_reviews} отзывов")
        pct = (already_processed / len(all_source_reviews) * 100) if all_source_reviews else 0
        print(f"Общий прогресс: {already_processed}/{len(all_source_reviews)} ({pct:.1f}%)")

        for i, review_data in enumerate(source_reviews):
            if is_shutting_down:
                print("Прерывание парсинга из-за shutdown")
                break

            processed_count = already_processed + i + 1
            current_in_batch = i + 1

            rid = review_data.get("id")
            print(
                f"\nОбрабатываем отзыв {current_in_batch}/{total_reviews} | "
                f"Общий: {processed_count}/{len(all_source_reviews)} (ID: {rid})"
            )

            try:
                detailed = parse_detailed_review(driver, review_data)

                if detailed:
                    all_reviews.append(detailed)
                    print(f"Успешно: {len(all_reviews)} | В батче: {current_in_batch}/{total_reviews}")
                else:
                    print(f"Отзыв {rid} пропущен из-за ошибок")

                if processed_count % 50 == 0:
                    print(f"\nПромежуточное сохранение после {processed_count} отзывов...")
                    save_reviews_to_file(all_reviews, f"otzovik_detailed_reviews_{processed_count}.json")

                driver.implicitly_wait(0)
                driver.sleep(0.5)

            except Exception as e:
                print(f"Критическая ошибка при обработке отзыва {rid}: {e}")
                continue

        if not is_shutting_down:
            print("\nПарсинг детальной информации завершен!")
            print(f"Общее количество успешно обработанных отзывов: {len(all_reviews)}")
            print(f"Общее количество просмотренных отзывов: {processed_count}")

            save_reviews_to_file(all_reviews)

        return all_reviews

    except Exception as e:
        print(f"Критическая ошибка парсера: {e}")
        raise
    finally:
        if driver is not None and not is_shutting_down:
            print("Закрытие браузера...")
            try:
                driver.quit()
            except Exception:
                pass
            driver = None


if __name__ == "__main__":
    install_signal_handlers()
    try:
        reviews = parse_detailed_reviews()
        if not is_shutting_down:
            print("Парсер детальной информации успешно завершен")
            print(f"Итоговый результат: {len(reviews)} детальных отзывов")
    except Exception as e:
        if not is_shutting_down:
            print(f"Парсер завершен с ошибкой: {e}")
            sys.exit(1)