import os
import json
import sys

# Fix Windows console Unicode
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from datasets import load_dataset

SUBSETS = ["hotpotqa", "msmarco", "pubmedqa"]
OUTPUT_DIR = "test_data/ragbench"
SPLIT = "test"
COLUMNS_TO_KEEP = ["id", "question", "documents", "response", "adherence_score"]


def download():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for subset in SUBSETS:
        out_path = os.path.join(OUTPUT_DIR, f"{subset}.json")
        if os.path.exists(out_path):
            print(f"[Skip] {subset}.json already exists.")
            continue

        print(f"[Download] Loading subset '{subset}' (split='{SPLIT}')...")
        try:
            ds = load_dataset("galileo-ai/ragbench", subset, split=SPLIT)
        except Exception as e:
            print(f"[Error] Cannot load '{subset}': {e}")
            continue

        data_list = []
        for item in ds:
            row = {col: item.get(col) for col in COLUMNS_TO_KEEP if col in item}
            data_list.append(row)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data_list, f, ensure_ascii=False, indent=2)

        print(f"[Done] Saved {len(data_list)} samples to {out_path}")


if __name__ == "__main__":
    download()

