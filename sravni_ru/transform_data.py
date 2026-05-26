import json


def transform_data() -> None:
    print("Начинаем преобразование dataset.json...")

    with open("dataset.json", "r", encoding="utf-8") as f:
        dataset = json.load(f)

    print(f"Найдено {len(dataset)} записей для обработки")

    transformed_data = []

    for index, item in enumerate(dataset):
        title = ""
        text = ""

        content = item.get("content")
        if content:
            double_newline_index = content.find("\n\n")

            if double_newline_index != -1:
                title = content[:double_newline_index].strip()
                text = content[double_newline_index + 2 :].strip()
            else:
                single_newline_index = content.find("\n")
                if single_newline_index != -1:
                    title = content[:single_newline_index].strip()
                    text = content[single_newline_index + 1 :].strip()
                else:
                    title = content.strip()
                    text = ""

        status = ""
        if item.get("status") == "ПРОВЕРЕН":
            status = "verified"
        elif item.get("status") == "ПРОБЛЕМА РЕШЕНА":
            status = "decided"
        else:
            status = item.get("status").lower() if item.get("status") else ""

        transformed_item = {
            "id": int(item.get("id")) if item.get("id") is not None else 0,
            "link": item.get("link") or "",
            "date": item.get("date") or "",
            "title": title,
            "text": text,
            "rating": str(item.get("rating")) if item.get("rating") is not None else "",
            "status": status,
        }

        if item.get("product"):
            transformed_item["product"] = item.get("product")

        transformed_item["city"] = item.get("city") or ""

        if (index + 1) % 1000 == 0:
            print(f"Обработано {index + 1} записей...")

        transformed_data.append(transformed_item)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(transformed_data, f, ensure_ascii=False, indent=2)

    print(f"Преобразование завершено! Создан файл data.json с {len(transformed_data)} записями")
    print("Примеры преобразованных записей:")

    for i in range(min(3, len(transformed_data))):
        ex = transformed_data[i]
        print(f"\nПример {i + 1}:")
        print("Title:", ex.get("title", ""))
        preview = (ex.get("text") or "")
        print("Text preview:", preview[:100] + ("..." if len(preview) > 100 else ""))
        print("Status:", ex.get("status", ""))
        print("Rating type:", type(ex.get("rating")).__name__)
        print("ID type:", type(ex.get("id")).__name__)


try:
    transform_data()
except Exception as error:
    print("Ошибка при преобразовании данных:", str(error))
    raise SystemExit(1)