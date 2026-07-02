import os
import json
import logging
from datasets import load_dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def download_data():
    output_dir = "test_data/ragbench"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "hotpotqa_raw.jsonl")

    logger.info("Đang tải dataset galileo-ai/ragbench (subset: hotpotqa) từ Hugging Face...")
    try:
        # Load all splits merged to get the full ~2700 samples
        dataset = load_dataset("galileo-ai/ragbench", "hotpotqa", split="train+test+validation")
        logger.info(f"Đã tải thành công {len(dataset)} mẫu.")
    except Exception as e:
        logger.error(f"Lỗi khi tải dataset: {e}")
        return

    required_columns = [
        "id", "question", "documents", "response", 
        "adherence_score", "relevance_score", 
        "utilization_score", "completeness_score"
    ]

    logger.info(f"Đang lưu dữ liệu ra file: {output_file}")
    with open(output_file, "w", encoding="utf-8") as f:
        for row in dataset:
            extracted_row = {}
            for col in required_columns:
                extracted_row[col] = row.get(col)
            f.write(json.dumps(extracted_row, ensure_ascii=False) + "\n")
            
    logger.info("Hoàn tất tải và lưu raw data!")

if __name__ == "__main__":
    download_data()
