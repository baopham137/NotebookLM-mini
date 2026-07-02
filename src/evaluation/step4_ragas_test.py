#!/usr/bin/env python3
"""
══════════════════════════════════════════════════════════════
  Step 4: RAGAS Evaluation — TEST (5-10 mẫu)
  Combo 1: Gemma 4 31B (LLM Judge) + Gemini Embedding 1
  Mục đích: Test nhanh pipeline trước khi chạy full
══════════════════════════════════════════════════════════════

Cách chạy:
    python scripts/step4_ragas_test.py              # Mặc định 5 mẫu
    python scripts/step4_ragas_test.py -n 10         # Chạy 10 mẫu
    python scripts/step4_ragas_test.py -n 3          # Chạy 3 mẫu

Cài đặt trước khi chạy:
    pip install ragas==0.1.21 langchain-google-genai datasets nest_asyncio
"""

import json
import os
import sys
import time
import argparse
import traceback
from pathlib import Path
from datetime import datetime

# Fix Unicode cho Windows
sys.stdout.reconfigure(encoding='utf-8')

# Fix asyncio cho Windows + Ragas
import nest_asyncio
nest_asyncio.apply()

from datasets import Dataset
from ragas import evaluate
try:
    from ragas.metrics import (
        Faithfulness,
        AnswerRelevancy,
        LLMContextPrecisionWithoutReference,
        LLMContextRecall,
    )
except ImportError:
    pass
from ragas.run_config import RunConfig
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

# Patch Ragas to prevent "Multiple candidates is not enabled" error with Gemini
_orig_agenerate_text = LangchainLLMWrapper.agenerate_text
async def _patched_agenerate_text(self, prompt, n=1, temperature=0.01, stop=None, callbacks=None):
    return await _orig_agenerate_text(self, prompt, n=1, temperature=temperature, stop=stop, callbacks=callbacks)
LangchainLLMWrapper.agenerate_text = _patched_agenerate_text

_orig_generate_text = LangchainLLMWrapper.generate_text
def _patched_generate_text(self, prompt, n=1, temperature=0.01, stop=None, callbacks=None):
    return _orig_generate_text(self, prompt, n=1, temperature=temperature, stop=stop, callbacks=callbacks)
LangchainLLMWrapper.generate_text = _patched_generate_text


# ╔══════════════════════════════════════════════════════════╗
# ║                    CONFIGURATION                         ║
# ╚══════════════════════════════════════════════════════════╝

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent.parent # Root dir: LLM-mini

INPUT_FILE = PROJECT_DIR / "tests" / "results" / "rag_results_hotpotqa.jsonl"
TEST_OUTPUT_FILE = PROJECT_DIR / "tests" / "results" / "ragbench_evaluation_test.csv"
API_KEYS_FILE = SCRIPT_DIR / "api_keys.txt"

LLM_MODEL = "gemma-4-31b-it"
EMBEDDING_MODEL = "models/gemini-embedding-001"
MIN_CYCLE_TIME = 26  # giây — adaptive rate limiting

METRICS = [Faithfulness(), AnswerRelevancy(), LLMContextPrecisionWithoutReference(), LLMContextRecall()]
METRIC_NAMES = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


# ╔══════════════════════════════════════════════════════════╗
# ║                   HELPER FUNCTIONS                       ║
# ╚══════════════════════════════════════════════════════════╝

def load_api_key():
    """Đọc API key đầu tiên từ .env hoặc api_keys.txt."""
    from dotenv import load_dotenv
    load_dotenv()
    
    env_keys_str = os.environ.get("GOOGLE_API_KEYS", "")
    if env_keys_str.strip():
        keys = [k.strip() for k in env_keys_str.split(",") if k.strip()]
        if keys:
            return keys[0]

    if not os.path.exists(API_KEYS_FILE):
        print(f"\n❌ Không tìm thấy file: {API_KEYS_FILE} và GOOGLE_API_KEYS trống.")
        print(f"   Hãy thêm GOOGLE_API_KEYS=\"key1,key2\" vào file .env")
        sys.exit(1)

    with open(API_KEYS_FILE, "r") as f:
        keys = [line.strip() for line in f
                if line.strip() and not line.startswith("#")]

    if not keys:
        print(f"\n❌ Không tìm thấy API key nào!")
        sys.exit(1)

    return keys[0]


def create_models(api_key):
    """Tạo Ragas LLM wrapper + Embedding wrapper."""
    llm = ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        google_api_key=api_key,
        temperature=0,
    )
    emb = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=api_key,
    )
    return LangchainLLMWrapper(llm), LangchainEmbeddingsWrapper(emb)


def load_input_data(filepath, n_samples):
    """Đọc N mẫu đầu tiên từ file JSONL."""
    data = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
                if len(data) >= n_samples:
                    break
    return data


def evaluate_single_sample(sample, ragas_llm, ragas_emb, run_config):
    """Chấm 1 mẫu với 4 tiêu chí Ragas."""
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
    for metric in METRICS:
        name = getattr(metric, 'name', type(metric).__name__)
        try:
            if name in df.columns:
                val = df[name].iloc[0]
                scores[name] = float(val) if pd.notna(val) else 0.0
            else:
                scores[name] = 0.0
        except Exception as e:
            scores[name] = 0.0
    return scores


