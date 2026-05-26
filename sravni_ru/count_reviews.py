import json
from datetime import datetime

with open("reviews.json", "r", encoding="utf-8") as f:
    reviews = json.load(f)

start_date = datetime.fromisoformat("2024-01-01")
end_date = datetime.fromisoformat("2025-05-31")

count = 0
total_reviews = len(reviews)

for review in reviews:
    try:
        review_date = datetime.fromisoformat(review.get("date"))
    except Exception:
        continue

    if start_date <= review_date <= end_date:
        count += 1

print(f"Всего отзывов в файле: {total_reviews}")
print(f"Отзывов в промежутке 01.01.2024 - 31.05.2025: {count}")

percent = (count / total_reviews * 100) if total_reviews else 0
print(f"Процент от общего количества: {percent:.2f}%")