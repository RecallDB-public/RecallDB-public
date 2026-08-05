import csv
from collections import Counter

with open("samples/recalls.csv", encoding="utf-8", newline="") as handle:
    recalls = list(csv.DictReader(handle))

print(f"{len(recalls)} sample recalls")
print(Counter(row["source_agency"] for row in recalls))
print(recalls[0]["title"])
