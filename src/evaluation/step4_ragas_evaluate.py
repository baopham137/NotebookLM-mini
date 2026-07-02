#!/usr/bin/env python3
"""
══════════════════════════════════════════════════════════════
  Step 4: RAGAS Evaluation — FULL (Tất cả mẫu)
  Combo 1: Gemma 4 31B (LLM Judge) + Gemini Embedding 1
  Features: API Key Rotation · Resume · Adaptive Rate Limiting
══════════════════════════════════════════════════════════════

Cách chạy:
    python scripts/step4_ragas_evaluate.py

Cách resume (khi bị dừng giữa chừng):
    python scripts/step4_ragas_evaluate.py
    → Script tự detect file CSV cũ và tiếp tục từ mẫu chưa chấm.

Cài đặt trước khi chạy:
    pip install ragas==0.1.21 langchain-google-genai datasets nest_asyncio
"""

# Vá lỗi import của langchain trong Ragas v0.4+ trên Python 3.13
import sys
import io
import threading
import asyncio
import typing
import warnings
warnings.simplefilter("ignore", DeprecationWarning)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    import langchain_google_vertexai
    sys.modules['langchain_community.chat_models.vertexai'] = langchain_google_vertexai
except ImportError:
    pass

import json
import csv
import os
import sys
import time
import traceback
from pathlib import Path
from datetime import datetime, timedelta

# Fix asyncio cho Windows + Ragas
import nest_asyncio
nest_asyncio.apply()


from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from ragas.run_config import RunConfig
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.outputs import LLMResult
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

# ╔══════════════════════════════════════════════════════════╗
# ║                    GEMINI WRAPPER                        ║
# ╚══════════════════════════════════════════════════════════╝

class GeminiWrapper(ChatGoogleGenerativeAI):
    """
    Wrapper cho ChatGoogleGenerativeAI để sửa lỗi:
      1. Extra inputs are not permitted (pydantic validation error cho tham số n)
      2. Multiple candidates is not enabled for this model (API limit của Gemini 3.x+)
      3. Bị nghẽn API làm chậm (Giới hạn tối đa 1 request gửi lên Google cùng lúc)
    """
    _semaphore: typing.ClassVar = None
    _lock: typing.ClassVar = threading.Lock()

    @classmethod
    def get_semaphore(cls):
        if cls._semaphore is None:
            cls._semaphore = asyncio.Semaphore(1)
        return cls._semaphore

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        # Chặn các tham số lỗi
        kwargs.pop('n', None)
        kwargs.pop('candidateCount', None)
        kwargs.pop('candidate_count', None)

        with self._lock:
            time.sleep(0.5)  # Tránh gửi quá nhanh làm nghẽn API
            return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        # Chặn các tham số lỗi
        kwargs.pop('n', None)
        kwargs.pop('candidateCount', None)
        kwargs.pop('candidate_count', None)

        async with self.get_semaphore():
            await asyncio.sleep(0.5)  # Tránh gửi quá nhanh làm nghẽn API
            return await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)


# ╔══════════════════════════════════════════════════════════╗
# ║                    CONFIGURATION                         ║
# ╚══════════════════════════════════════════════════════════╝

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

INPUT_FILE = PROJECT_DIR / "rag_results_hotpotqa.jsonl"
OUTPUT_FILE = PROJECT_DIR / "tests" / "results" / "ragbench_evaluation_final.csv"
API_KEYS_FILE = PROJECT_DIR / "api_keys.txt"

# Model IDs
LLM_MODEL = "gemma-4-31b-it"        # 15 RPM, 500 RPD
EMBEDDING_MODEL = "models/gemini-embedding-001"  # 100 RPM, 1000 RPD

# Adaptive Rate Limiting
# Tổng cycle >= 26s để đảm bảo 6 LLM calls/sample < 15 RPM
MIN_CYCLE_TIME = 26  # giây

# Ragas metrics
METRICS = [faithfulness, answer_relevancy, context_precision, context_recall]
METRIC_NAMES = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]

# Ragas RunConfig — chạy tuần tự, retry khi gặp lỗi tạm
RUN_CONFIG = RunConfig(
    max_workers=1,     # Tuần tự, không song song
    max_wait=180,      # Đợi tối đa 3 phút khi bị rate limit
    max_retries=10,    # Retry 10 lần cho lỗi tạm (RPM limit)
)


