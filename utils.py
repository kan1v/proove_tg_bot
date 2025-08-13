import csv

def update_status_in_csv(chat_id: int, status: str, csv_file: str = "data.csv"):
    rows = []
    updated = False
    with open(csv_file, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if str(row["chat_id"]) == str(chat_id):
                row["Статус"] = status
                updated = True
            rows.append(row)
    if updated:
        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "ПІБ",
                "Телефон",
                "Instagram",
                "TikTok",
                "YouTube Shorts",
                "Підписники / Перегляди",
                "Ідея",
                "Telegram username",
                "Дата",
                "Статус",
                "chat_id",
            ])
            writer.writeheader()
            writer.writerows(rows)