def format_duration(seconds):
    """Format số giây thành chuỗi dễ đọc."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f} phút"
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h{m:02d}'"


# ╔══════════════════════════════════════════════════════════╗
# ║                       MAIN                               ║
# ╚══════════════════════════════════════════════════════════╝

def main():
    parser = argparse.ArgumentParser(
        description="RAGAS Evaluation — TEST MODE (5-10 mẫu)"
    )
    parser.add_argument(
        "-n", "--num-samples",
        type=int, default=5,
        help="Số mẫu để test (mặc định: 5)"
    )
    args = parser.parse_args()
    n = args.num_samples

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print()
    print("═" * 62)
    print("  🧪  RAGAS EVALUATION — TEST MODE")
    print("═" * 62)
    print(f"  Thời gian          : {now}")
    print(f"  Số mẫu test        : {n}")
    print(f"  LLM Judge          : {LLM_MODEL}")
    print(f"  Embedding          : {EMBEDDING_MODEL}")
    print(f"  Ước tính API calls : ~{n * 6} LLM + ~{n} Embedding")
    print(f"  Ước tính thời gian : ~{format_duration(n * MIN_CYCLE_TIME)}")
    print("═" * 62)

    # --- Load data & API key ---
    api_key = load_api_key()
    print(f"🔑 API Key: {api_key[:8]}...{api_key[-4:]}")

    test_data = load_input_data(INPUT_FILE, n)
    print(f"📂 Đã tải {len(test_data)} mẫu")

    # --- Tạo models ---
    print(f"🤖 Đang khởi tạo {LLM_MODEL} + {EMBEDDING_MODEL}...")
    ragas_llm, ragas_emb = create_models(api_key)

    run_config = RunConfig(
        max_workers=1,
        max_wait=120,
        max_retries=5,
    )

    # --- Chấm điểm ---
    results = []
    start_time = time.time()

    for i, sample in enumerate(test_data):
        cycle_start = time.time()

        q_preview = sample["question"][:55]
        print(f"\n{'─' * 62}")
        print(f"[{i + 1}/{n}] {sample['id'][:16]}...")
        print(f"  Q: {q_preview}{'...' if len(sample['question']) > 55 else ''}")
        print(f"  A (AI): {sample['response_AI'][:60]}...")

        try:
            scores = evaluate_single_sample(
                sample, ragas_llm, ragas_emb, run_config
            )
            results.append({"id": sample["id"], "question": sample["question"], **scores})

            # In kết quả
            for name in METRIC_NAMES:
                val = scores.get(name)
                bar = ""
                if val is not None:
                    filled = int(val * 20)
                    bar = "█" * filled + "░" * (20 - filled)
                    print(f"  {name:22s} {bar} {val:.4f}")
                else:
                    print(f"  {name:22s} {'?' * 20} N/A")

        except Exception as e:
            print(f"  ❌ Lỗi: {str(e)[:150]}")
            traceback.print_exc()
            results.append({"id": sample["id"], "error": str(e)[:200]})

        # Adaptive rate limiting (trừ mẫu cuối)
        if i < len(test_data) - 1:
            elapsed = time.time() - cycle_start
            if elapsed < MIN_CYCLE_TIME:
                sleep_needed = MIN_CYCLE_TIME - elapsed
                print(f"  💤 Sleep {sleep_needed:.1f}s")
                time.sleep(sleep_needed)

    # ── Tổng kết ──
    total_time = time.time() - start_time
    success = [r for r in results if "error" not in r]

    print()
    print("═" * 62)
    print("  📊  KẾT QUẢ TEST")
    print("═" * 62)

    if success:
        # Bảng tổng hợp
        print(f"\n  {'ID':<18} {'faith':>6} {'relev':>6} {'prec':>6} {'recall':>6}")
        print(f"  {'─' * 18} {'─' * 6} {'─' * 6} {'─' * 6} {'─' * 6}")

        totals = {name: 0.0 for name in METRIC_NAMES}
        count = 0

        for r in success:
            vals = []
            for name in METRIC_NAMES:
                v = r.get(name)
                if v is not None:
                    vals.append(f"{v:6.3f}")
                    totals[name] += v
                else:
                    vals.append("   N/A")
            print(f"  {r['id'][:18]} {vals[0]} {vals[1]} {vals[2]} {vals[3]}")
            count += 1

        # Trung bình
        print(f"  {'─' * 18} {'─' * 6} {'─' * 6} {'─' * 6} {'─' * 6}")
        avg_vals = []
        for name in METRIC_NAMES:
            avg = totals[name] / count if count > 0 else 0
            avg_vals.append(f"{avg:6.3f}")
        print(f"  {'TRUNG BÌNH':<18} {avg_vals[0]} {avg_vals[1]} {avg_vals[2]} {avg_vals[3]}")

    # Lưu kết quả test
    if success:
        os.makedirs(os.path.dirname(TEST_OUTPUT_FILE), exist_ok=True)
        import csv
        with open(TEST_OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "question",
                "faithfulness", "answer_relevancy",
                "context_precision", "context_recall",
            ])
            for r in success:
                writer.writerow([
                    r["id"], r["question"],
                    r.get("faithfulness", ""),
                    r.get("answer_relevancy", ""),
                    r.get("context_precision", ""),
                    r.get("context_recall", ""),
                ])
        print(f"\n  💾 Kết quả test đã lưu tại: {TEST_OUTPUT_FILE}")

    errors = [r for r in results if "error" in r]
    print(f"\n  Tổng cộng  : {len(success)} ✅  |  {len(errors)} ❌")
    print(f"  Thời gian  : {format_duration(total_time)}")
    if success:
        print(f"  TB/mẫu     : {total_time / len(success):.1f}s")

    print("═" * 62)

    if success:
        print("\n  ✅ Test OK! Bạn có thể chạy full evaluation:")
        print("     python scripts/step4_ragas_evaluate.py")
    else:
        print("\n  ❌ Tất cả mẫu test đều lỗi. Kiểm tra API key và kết nối.")

    print()


if __name__ == "__main__":
    main()