# ╔══════════════════════════════════════════════════════════╗
# ║                  API KEY MANAGER                         ║
# ╚══════════════════════════════════════════════════════════╝

class APIKeyManager:
    """Quản lý danh sách API keys với khả năng tự động rotate."""

    def __init__(self, keys_file):
        self.keys = self._load_keys(keys_file)
        self.current_index = 0
        print(f"🔑 Đã tải {len(self.keys)} API key(s)")

    def _load_keys(self, filepath):
        if not os.path.exists(filepath):
            print(f"\n❌ Không tìm thấy file: {filepath}")
            print(f"   Tạo file api_keys.txt và thêm API key (mỗi dòng 1 key).")
            sys.exit(1)

        with open(filepath, "r", encoding="utf-8") as f:
            keys = [line.strip() for line in f
                    if line.strip() and not line.startswith("#")]

        if not keys:
            print(f"\n❌ File {filepath} không chứa API key nào!")
            print(f"   Thêm ít nhất 1 key (bỏ dấu # ở đầu dòng).")
            sys.exit(1)

        return keys

    @property
    def current_key(self):
        return self.keys[self.current_index]

    @property
    def key_label(self):
        k = self.current_key
        return f"Key #{self.current_index + 1}/{len(self.keys)} ({k[:8]}...)"

    def rotate(self):
        """Chuyển sang API key tiếp theo. Return False nếu hết key."""
        self.current_index += 1
        if self.current_index >= len(self.keys):
            return False
        print(f"\n🔄 Chuyển sang {self.key_label}")
        return True

    def has_more_keys(self):
        return self.current_index < len(self.keys) - 1


# ╔══════════════════════════════════════════════════════════╗
# ║                   HELPER FUNCTIONS                       ║
# ╚══════════════════════════════════════════════════════════╝

def create_models(api_key):
    """Tạo Ragas LLM wrapper + Embedding wrapper từ API key."""
    llm = GeminiWrapper(
        model=LLM_MODEL,
        google_api_key=api_key,
        temperature=0,
    )
    emb = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=api_key,
    )
    return LangchainLLMWrapper(llm, bypass_n=True), LangchainEmbeddingsWrapper(emb)


def load_input_data(filepath):
    """Đọc tất cả mẫu từ file JSONL."""
    data = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def get_completed_ids(filepath):
    """Lấy danh sách ID đã chấm xong từ file CSV."""
    completed = set()
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("id"):
                    completed.add(row["id"])
    return completed


def init_csv(filepath):
    """Tạo file CSV với header nếu chưa tồn tại."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if not os.path.exists(filepath):
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "question", "documents", "ground_truth", "response_AI", "top_chunks",
                "faithfulness", "answer_relevancy",
                "context_precision", "context_recall",
            ])


def append_result_to_csv(filepath, sample, scores):
    """Ghi 1 kết quả vào cuối file CSV ngay lập tức (crash-safe)."""
    row = [
        sample["id"],
        sample["question"],
        sample.get("documents", ""),
        sample["ground_truth"],
        sample.get("response_AI", ""),
        json.dumps(sample["top_chunks"], ensure_ascii=False),
        scores.get("faithfulness", ""),
        scores.get("answer_relevancy", ""),
        scores.get("context_precision", ""),
        scores.get("context_recall", ""),
    ]

    retries = 3
    for attempt in range(retries):
        try:
            with open(filepath, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(row)
            return filepath
        except PermissionError:
            if attempt < retries - 1:
                print(f"\n⚠️  Không thể ghi vào {os.path.basename(filepath)} (file đang mở trong Excel?).")
                print("   Vui lòng ĐÓNG file trong Excel. Thử lại sau 5 giây...")
                time.sleep(5)
            else:
                base, ext = os.path.splitext(filepath)
                fallback_path = f"{base}_temp_backup{ext}"
                print(f"\n⚠️  Ghi thất bại sau {retries} lần thử. Ghi tạm vào file dự phòng: {fallback_path}")
                if not os.path.exists(fallback_path):
                    with open(fallback_path, "w", encoding="utf-8", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            "id", "question", "documents", "ground_truth", "response_AI", "top_chunks",
                            "faithfulness", "answer_relevancy",
                            "context_precision", "context_recall",
                        ])
                with open(fallback_path, "a", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(row)
                return fallback_path


def is_quota_error(error):
    """Kiểm tra lỗi có phải do hết quota / rate limit không."""
    msg = str(error).lower()
    keywords = [
        "429", "quota", "resource_exhausted", "resourceexhausted",
        "rate_limit", "rate limit", "too many requests",
    ]
    return any(k in msg for k in keywords)


def is_timeout_error(error):
    """Kiểm tra lỗi có phải do Timeout không."""
    msg = str(error).lower()
    return "timeout" in msg or "time out" in msg or isinstance(error, asyncio.TimeoutError)


def evaluate_single_sample(sample, ragas_llm, ragas_emb, run_config):
    """
    Chấm 1 mẫu với 4 tiêu chí Ragas.
    Return dict: {metric_name: score}
    """
    dataset = Dataset.from_dict({
        "question": [sample["question"]],
        "answer": [sample["response_AI"]],
        "contexts": [sample["top_chunks"]],
        "ground_truth": [sample["ground_truth"]],
    })

    result = evaluate(
        dataset,
        metrics=METRICS,
        llm=ragas_llm,
        embeddings=ragas_emb,
        run_config=run_config,
    )

    df = result.to_pandas()
    scores = {}
    for name in METRIC_NAMES:
        val = df[name].iloc[0]
        # Xử lý NaN
        if val != val:  # NaN check
            scores[name] = None
        else:
            scores[name] = round(float(val), 4)
    return scores


def format_duration(seconds):
    """Format số giây thành chuỗi dễ đọc."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f} phút"
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h{m:02d}'"


