import os
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def filter_data():
    input_file = "test_data/ragbench/hotpotqa_raw.jsonl"
    output_file = "test_data/ragbench/hotpotqa_top500.jsonl"

    if not os.path.exists(input_file):
        logger.error(f"Không tìm thấy {input_file}. Vui lòng chạy step1 trước.")
        return

    logger.info(f"Đang đọc dữ liệu từ {input_file}...")
    valid_samples = []
    
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            
            # Loại bỏ nếu rỗng documents hoặc question
            if not row.get("documents") or not row.get("question") or not str(row.get("question")).strip():
                continue
                
            # Tính tổng điểm TRACE (chuyển đổi an toàn các giá trị None thành 0)
            adherence = 1.0 if row.get("adherence_score") is True else (row.get("adherence_score") or 0.0)
            relevance = row.get("relevance_score") or 0.0
            utilization = row.get("utilization_score") or 0.0
            completeness = row.get("completeness_score") or 0.0
            
            total_score = adherence + relevance + utilization + completeness
            row["_total_score"] = total_score
            
            valid_samples.append(row)

    logger.info(f"Tổng số mẫu hợp lệ ban đầu: {len(valid_samples)}")
    
    # Sắp xếp giảm dần theo tổng điểm
    valid_samples.sort(key=lambda x: x["_total_score"], reverse=True)
    
    # Lấy Top 500
    top_500 = valid_samples[:500]
    
    logger.info(f"Đang lưu {len(top_500)} mẫu tốt nhất ra {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        for row in top_500:
            final_row = {
                "id": row["id"],
                "question": row["question"],
                "documents": row["documents"],
                "ground_truth": row["response"]
            }
            f.write(json.dumps(final_row, ensure_ascii=False) + "\n")
            
    logger.info("Hoàn tất lọc dữ liệu (Step 2)!")

if __name__ == "__main__":
    filter_data()
