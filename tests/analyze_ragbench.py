"""
Script phân tích và hiển thị kết quả benchmark Ragbench.

Cách dùng:
  python tests/analyze_ragbench.py                         # Phân tích file CSV mới nhất
  python tests/analyze_ragbench.py tests/ragbench_xxx.csv  # Phân tích file cụ thể
"""

import os
import sys
import glob
import pandas as pd


def find_latest_result(results_dir: str = "tests") -> str:
    """Tìm file kết quả CSV mới nhất trong thư mục tests/."""
    pattern = os.path.join(results_dir, "ragbench_*.csv")
    files = sorted(glob.glob(pattern), reverse=True)
    if not files:
        print(f"[Error] Không tìm thấy file kết quả nào trong '{results_dir}/'")
        sys.exit(1)
    return files[0]


def analyze(csv_path: str):
    print(f"\n{'='*65}")
    print(f"  PHÂN TÍCH KẾT QUẢ RAGBENCH BENCHMARK")
    print(f"  File: {csv_path}")
    print(f"{'='*65}\n")

    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    total = len(df)
    print(f"  Tổng số mẫu          : {total}")

    # Lấy cột có dữ liệu similarity
    valid = df[df["similarity_score"].notna() & (df["similarity_score"] != "")].copy()
    valid["similarity_score"] = valid["similarity_score"].astype(float)
    valid["true_false"] = valid["true_false"].map(
        {True: True, False: False, "True": True, "False": False}
    )

    if valid.empty:
        print("  [Warning] Không có mẫu nào có điểm similarity hợp lệ.")
        return

    avg_sim   = valid["similarity_score"].mean()
    max_sim   = valid["similarity_score"].max()
    min_sim   = valid["similarity_score"].min()
    true_cnt  = valid["true_false"].sum()
    false_cnt = (~valid["true_false"]).sum()
    true_pct  = (true_cnt / len(valid)) * 100

    print(f"  Avg Similarity Score  : {avg_sim:.4f}")
    print(f"  Max Similarity Score  : {max_sim:.4f}")
    print(f"  Min Similarity Score  : {min_sim:.4f}")
    print(f"  True  (sim >= 0.75)   : {int(true_cnt)} mẫu  ({true_pct:.1f}%)")
    print(f"  False (sim <  0.75)   : {int(false_cnt)} mẫu  ({100 - true_pct:.1f}%)")

    # Phân phối điểm
    print(f"\n  PHÂN PHỐI ĐIỂM SIMILARITY:")
    bins = [0.0, 0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1.01]
    labels = ["<0.5", "0.5-0.6", "0.6-0.7", "0.7-0.75", "0.75-0.8", "0.8-0.9", ">=0.9"]
    valid["bucket"] = pd.cut(valid["similarity_score"], bins=bins, labels=labels, right=False)
    dist = valid["bucket"].value_counts().sort_index()
    for label, count in dist.items():
        bar = "█" * count
        print(f"    {str(label):>10}  {bar}  ({count})")

    # Top 3 câu trả lời tốt nhất
    print(f"\n  TOP 3 MẪU CÓ SIMILARITY CAO NHẤT:")
    top3 = valid.nlargest(3, "similarity_score")
    for _, row in top3.iterrows():
        print(f"\n  Q: {row['question'][:100]}...")
        print(f"  [Ref]  {row['response'][:120]}...")
        print(f"  [AI ]  {row['response_AI'][:120]}...")
        print(f"  Score: {row['similarity_score']:.4f}  |  Match: {row['true_false']}")

    # Bottom 3 câu trả lời kém nhất
    print(f"\n  BOTTOM 3 MẪU CÓ SIMILARITY THẤP NHẤT:")
    bot3 = valid.nsmallest(3, "similarity_score")
    for _, row in bot3.iterrows():
        print(f"\n  Q: {row['question'][:100]}...")
        print(f"  [Ref]  {row['response'][:120]}...")
        print(f"  [AI ]  {row['response_AI'][:120]}...")
        print(f"  Score: {row['similarity_score']:.4f}  |  Match: {row['true_false']}")

    print(f"\n{'='*65}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = find_latest_result()

    analyze(csv_path)