# ╔══════════════════════════════════════════════════════════╗
# ║                      MAIN LOOP                           ║
# ╚══════════════════════════════════════════════════════════╝

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Step 4: RAGAS Evaluation")
    parser.add_argument(
        "-n", "--num-samples",
        type=int, default=None,
        help="Số lượng mẫu tối đa muốn chấm trong phiên này (mặc định: tất cả)"
    )
    args = parser.parse_args()

    start_wall = time.time()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print()
    print("═" * 62)
    print("  🏆  RAGAS EVALUATION — Step 4 (FULL)")
    print("═" * 62)
    print(f"  Thời gian bắt đầu : {now}")
    print(f"  LLM Judge          : {LLM_MODEL}")
    print(f"  Embedding          : {EMBEDDING_MODEL}")
    print(f"  Min cycle time     : {MIN_CYCLE_TIME}s (adaptive rate limiting)")
    print(f"  Input              : {INPUT_FILE}")
    print(f"  Output             : {OUTPUT_FILE}")
    print("═" * 62)

    # --- Load API keys ---
    key_mgr = APIKeyManager(API_KEYS_FILE)

    # --- Load input data ---
    all_data = load_input_data(INPUT_FILE)
    total_samples = len(all_data)
    print(f"📂 Đã tải {total_samples} mẫu từ input file")

    # --- Resume check ---
    init_csv(OUTPUT_FILE)
    completed_ids = get_completed_ids(OUTPUT_FILE)
    remaining = [s for s in all_data if s["id"] not in completed_ids]

    if args.num_samples is not None:
        print(f"🎯 Chỉ định chấm tối đa: {args.num_samples} mẫu trong phiên này")
        remaining = remaining[:args.num_samples]

    if completed_ids:
        print(f"⏩ Resume: đã chấm {len(completed_ids)}/{total_samples}, "
              f"phiên này sẽ chấm {len(remaining)} mẫu")
    else:
        print(f"🆕 Bắt đầu chấm mới: {len(remaining)} mẫu")

    if not remaining:
        print("\n✅ Không còn mẫu nào cần chấm hoặc đã chấm xong!")
        return

    # --- Ước tính thời gian ---
    est_time = len(remaining) * MIN_CYCLE_TIME
    print(f"⏱️  Ước tính thời gian: ~{format_duration(est_time)}")
    print(f"📊 Ước tính API calls: ~{len(remaining) * 6} LLM + ~{len(remaining)} Embedding")

    # --- Tạo models với API key đầu tiên ---
    ragas_llm, ragas_emb = create_models(key_mgr.current_key)
    print(f"🤖 Đang dùng {key_mgr.key_label}")

    # --- Chấm điểm ---
    success_count = 0
    error_count = 0
    all_keys_exhausted = False

    for i, sample in enumerate(remaining):
        cycle_start = time.time()
        global_idx = len(completed_ids) + i + 1  # Số thứ tự tổng thể

        # Header cho mẫu hiện tại
        q_preview = sample["question"][:55]
        print(f"\n{'─' * 62}")
        print(f"[{global_idx}/{total_samples}] {sample['id'][:16]}...")
        print(f"  Q: {q_preview}{'...' if len(sample['question']) > 55 else ''}")

        # --- Thử chấm, rotate key nếu cần ---
        evaluated = False
        while not evaluated:
            try:
                scores = evaluate_single_sample(
                    sample, ragas_llm, ragas_emb, RUN_CONFIG
                )

                # Lưu ngay vào CSV
                append_result_to_csv(OUTPUT_FILE, sample, scores)
                success_count += 1
                evaluated = True

                # In kết quả
                score_parts = []
                for name in METRIC_NAMES:
                    val = scores.get(name)
                    if val is not None:
                        score_parts.append(f"{name[:5]}={val:.2f}")
                    else:
                        score_parts.append(f"{name[:5]}=N/A")
                print(f"  ✅ {' | '.join(score_parts)}")

            except Exception as e:
                if is_quota_error(e):
                    print(f"  ⚠️  Quota exhausted trên {key_mgr.key_label}!")

                    if key_mgr.rotate():
                        # Tạo lại models với key mới
                        ragas_llm, ragas_emb = create_models(key_mgr.current_key)
                        print(f"  🔄 Retry với {key_mgr.key_label}...")
                        continue  # Retry mẫu này với key mới
                    else:
                        # Hết tất cả key
                        all_keys_exhausted = True
                        evaluated = True  # Thoát while loop
                else:
                    # Lỗi khác (không phải quota)
                    print(f"  ❌ Lỗi: {str(e)[:120]}")
                    traceback.print_exc()
                    error_count += 1
                    evaluated = True  # Bỏ qua mẫu này

        # Nếu hết key → dừng hoàn toàn
        if all_keys_exhausted:
            done_so_far = len(completed_ids) + success_count
            next_sample = global_idx
            print()
            print("═" * 62)
            print("  ⚠️   TẤT CẢ API KEY ĐÃ HẾT QUOTA")
            print("═" * 62)
            print(f"  Đã chấm  : {done_so_far}/{total_samples} mẫu")
            print(f"  Còn lại  : {total_samples - done_so_far} mẫu")
            print(f"  File CSV : {OUTPUT_FILE}")
            print()
            print("  Cách tiếp tục:")
            print(f"    1. Thêm API key mới vào {API_KEYS_FILE}")
            print(f"    2. Hoặc đợi 24h cho Google reset quota")
            print(f"    3. Chạy lại script → tự resume từ mẫu {next_sample}")
            print("═" * 62)
            break

        # --- Adaptive Rate Limiting ---
        elapsed = time.time() - cycle_start
        if elapsed < MIN_CYCLE_TIME:
            sleep_needed = MIN_CYCLE_TIME - elapsed
            print(f"  💤 Sleep {sleep_needed:.1f}s (cycle took {elapsed:.1f}s)")
            time.sleep(sleep_needed)
        else:
            print(f"  ⏱️  Cycle took {elapsed:.1f}s (no sleep needed)")

        # Progress ETA
        if success_count > 0 and success_count % 10 == 0:
            avg_cycle = (time.time() - start_wall) / success_count
            samples_left = len(remaining) - (i + 1)
            eta = avg_cycle * samples_left
            print(f"\n  📈 Progress: {success_count} done | "
                  f"ETA: ~{format_duration(eta)} | "
                  f"Avg: {avg_cycle:.1f}s/sample")

    # ── Tổng kết ──
    total_time = time.time() - start_wall
    final_done = len(completed_ids) + success_count

    print()
    print("═" * 62)
    print("  📊  KẾT QUẢ TỔNG HỢP")
    print("═" * 62)
    print(f"  Tổng mẫu đã chấm  : {final_done}/{total_samples}")
    print(f"  Phiên này          : {success_count} ✅  |  {error_count} ❌")
    print(f"  Thời gian chạy     : {format_duration(total_time)}")
    if success_count > 0:
        print(f"  Trung bình/mẫu     : {total_time / success_count:.1f}s")
    print(f"  Output             : {OUTPUT_FILE}")
    if final_done < total_samples:
        print(f"\n  ⚡ Chạy lại script để tiếp tục chấm {total_samples - final_done} mẫu còn lại!")
    else:
        print(f"\n  🎉 HOÀN THÀNH! Tất cả {total_samples} mẫu đã được chấm điểm!")
    print("═" * 62)


if __name__ == "__main__":
    main()
