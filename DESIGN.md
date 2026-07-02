# NotebookLM Clone — DESIGN.md

# Kiến Trúc Hệ Thống Cấp Production

**Phiên bản:** 1.1 (Local Vision Model Edition)  
**Tác giả:** Son Pham  
**Ngày cập nhật:** 2026-06-14  
**Tính năng:** Airgapped/Offline-First (không cần Internet)

---

## Mục Lục

1. [Tổng Quan Kiến Trúc](#1-tổng-quan-kiến-trúc)
2. [Luồng Dữ Liệu Tổng Thể](#2-luồng-dữ-liệu-tổng-thể)
3. [Local Vision Model Architecture](#3-local-vision-model-architecture-airgapped)
4. [Pipeline Ingestion Theo Định Dạng](#4-pipeline-ingestion-theo-định-dạng)
   - 4.1 PDF
   - 4.2 DOCX
   - 4.3 PPTX
   - 4.4 Markdown (.md)
   - 4.5 TXT (.txt)
   - 4.6 Website (HTML / URL)
   - 4.7 Google Docs
   - 4.8 Google Slides
   - 4.9 YouTube
   - 4.10 Audio
   - 4.11 Image
   - 4.12 Copy-Paste Text
   - 4.13 CSV / Excel (Spreadsheet)
5. [Document Tree — Định Dạng Nội Bộ Thống Nhất](#5-document-tree--định-dạng-nội-bộ-thống-nhất)
6. [Markdown Canonical Format](#6-markdown-canonical-format)
7. [Metadata Schema](#7-metadata-schema)
8. [Chunking Strategy](#8-chunking-strategy)
9. [Dense Retrieval — Vector Index](#9-dense-retrieval--vector-index)
10. [Sparse Retrieval — BM25 / Sparse Vector](#10-sparse-retrieval--bm25--sparse-vector)
11. [Qdrant Collection Design](#11-qdrant-collection-design)
12. [Hybrid Search & Fusion](#12-hybrid-search--fusion)
13. [Reranker](#13-reranker)
14. [Query Pipeline End-to-End](#14-query-pipeline-end-to-end)
15. [Citation System](#15-citation-system)
16. [Cấu Trúc Thư Mục Dự Án](#16-cấu-trúc-thư-mục-dự-án)
17. [Tech Stack Đề Xuất (Mức 2 — Airgapped/Offline)](#17-tech-stack-đề-xuất-mức-2--airgappedoffline)

---

## 1. Tổng Quan Kiến Trúc

Hệ thống NotebookLM Clone bao gồm hai luồng chính:

```
┌─────────────────────────────────────────────────────────────────┐
│                        INGESTION PIPELINE                       │
│                                                                 │
│  PDF / DOCX / PPTX / HTML / YouTube / Audio / Image / Text     │
│                          │                                      │
│                          ▼                                      │
│               Format-Specific Parser                            │
│                          │                                      │
│                          ▼                                      │
│                    Document Tree                                │
│                          │                                      │
│                          ▼                                      │
│               Markdown Canonical Format                         │
│                          │                                      │
│               ┌──────────┴──────────┐                          │
│               ▼                     ▼                          │
│       Dense Embedding         Sparse Encoding                  │
│               │                     │                          │
│               ▼                     ▼                          │
│      Qdrant Dense Index    Qdrant Sparse Index                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         QUERY PIPELINE                          │
│                                                                 │
│                        User Query                              │
│                          │                                      │
│               ┌──────────┴──────────┐                          │
│               ▼                     ▼                          │
│       Dense Search          Sparse Search                      │
│    (Qdrant Dense)        (Qdrant Sparse)                       │
│               │                     │                          │
│               └──────────┬──────────┘                          │
│                          ▼                                      │
│                 Weighted RRF Fusion                            │
│                          │                                      │
│                          ▼                                      │
│                Cross-Encoder Reranker                          │
│                          │                                      │
│                          ▼                                      │
│                    Top-K Chunks                                │
│                          │                                      │
│                          ▼                                      │
│                         LLM                                    │
│                          │                                      │
│                          ▼                                      │
│               Answer + Citation Metadata                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Luồng Dữ Liệu Tổng Thể

```
Source File
    │
    ▼
[1] Format Detection
    │
    ▼
[2] Format-Specific Parser
    │
    ▼
[3] Raw Object List
    {text, image, table, bbox, font_size, page}
    │
    ▼
[4] Layout Analysis + Reading Order
    │
    ▼
[5] Semantic Classification
    {title, heading, paragraph, figure, table, footer, caption}
    │
    ▼
[6] Relationship Builder
    {caption_of, belongs_to, follows}
    │
    ▼
[7] Vision / OCR (nếu có ảnh)
    │
    ▼
[8] Document Tree (AST)
    │
    ▼
[9] Markdown Renderer
    │
    ▼
[10] Metadata Enrichment
    {document_id, source_type, language, section_path, page, ...}
    │
    ▼
[11] Chunking
    │
    ├──────────────────────────┐
    ▼                          ▼
[12a] Dense Embedding     [12b] Sparse Encoding
    │                          │
    ▼                          ▼
[13] Qdrant Upsert (Dense + Sparse trong cùng collection)
```

---

## 3. Unified Multimodal Architecture (LLaVA) — Airgapped

Thay vì dùng 2 model riêng (1 cho vision, 1 cho LLM), hệ thống sử dụng **LLaVA Multimodal Model** chạy trên máy local. LLaVA vừa xử lý hình ảnh vừa sinh text, hoàn toàn offline.

### 3.1 Kiến Trúc Tổng Quan (Unified Pipeline)

```
┌─────────────────────────────────────────────────────────────────┐
│                    IMAGE PROCESSING PIPELINE                    │
│                       (Airgapped Mode)                          │
│                                                                 │
│               Image File (.png, .jpg, .webp)                   │
│                          │                                      │
│              ┌───────────┼───────────┐                         │
│              ▼           ▼           ▼                         │
│          Has Text?   Simple Image?  Complex Chart?            │
│              │           │           │                         │
│              ▼           ▼           ▼                         │
│        Tesseract OCR  LLaVA Vision  LLaVA 13B/34B             │
│        (Fast, Local)  (7B Model)    (Slower, Better)          │
│              │           │           │                         │
│              └───────────┼───────────┘                         │
│                          ▼                                      │
│                  Image Description                             │
│            {text_extracted, caption, type}                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 LLaVA Model Options

**LLaVA 7B** (~5GB VRAM)

- ✅ Nhanh (1-2s/image)
- ⚠️ Chất lượng thấp, hiểu hạn chế
- Dùng cho: Demo, testing, máy yếu

**LLaVA 13B** (~10GB VRAM) — **Khuyến nghị**

- ✅ Cân bằng tốt: nhanh (2-3s) + chất lượng tốt
- ✅ Hiểu diagram, chart, Vietnamese
- ✅ Vừa xử lý vision vừa sinh text chất lượng
- Dùng cho: Production, balanced setup

**LLaVA 34B** (~24GB VRAM)

- ✅ Chất lượng cao (gần GPT-4V)
- ⚠️ Chậm (4-6s/image)
- Dùng cho: High-precision tasks, GPU 24GB+

**Fallback: Tesseract OCR** (khi chỉ cần text extraction)

- Siêu nhanh (< 100ms/image)
- Chỉ trích xuất text từ image (OCR)
- Dùng khi: Image là scan document, không cần vision understanding

### 3.3 Auto-Detection & Device-Aware Model Selection

**Problem:** Mỗi thiết bị có cấu hình khác nhau. Làm sao để hệ thống **tự động** phát hiện VRAM available và chọn model phù hợp?

**Solution:** Auto-detection script phát hiện:

- 🖥️ GPU VRAM (NVIDIA/AMD/Apple Silicon)
- 💾 System RAM & CPU cores
- 🤖 Recommend model size (7B/13B/34B)
- ⚙️ Suggest configuration

```python
import subprocess
import psutil
import json
import os

class DeviceDetector:
    """Auto-detect device specs và recommend LLaVA model."""

    @staticmethod
    def get_gpu_vram() -> dict:
        """Detect GPU VRAM từ NVIDIA/AMD/Apple."""
        try:
            # NVIDIA GPU
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.total', '--format=csv,nounits'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                vram_mb = int(result.stdout.strip().split('\n')[0])
                return {
                    "gpu_type": "NVIDIA",
                    "vram_gb": vram_mb / 1024,
                    "available": True
                }
        except:
            pass

        try:
            # Check Apple Silicon (Metal)
            result = subprocess.run(
                ['system_profiler', 'SPDisplaysDataType'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if 'Apple' in result.stdout or 'M1' in result.stdout or 'M2' in result.stdout:
                # Apple Silicon uses unified memory
                system_ram = psutil.virtual_memory().total / (1024**3)
                return {
                    "gpu_type": "Apple Silicon",
                    "unified_memory_gb": system_ram * 0.7,  # Conservative 70%
                    "available": True
                }
        except:
            pass

        return {
            "gpu_type": "Not detected",
            "vram_gb": 0,
            "available": False
        }

    @staticmethod
    def get_system_specs() -> dict:
        """Get CPU, RAM, và storage info."""
        return {
            "cpu_cores": psutil.cpu_count(logical=False),
            "cpu_threads": psutil.cpu_count(logical=True),
            "ram_gb": psutil.virtual_memory().total / (1024**3),
            "available_ram_gb": psutil.virtual_memory().available / (1024**3),
            "disk_free_gb": psutil.disk_usage('/').free / (1024**3)
        }

    @staticmethod
    def recommend_model(gpu_vram_gb: float, system_ram_gb: float) -> dict:
        """
        Recommend LLaVA model size dựa trên VRAM & System RAM.

        Logic:
        - 7B: VRAM ≥ 5GB (minimal)
        - 13B: VRAM ≥ 10GB (recommended)
        - 34B: VRAM ≥ 24GB (high-end)
        - Fallback: Tesseract OCR nếu không đủ
        """
        # Prefer GPU VRAM, fallback to system RAM
        effective_vram = gpu_vram_gb if gpu_vram_gb > 0 else (system_ram_gb * 0.5)

        if effective_vram >= 24:
            return {
                "model": "llava:34b",
                "vram_required": 24,
                "speed": "Slow (4-6s/image)",
                "quality": "Excellent (GPT-4V level)",
                "reason": f"VRAM {effective_vram:.1f}GB >= 24GB"
            }
        elif effective_vram >= 10:
            return {
                "model": "llava:13b",
                "vram_required": 10,
                "speed": "Medium (2-3s/image)",
                "quality": "Good (production ready)",
                "reason": f"VRAM {effective_vram:.1f}GB >= 10GB"
            }
        elif effective_vram >= 5:
            return {
                "model": "llava:7b",
                "vram_required": 5,
                "speed": "Fast (1-2s/image)",
                "quality": "Acceptable (basic understanding)",
                "reason": f"VRAM {effective_vram:.1f}GB >= 5GB"
            }
        else:
            return {
                "model": "tesseract-ocr",
                "vram_required": 0.1,
                "speed": "Very fast (<100ms/image)",
                "quality": "OCR only (text extraction)",
                "reason": f"VRAM {effective_vram:.1f}GB < 5GB (fallback)",
                "warning": "Limited to text extraction, no vision understanding"
            }

    @classmethod
    def auto_detect(cls) -> dict:
        """
        Full auto-detection pipeline. Returns recommended config.
        """
        gpu_info = cls.get_gpu_vram()
        system_specs = cls.get_system_specs()

        gpu_vram = gpu_info.get("vram_gb", gpu_info.get("unified_memory_gb", 0))
        recommendation = cls.recommend_model(gpu_vram, system_specs["ram_gb"])

        return {
            "device": {
                "gpu": gpu_info,
                "system": system_specs
            },
            "recommended_model": recommendation,
            "config": {
                "model": recommendation["model"],
                "base_url": "http://localhost:11434",
                "timeout": 120,
                "temperature": 0.3
            }
        }


# Usage Example
if __name__ == "__main__":
    detector = DeviceDetector()
    result = detector.auto_detect()

    print("=" * 60)
    print("📊 DEVICE AUTO-DETECTION REPORT")
    print("=" * 60)
    print(f"\n🖥️  GPU: {result['device']['gpu']['gpu_type']}")
    print(f"   VRAM: {result['device']['gpu'].get('vram_gb', result['device']['gpu'].get('unified_memory_gb', 0)):.1f}GB")
    print(f"\n💾 System:")
    print(f"   RAM: {result['device']['system']['ram_gb']:.1f}GB")
    print(f"   Available: {result['device']['system']['available_ram_gb']:.1f}GB")
    print(f"   CPU: {result['device']['system']['cpu_cores']} cores / {result['device']['system']['cpu_threads']} threads")

    rec = result['recommended_model']
    print(f"\n✅ RECOMMENDED MODEL: {rec['model']}")
    print(f"   Reason: {rec['reason']}")
    print(f"   Quality: {rec['quality']}")
    print(f"   Speed: {rec['speed']}")
    print(f"   VRAM Required: {rec['vram_required']}GB")

    if "warning" in rec:
        print(f"   ⚠️  Warning: {rec['warning']}")

    print(f"\n⚙️  Recommended Ollama Setup:")
    print(f"   ollama pull {rec['model']}")
    print(f"   ollama serve")
    print("=" * 60)
```

**Auto-Detection Logic:**

| Detected VRAM | Recommended   | Quality              | Speed              |
| ------------- | ------------- | -------------------- | ------------------ |
| ≥ 24GB        | llava:34b     | Excellent ⭐⭐⭐⭐⭐ | Slow (4-6s)        |
| 10-24GB       | llava:13b     | Good ⭐⭐⭐⭐        | Medium (2-3s)      |
| 5-10GB        | llava:7b      | Acceptable ⭐⭐⭐    | Fast (1-2s)        |
| < 5GB         | tesseract-ocr | OCR Only             | Very Fast (<100ms) |

### 3.4 Implementation Example (LLaVA + Ollama)

```python
import requests
from PIL import Image
import base64

def encode_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def describe_image_with_llava(image_path: str, model: str = "llava:13b") -> dict:
    """
    Dùng LLaVA via Ollama để mô tả hình ảnh.
    Ollama server phải chạy trên localhost:11434
    """
    image_b64 = encode_image_to_base64(image_path)

    prompt = """
Describe this image in detail:
1. What is the main subject?
2. List all text, labels, and annotations visible.
3. Describe relationships between components (arrows, connections, etc.).
4. What type of diagram/chart is this (if applicable)?
Provide structured output.
    """

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "temperature": 0.3  # Lower temp = more factual
        },
        timeout=60
    )

    if response.status_code == 200:
        return {
            "description": response.json()["response"],
            "model": model,
            "status": "success"
        }
    else:
        return {
            "description": "",
            "error": response.text,
            "status": "failed"
        }

def extract_text_with_tesseract(image_path: str) -> str:
    """
    Fallback: Dùng Tesseract OCR nhanh.
    """
    from pytesseract import pytesseract
    from PIL import Image

    img = Image.open(image_path)
    text = pytesseract.image_to_string(img, lang='eng+vie')
    return text

def describe_image_hybrid(image_path: str) -> dict:
    """
    Hybrid strategy: thử OCR trước, nếu không có text thì dùng LLaVA
    """
    # Bước 1: OCR (nhanh)
    ocr_text = extract_text_with_tesseract(image_path)

    if ocr_text.strip():  # Tìm thấy text
        return {
            "method": "tesseract_ocr",
            "text_extracted": ocr_text,
            "description": f"Text detected in image: {ocr_text[:200]}..."
        }
    else:  # Không có text, dùng LLaVA
        result = describe_image_with_llava(image_path)
        result["method"] = "llava_vision"
        return result
```



### 3.6 Model Zoo Manager & Auto-Installer
Hệ thống sử dụng module src/utils/hardware_profiler.py (đóng vai trò như một Model Manager) để quản lý kho **Model Zoo**. Tùy thuộc vào cấu hình thực tế của máy (VRAM/RAM/OS), hệ thống sẽ chọn các siêu phẩm tốt nhất hiện nay:
- **Tier 1 (>16GB VRAM):** llama3.2-vision:11b (High-End)
- **Tier 2 (8-16GB VRAM):** qwen2.5:7b (Mid-Range)
- **Tier 3 (4-8GB VRAM):** qwen2-vl:2b (Entry-Level)
- **Tier 4 (<4GB VRAM):** qwen2.5:1.5b (CPU/Low VRAM)

Đặc biệt, hệ thống tích hợp cơ chế **Interactive Auto-Install**. Nếu model được đề xuất chưa có sẵn trên máy, nó sẽ in ra gợi ý và hỏi ý kiến người dùng ([y/N]) để tự động chạy lệnh ollama pull tải model ngầm, mang lại trải nghiệm Onboarding như các phần mềm thương mại.

### 3.4 Setup Ollama (Offline Vision Model Server)

**Linux / macOS:**

```bash
# Cài Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull LLaVA model (chọn theo VRAM của máy)
ollama pull llava:7b      # ~5GB VRAM (nhanh, quá tối thiểu)
ollama pull llava:13b     # ~10GB VRAM (cân bằng)
ollama pull llava:34b     # ~24GB VRAM (best quality)

# Chạy server
ollama serve
```

**Windows (via WSL2 hoặc Native):**

```cmd
ollama pull llava:13b
ollama serve
```

**Docker:**

```bash
docker run -d \
  --gpus all \
  -p 11434:11434 \
  --name ollama_vision \
  ollama/ollama:latest

docker exec ollama_vision ollama pull llava:13b
```

### 3.5 Model Compression Techniques

**Problem:** LLaVA 13B = 10GB VRAM. Không phải ai cũng có GPU mạnh. Làm sao chạy model trên thiết bị yếu?

**Solution:** Nén model (compression) → Giảm kích thước 50-90% + tăng tốc độ + vẫn giữ chất lượng!

#### Các Phương Pháp Nén Model

| Phương Pháp             | Kích Thước | VRAM  | Tốc Độ        | Chất Lượng | Công Cụ               | Khi Nào Dùng                  |
| ----------------------- | ---------- | ----- | ------------- | ---------- | --------------------- | ----------------------------- |
| **GGUF (Quantization)** | 4B (INT4)  | 3-4GB | ⚡ 2-3x nhanh | 95%        | Ollama, llama.cpp     | ✅ Khuyên dùng (best balance) |
| GPTQ (INT4)             | 4B         | 2-3GB | ⚡ 3-4x nhanh | 93%        | AutoGPTQ              | Hiếm cần (chỉ inference)      |
| AWQ (INT4)              | 4B         | 2-3GB | ⚡ 2-3x nhanh | 94%        | AWQ                   | Alternative to GPTQ           |
| INT8                    | 5-6B       | 5-6GB | ⚡ 1.5x nhanh | 97%        | torch, transformers   | Lựa chọn thứ 2                |
| FP16 (baseline)         | 13B        | 10GB  | 1x            | 100%       | Standard              | Baseline (không nén)          |
| **Pruning**             | 8-10B      | 7-9GB | ⚡ 1.2x       | 96%        | LLaMA-Pruned          | Niche use case                |
| **Knowledge Distill**   | 3-5B       | 2-4GB | ⚡ 4-5x       | 85-90%     | DistilBERT, TinyLLaMA | Edge devices                  |

#### 3.5.1 Quantization — GGUF Format (Khuyên Dùng)

**GGUF** = Format tối ưu cho Ollama & llama.cpp. **Không cần VRAM GPU để quantize!**

**Ưu điểm:**

- ✅ Hỗ trợ Ollama (dùng ngay!)
- ✅ INT4 = 75% nhỏ hơn + 2-3x nhanh
- ✅ Quality drop minimal (~5%)
- ✅ Cross-platform (Mac/Windows/Linux)

**Ví dụ - Convert LLaVA to GGUF (INT4):**

```bash
# Bước 1: Download original model
git clone https://huggingface.co/liuhaotian/llava-v1.5-13b

# Bước 2: Cài llama.cpp (chứa convert tool)
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp

# Bước 3: Convert to GGUF format (tự động quantize INT4)
python convert.py \
  --model-dir ../llava-v1.5-13b \
  --outfile llava-13b-int4.gguf \
  --quant-method q4_k_m  # INT4 with K-means

# Bước 4: Dùng với Ollama
cp llava-13b-int4.gguf ~/.ollama/models/
ollama create llava:13b-q4 -f Modelfile
```

**Modelfile** (file cấu hình cho Ollama):

```
FROM llava-13b-int4.gguf
TEMPLATE "[INST] {{ .Prompt }} [/INST]"
PARAMETERS stop "[INST]" "INST"
```

**Result:**

```
Original: llava-13b-fp16.gguf → 26GB
Quantized: llava-13b-q4.gguf → 8GB (69% nhỏ hơn!)
VRAM: 10GB → 4GB
Tốc độ: 2-3s/image → 1.5s/image
```

#### 3.5.2 Quantization — INT8 (Alternative)

**INT8** = Nhỏ hơn GGUF INT4 nhưng giữ chất lượng tốt hơn.

```bash
# Dùng torch.quantization
python -c "
import torch
from transformers import AutoModelForCausalLM

model = AutoModelForCausalLM.from_pretrained('liuhaotian/llava-v1.5-13b')

# Dynamic quantization INT8
quantized_model = torch.quantization.quantize_dynamic(
    model,
    {torch.nn.Linear},  # Quantize only Linear layers
    dtype=torch.qint8
)

# Save
quantized_model.save_pretrained('llava-13b-int8')
"
```

#### 3.5.3 Pruning — Remove Redundant Weights

**Pruning** = Xoá các weights không quan trọng. Giảm kích thước mà không quantize.

```python
# Dùng thư viện: magnitude pruning
import torch
import torch.nn.utils.prune as prune

model = AutoModelForCausalLM.from_pretrained('llava-v1.5-13b')

# Prune 30% weights với lowest magnitude
for name, module in model.named_modules():
    if isinstance(module, torch.nn.Linear):
        prune.l1_unstructured(module, name='weight', amount=0.3)

# Apply pruning (permanent)
for name, module in model.named_modules():
    if hasattr(module, 'weight_orig'):
        prune.remove(module, 'weight')

# Fine-tune lại (10-20% training data)
# ... training loop ...

model.save_pretrained('llava-13b-pruned-30')
```

**Result:**

- Size: 13B → 9B (30% pruning)
- VRAM: 10GB → 7GB
- Quality: ~96% (minimal drop)
- Trade-off: Cần fine-tune (expensive)

#### 3.5.4 Knowledge Distillation — Small But Smart

**Knowledge Distill** = Train small model (3-5B) để bắt chước large model (13B).

```python
from transformers import DistilBertModel, DistilBertConfig

# Create small model (5B)
distill_config = DistilBertConfig(
    hidden_size=768,
    num_hidden_layers=6,  # 50% fewer layers
    intermediate_size=3072
)
small_model = DistilBertModel(distill_config)

# Loss = KL divergence between small & large output
teacher_model = AutoModel.from_pretrained('llava-13b')

def distillation_loss(small_output, teacher_output, temperature=4.0):
    return torch.nn.functional.kl_div(
        torch.log_softmax(small_output / temperature, dim=-1),
        torch.softmax(teacher_output / temperature, dim=-1),
        reduction='batchmean'
    ) * (temperature ** 2)
```

**Result:**

- Size: 13B → 3-5B (75% nhỏ hơn!)
- VRAM: 10GB → 2-3GB
- Tốc độ: 2-3s → 0.5s/image
- Quality: 85-90% (acceptable trade-off)
- **Use Case:** Mobile, edge devices

#### 3.5.5 LoRA — Low-Rank Adaptation (Fine-tuning Only)

**LoRA** = Không nén model, nhưng **thêm nhẹ learnable adapters** để custom cho task.

```python
from peft import LoraConfig, get_peft_model

base_model = AutoModelForCausalLM.from_pretrained('llava-13b')

lora_config = LoraConfig(
    r=16,  # Rank (nhỏ nhất là 8)
    lora_alpha=32,
    target_modules=['q_proj', 'v_proj', 'k_proj', 'o_proj'],
    lora_dropout=0.1,
    bias='none',
    task_type='CAUSAL_LM'
)

model = get_peft_model(base_model, lora_config)

# Training (chỉ cần train LoRA weights, không phải full model!)
# VRAM reduction: 10GB → 6-7GB (chỉ train adapters)
```

**Result:**

- VRAM: 10GB → 6-7GB (for training)
- LoRA file size: 10-50MB (rất nhỏ!)
- Quality: 100% (custom tuning)
- **Use Case:** Fine-tuning cho domain-specific tasks

#### 3.5.6 Comparison & Recommendation

```
Use Case                           | Recommend            | VRAM  | Speed | Quality
-----------------------------------+----------------------+-------+-------+--------
💻 Standard desktop (16GB GPU)     | LLaVA 13B (no nén)  | 10GB  | 2-3s  | ⭐⭐⭐⭐⭐
💻 Budget desktop (8GB GPU)        | LLaVA 13B INT4 GGUF | 4GB   | 1-2s  | ⭐⭐⭐⭐
💻 Weak laptop (4GB)               | LLaVA 7B INT4       | 2-3GB | 0.8s  | ⭐⭐⭐
📱 Mobile / Raspberry Pi (2GB)     | TinyLLaMA (distilled)| 1-2GB | 0.3s  | ⭐⭐
🖥️  Server (batch processing)     | LLaVA 34B FP16      | 24GB  | 4-6s  | ⭐⭐⭐⭐⭐
🎯 Domain-specific tuning          | Base model + LoRA    | 6-7GB | 2-3s  | ⭐⭐⭐⭐⭐
```

#### 3.5.7 Setup Compressed Model with Ollama

```bash
# 1️⃣ Download pre-quantized model (huggingface)
# Hoặc quantize yourself (see 3.5.1)

# 2️⃣ Create Modelfile
cat > Modelfile << 'EOF'
FROM llava-13b-int4.gguf  # Use quantized version
TEMPLATE "[INST] {{ .Prompt }} [/INST]"
PARAMETERS stop "[INST]"
PARAMETERS temperature 0.3
EOF

# 3️⃣ Build & run
ollama create llava:13b-q4 -f Modelfile
ollama run llava:13b-q4

# 4️⃣ Verify (should use less VRAM)
nvidia-smi  # Check VRAM usage
```

#### 3.5.8 Choosing Right Compression Method

```python
# Auto-select compression based on device
def get_compression_strategy(vram_gb: float, target_latency_s: float = 3.0):
    """Recommend compression method based on constraints."""

    if vram_gb >= 20:
        return {
            "method": "No compression (FP16)",
            "model": "llava:34b",
            "size": "26GB",
            "vram": 20,
            "latency": 4.5,
            "quality": 100
        }
    elif vram_gb >= 10:
        return {
            "method": "GGUF INT4 (Quantization)",
            "model": "llava:13b-q4",
            "size": "8GB",
            "vram": 5,
            "latency": 1.5,
            "quality": 95
        }
    elif vram_gb >= 5:
        return {
            "method": "GGUF INT5 (Quantization)",
            "model": "llava:7b-q5",
            "size": "5GB",
            "vram": 3,
            "latency": 0.8,
            "quality": 93
        }
    elif vram_gb >= 2:
        return {
            "method": "Knowledge Distillation",
            "model": "tinyllava:3b",
            "size": "2GB",
            "vram": 2,
            "latency": 0.3,
            "quality": 80
        }
    else:
        return {
            "method": "Fallback: Tesseract OCR",
            "model": "tesseract",
            "size": "0.1GB",
            "vram": 0.1,
            "latency": 0.05,
            "quality_note": "Text extraction only"
        }
```

---

## 4. Pipeline Ingestion Theo Định Dạng

> **TỐI ƯU HÓA VỚI MARKITDOWN (MICROSOFT):**
> Bạn hoàn toàn có thể giảm thiểu số lượng parser bằng cách sử dụng thư viện `markitdown`. Thay vì xây dựng parser riêng cho PDF, DOCX, PPTX, HTML, Excel, tất cả định dạng này có thể đưa qua `markitdown` để chuyển trực tiếp thành Markdown. Sau đó, ta chỉ cần một **Markdown Parser** (Mục 3.4) duy nhất để tạo Document Tree. Kiến trúc này giúp giảm 80% công sức viết custom parser!
> _(Các phần 3.1 - 3.8 dưới đây mô tả cơ chế bóc tách sâu bên dưới mà MarkItDown hoặc các parser chuyên dụng thực hiện)._

---

### 4.1 PDF

PDF là định dạng phức tạp nhất vì nó không lưu cấu trúc ngữ nghĩa mà chỉ lưu lệnh vẽ.

#### Input

```
hybrid_search_report.pdf
```

#### Step 1 — PDF Extractor

Thư viện đề xuất: `pdfplumber`, `PyMuPDF (fitz)`, `Docling`, `LlamaParse`

PDF Extractor đọc tất cả các object trên từng trang và xuất ra danh sách thô.

**Output của PDF Extractor (page_1.json):**

```json
{
  "document_metadata": {
    "filename": "hybrid_search_report.pdf",
    "total_pages": 5,
    "author": "Son Pham",
    "creation_date": "2026-01-10"
  },
  "page_metadata": {
    "page": 1,
    "width": 595,
    "height": 842
  },
  "objects": [
    {
      "id": "txt_001",
      "type": "text",
      "text": "HYBRID SEARCH FOR ENTERPRISE RAG",
      "bbox": [72, 60, 480, 90],
      "font_size": 24,
      "font_name": "Helvetica-Bold",
      "font_weight": "bold"
    },
    {
      "id": "txt_002",
      "type": "text",
      "text": "Author: Son Pham",
      "bbox": [72, 110, 220, 125],
      "font_size": 12,
      "font_name": "Helvetica",
      "font_weight": "normal"
    },
    {
      "id": "txt_003",
      "type": "text",
      "text": "Abstract",
      "bbox": [72, 150, 150, 170],
      "font_size": 18,
      "font_name": "Helvetica-Bold",
      "font_weight": "bold"
    },
    {
      "id": "txt_004",
      "type": "text",
      "text": "Hybrid Search combines sparse retrieval and dense retrieval to improve recall.",
      "bbox": [72, 190, 520, 230],
      "font_size": 12,
      "font_name": "Helvetica",
      "font_weight": "normal"
    },
    {
      "id": "img_001",
      "type": "image",
      "bbox": [120, 260, 450, 500],
      "image_path": "extracted/img_001.png"
    },
    {
      "id": "txt_005",
      "type": "text",
      "text": "Figure 1. Hybrid Search Architecture",
      "bbox": [120, 515, 360, 530],
      "font_size": 10,
      "font_name": "Helvetica",
      "font_weight": "normal"
    },
    {
      "id": "txt_006",
      "type": "text",
      "text": "The architecture consists of:",
      "bbox": [72, 560, 260, 580],
      "font_size": 12,
      "font_name": "Helvetica",
      "font_weight": "normal"
    },
    {
      "id": "txt_007",
      "type": "text",
      "text": "1. BM25 Retriever",
      "bbox": [90, 590, 220, 605],
      "font_size": 12,
      "font_name": "Helvetica",
      "font_weight": "normal"
    },
    {
      "id": "txt_008",
      "type": "text",
      "text": "2. Dense Retriever",
      "bbox": [90, 610, 240, 625],
      "font_size": 12,
      "font_name": "Helvetica",
      "font_weight": "normal"
    },
    {
      "id": "txt_009",
      "type": "text",
      "text": "3. Reranker",
      "bbox": [90, 630, 180, 645],
      "font_size": 12,
      "font_name": "Helvetica",
      "font_weight": "normal"
    },
    {
      "id": "txt_010",
      "type": "text",
      "text": "Table 1. Retrieval Performance",
      "bbox": [72, 670, 320, 690],
      "font_size": 10,
      "font_name": "Helvetica",
      "font_weight": "normal"
    },
    {
      "id": "table_001",
      "type": "table",
      "bbox": [72, 700, 500, 800],
      "headers": ["Method", "Recall", "Precision"],
      "rows": [
        ["BM25", "80", "85"],
        ["Dense", "87", "88"],
        ["Hybrid", "92", "91"]
      ]
    },
    {
      "id": "txt_011",
      "type": "text",
      "text": "Conclusion",
      "bbox": [72, 820, 180, 840],
      "font_size": 18,
      "font_name": "Helvetica-Bold",
      "font_weight": "bold"
    },
    {
      "id": "txt_012",
      "type": "text",
      "text": "Hybrid Search achieves the highest recall.",
      "bbox": [72, 850, 520, 870],
      "font_size": 12,
      "font_name": "Helvetica",
      "font_weight": "normal"
    },
    {
      "id": "txt_013",
      "type": "text",
      "text": "Page 1",
      "bbox": [280, 900, 330, 915],
      "font_size": 8,
      "font_name": "Helvetica",
      "font_weight": "normal"
    }
  ]
}
```

> **Lưu ý quan trọng:** Extractor chỉ biết `text`, `image`, `table` và `bbox`. Nó KHÔNG biết đâu là `title`, `heading`, `caption`, hay `footer`.

#### Step 2 — Layout Analysis + Reading Order

**Reading Order Engine** sắp xếp objects theo thứ tự đọc đúng (quan trọng với PDF đa cột).

Đầu ra reading order:

```json
{
  "reading_order": [
    "txt_001",
    "txt_002",
    "txt_003",
    "txt_004",
    "img_001",
    "txt_005",
    "txt_006",
    "txt_007",
    "txt_008",
    "txt_009",
    "txt_010",
    "table_001",
    "txt_011",
    "txt_012",
    "txt_013"
  ]
}
```

#### Step 3 — Semantic Classification

Layout Parser dùng font_size, font_weight, bbox, vị trí tương đối để phân loại:

```json
{
  "txt_001": { "label": "title", "confidence": 0.98 },
  "txt_002": { "label": "author", "confidence": 0.95 },
  "txt_003": { "label": "section_header", "confidence": 0.97 },
  "txt_004": { "label": "paragraph", "confidence": 0.99 },
  "img_001": { "label": "figure", "confidence": 0.99 },
  "txt_005": { "label": "figure_caption", "confidence": 0.96 },
  "txt_006": { "label": "paragraph", "confidence": 0.99 },
  "txt_007": { "label": "list_item", "confidence": 0.95 },
  "txt_008": { "label": "list_item", "confidence": 0.95 },
  "txt_009": { "label": "list_item", "confidence": 0.95 },
  "txt_010": { "label": "table_caption", "confidence": 0.96 },
  "table_001": { "label": "table", "confidence": 0.99 },
  "txt_011": { "label": "section_header", "confidence": 0.97 },
  "txt_012": { "label": "paragraph", "confidence": 0.99 },
  "txt_013": { "label": "footer", "confidence": 0.94 }
}
```

#### Step 4 — Relationship Builder

Ghép caption với figure/table dựa trên proximity (khoảng cách bbox):

```json
{
  "relations": [
    {
      "type": "caption_of",
      "source": "txt_005",
      "target": "img_001",
      "distance_points": 15
    },
    {
      "type": "caption_of",
      "source": "txt_010",
      "target": "table_001",
      "distance_points": 10
    },
    {
      "type": "footer",
      "source": "txt_013",
      "page": 1
    }
  ]
}
```

#### Step 5 — Local Vision Model (cho ảnh) [AIRGAPPED]

File ảnh `extracted/img_001.png` được gửi tới Local Vision Model (LLaVA via Ollama):

**Prompt:**

```
Describe the content of this figure in detail, including all labels, arrows, components, and relationships shown.
```

**Local Vision Model Output (LLaVA 13B):**

```json
{
  "image_id": "img_001",
  "method": "llava_13b_ollama",
  "description": "The figure illustrates a Hybrid Search pipeline. It consists of four components arranged vertically: BM25 Retriever at the top, followed by Dense Retriever, then a Fusion Layer that combines outputs from both retrievers, and finally a Reranker at the bottom that produces the final ranked results.",
  "labels_detected": [
    "BM25 Retriever",
    "Dense Retriever",
    "Fusion Layer",
    "Reranker"
  ],
  "type": "architecture_diagram",
  "processing_time_ms": 3200,
  "model_size": "13B"
}
```

> **Lợi ích offline:**
>
> - ✅ Không cần Internet, không gửi dữ liệu ra cloud
> - ✅ Không có latency API, chỉ phụ thuộc vào GPU local
> - ✅ Không có chi phí API token
> - ❌ Chậm hơn GPT-4o (3-5s/image vs 1-2s), nhưng chấp nhận được cho batch processing

---

### 4.2 DOCX

Word đã có cấu trúc ngữ nghĩa sẵn (Heading 1, Heading 2, Normal, Table, Image). Pipeline đơn giản hơn PDF.

```
DOCX
  │
  ▼
python-docx Parser
  │
  ▼
Paragraph Extractor
  ├── Heading 1, 2, 3
  ├── Normal Text
  ├── List (bullet/numbered)
  ├── Table (rows, headers)
  └── Inline Image
  │
  ▼
Local Vision Model (inline images) [LLaVA or Tesseract]
  │
  ▼
Document Tree
  │
  ▼
Markdown
```

**Output của DOCX Parser:**

```json
{
  "document_metadata": {
    "filename": "report.docx",
    "source_type": "docx",
    "author": "Son Pham",
    "language": "en"
  },
  "objects": [
    {
      "id": "h1_001",
      "type": "heading",
      "level": 1,
      "text": "Deep Learning Overview"
    },
    {
      "id": "para_001",
      "type": "paragraph",
      "text": "Deep learning is a subset of machine learning..."
    },
    {
      "id": "h2_001",
      "type": "heading",
      "level": 2,
      "text": "CNN Architecture"
    },
    {
      "id": "img_001",
      "type": "image",
      "image_path": "extracted/img_001.png",
      "alt_text": "CNN Diagram"
    },
    {
      "id": "table_001",
      "type": "table",
      "headers": ["Model", "Accuracy", "Params"],
      "rows": [
        ["ResNet-50", "76.1%", "25M"],
        ["EfficientNet", "84.2%", "66M"]
      ]
    }
  ]
}
```

> **Ưu điểm DOCX so với PDF:** Không cần Layout Analysis vì cấu trúc semantic có sẵn (Heading 1 = title, Heading 2 = section, v.v.)

---

### 4.3 PPTX

PowerPoint cần xử lý theo từng slide, vì mỗi slide là một đơn vị nội dung độc lập.

```
PPTX
  │
  ▼
python-pptx Parser
  │
  ▼
Slide Extractor
  ├── Slide Title (text box đầu tiên)
  ├── Content Text Boxes
  ├── Images / Charts / Diagrams
  ├── Tables
  └── Speaker Notes
  │
  ▼
Slide Layout Parser
  (phân biệt title vs content vs image)
  │
  ▼
Local Vision Model (images/charts) [LLaVA or Tesseract]
  │
  ▼
Document Tree
  │
  ▼
Markdown
```

**Output của Slide Extractor (slide_3):**

```json
{
  "slide_number": 3,
  "objects": [
    {
      "id": "title_s3",
      "type": "slide_title",
      "text": "Hybrid Search Architecture"
    },
    {
      "id": "content_s3_001",
      "type": "text_box",
      "text": "Combines BM25 and Dense Retrieval for better recall."
    },
    {
      "id": "img_s3_001",
      "type": "image",
      "image_path": "extracted/slide_3_img_001.png"
    },
    {
      "id": "notes_s3",
      "type": "speaker_notes",
      "text": "Emphasize that Hybrid Search improves recall by 5-10% over single methods."
    }
  ]
}
```

---

### 4.4 Markdown (.md)

Markdown đã có cấu trúc semantic tường minh (`#`, `##`, `**bold**`, `| table |`, `` `code` ``). Pipeline không cần Layout Analysis hay Semantic Classification vì ý nghĩa của từng phần tử đã được mã hóa sẵn trong cú pháp.

````
Markdown File (.md)
  │
  ▼
Encoding Detector
  (UTF-8 / UTF-16 / Latin-1)
  │
  ▼
Text Normalizer
  (normalize line endings: CRLF → LF,
   normalize unicode, strip BOM)
  │
  ▼
Markdown Parser → AST
  (thư viện: mistletoe / markdown-it-py)
  │
  Nodes nhận diện được trực tiếp từ cú pháp:
  ├── ATX Heading (#, ##, ###)     → heading level 1/2/3
  ├── Setext Heading (===, ---)    → heading level 1/2
  ├── Paragraph                   → paragraph
  ├── Bullet List (-, *, +)       → list (unordered)
  ├── Ordered List (1. 2. 3.)     → list (ordered)
  ├── Fenced Code Block (```)     → code_block + language tag
  ├── Inline Code (`)             → inline_code
  ├── Table (| col | col |)       → table
  ├── Image (![alt](url))         → figure (alt text = caption)
  ├── Blockquote (>)              → blockquote
  └── Horizontal Rule (---)       → section_divider
  │
  ▼
Document Tree Builder
  (map trực tiếp từ AST nodes → Document Tree nodes,
   KHÔNG cần suy luận thêm)
  │
  ▼
Markdown Output
  (giữ nguyên nội dung gốc, chỉ normalize format)
````

**Ví dụ: Markdown input → AST → Document Tree**

Input Markdown:

````markdown
# Hybrid Search

## BM25

BM25 là thuật toán sparse retrieval.

### Công thức

```python
score = tf * idf
```
````

| Method | Recall |
| ------ | ------ |
| BM25   | 80     |

````

AST nodes (markdown-it-py):

```json
[
  { "type": "heading", "level": 1, "text": "Hybrid Search" },
  { "type": "heading", "level": 2, "text": "BM25" },
  { "type": "paragraph", "text": "BM25 là thuật toán sparse retrieval." },
  { "type": "heading", "level": 3, "text": "Công thức" },
  { "type": "code_block", "language": "python", "text": "score = tf * idf" },
  { "type": "table",
    "headers": ["Method", "Recall"],
    "rows": [["BM25", "80"]]
  }
]
````

Document Tree output:

```json
{
  "type": "document",
  "children": [
    {
      "type": "section",
      "heading_level": 1,
      "title": "Hybrid Search",
      "children": [
        {
          "type": "section",
          "heading_level": 2,
          "title": "BM25",
          "children": [
            {
              "type": "paragraph",
              "text": "BM25 là thuật toán sparse retrieval."
            },
            {
              "type": "section",
              "heading_level": 3,
              "title": "Công thức",
              "children": [
                {
                  "type": "code_block",
                  "language": "python",
                  "text": "score = tf * idf"
                },
                {
                  "type": "table",
                  "headers": ["Method", "Recall"],
                  "rows": [["BM25", "80"]]
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

> **Điểm khác biệt then chốt so với TXT:** Với Markdown, bước Semantic Classification hoàn toàn không cần thiết vì `#` đã xác định rõ là heading level 1, `##` là heading level 2, `|table|` là table. Không có suy luận, không có xác suất confidence.

---

### 4.5 TXT (.txt)

TXT không có cấu trúc semantic. Pipeline phải **suy luận cấu trúc** từ các dấu hiệu heuristic trong văn bản thuần.

```
TXT File (.txt)
  │
  ▼
Encoding Detector
  (UTF-8 / UTF-16 / Latin-1 / Windows-1252)
  │
  ▼
Text Normalizer
  (normalize line endings,
   normalize unicode,
   collapse excessive blank lines)
  │
  ▼
Language Detector
  (langdetect / lingua-py)
  → metadata: language = "vi" / "en" / ...
  │
  ▼
Heuristic Section Detector
  Phát hiện cấu trúc dựa trên:
  ├── ALL CAPS line          → có thể là title hoặc heading
  ├── Line kết thúc bằng ":"  → có thể là heading nhỏ
  ├── Numbered prefix         → "1. " / "1.1 " → heading có số
  ├── Blank line trước/sau    → dấu hiệu paragraph boundary
  ├── Indentation             → có thể là list hoặc code
  ├── Dòng bắt đầu bằng "-", "*", "•" → list item
  └── Dòng toàn dấu "=" hoặc "-" → underline-style heading
  │
  ▼
Confidence Scoring
  (mỗi heuristic cho một confidence score,
   kết hợp để đưa ra label)
  │
  ▼
Semantic Classifier Output:
  ├── title        (confidence ≥ 0.85)
  ├── heading_1    (confidence ≥ 0.75)
  ├── heading_2    (confidence ≥ 0.70)
  ├── paragraph    (mặc định nếu không khớp)
  ├── list_item    (confidence ≥ 0.80)
  └── code_block   (confidence ≥ 0.75, dựa trên indentation)
  │
  ▼
Document Tree Builder
  │
  ▼
Markdown Renderer
  (chuyển TXT → Markdown để downstream pipeline
   xử lý đồng nhất)
```

**Ví dụ: TXT input → Heuristic Detection → Document Tree**

Input TXT:

```
HYBRID SEARCH FOR ENTERPRISE RAG

Abstract:
Hybrid Search kết hợp BM25 và Dense Retrieval để cải thiện recall.

Các thành phần:
- BM25 Retriever
- Dense Retriever
- Reranker

1. Giới thiệu
BM25 là phương pháp truyền thống dựa trên từ khóa.

1.1 Lịch sử BM25
BM25 được phát triển bởi Robertson vào năm 1994.
```

Heuristic Detection output:

```json
[
  {
    "text": "HYBRID SEARCH FOR ENTERPRISE RAG",
    "heuristics_matched": ["ALL_CAPS", "short_line", "followed_by_blank"],
    "label": "title",
    "confidence": 0.92
  },
  {
    "text": "Abstract:",
    "heuristics_matched": ["ends_with_colon", "short_line"],
    "label": "heading_2",
    "confidence": 0.78
  },
  {
    "text": "Hybrid Search kết hợp BM25 và Dense Retrieval để cải thiện recall.",
    "heuristics_matched": ["preceded_by_heading", "normal_length"],
    "label": "paragraph",
    "confidence": 0.95
  },
  {
    "text": "Các thành phần:",
    "heuristics_matched": ["ends_with_colon", "followed_by_list"],
    "label": "heading_2",
    "confidence": 0.81
  },
  {
    "text": "- BM25 Retriever",
    "heuristics_matched": ["starts_with_dash"],
    "label": "list_item",
    "confidence": 0.97
  },
  {
    "text": "- Dense Retriever",
    "heuristics_matched": ["starts_with_dash"],
    "label": "list_item",
    "confidence": 0.97
  },
  {
    "text": "- Reranker",
    "heuristics_matched": ["starts_with_dash"],
    "label": "list_item",
    "confidence": 0.97
  },
  {
    "text": "1. Giới thiệu",
    "heuristics_matched": ["numbered_prefix", "short_line"],
    "label": "heading_1",
    "confidence": 0.88
  },
  {
    "text": "BM25 là phương pháp truyền thống dựa trên từ khóa.",
    "heuristics_matched": ["preceded_by_heading"],
    "label": "paragraph",
    "confidence": 0.95
  },
  {
    "text": "1.1 Lịch sử BM25",
    "heuristics_matched": ["numbered_decimal_prefix", "short_line"],
    "label": "heading_2",
    "confidence": 0.86
  },
  {
    "text": "BM25 được phát triển bởi Robertson vào năm 1994.",
    "heuristics_matched": ["preceded_by_heading"],
    "label": "paragraph",
    "confidence": 0.95
  }
]
```

Document Tree output:

```json
{
  "type": "document",
  "children": [
    {
      "type": "title",
      "text": "HYBRID SEARCH FOR ENTERPRISE RAG"
    },
    {
      "type": "section",
      "heading_level": 2,
      "title": "Abstract",
      "children": [
        {
          "type": "paragraph",
          "text": "Hybrid Search kết hợp BM25 và Dense Retrieval để cải thiện recall."
        }
      ]
    },
    {
      "type": "section",
      "heading_level": 2,
      "title": "Các thành phần",
      "children": [
        {
          "type": "list",
          "list_type": "unordered",
          "items": ["BM25 Retriever", "Dense Retriever", "Reranker"]
        }
      ]
    },
    {
      "type": "section",
      "heading_level": 1,
      "title": "1. Giới thiệu",
      "children": [
        {
          "type": "paragraph",
          "text": "BM25 là phương pháp truyền thống dựa trên từ khóa."
        },
        {
          "type": "section",
          "heading_level": 2,
          "title": "1.1 Lịch sử BM25",
          "children": [
            {
              "type": "paragraph",
              "text": "BM25 được phát triển bởi Robertson vào năm 1994."
            }
          ]
        }
      ]
    }
  ]
}
```

Markdown output (sau khi render từ Document Tree):

```markdown
# HYBRID SEARCH FOR ENTERPRISE RAG

## Abstract

Hybrid Search kết hợp BM25 và Dense Retrieval để cải thiện recall.

## Các thành phần

- BM25 Retriever
- Dense Retriever
- Reranker

# 1. Giới thiệu

BM25 là phương pháp truyền thống dựa trên từ khóa.

## 1.1 Lịch sử BM25

BM25 được phát triển bởi Robertson vào năm 1994.
```

> **Hạn chế của TXT Parser:** Heuristic detection không bao giờ đạt độ chính xác 100%. Với TXT có cấu trúc không rõ ràng (VD: văn bản email, ghi chú không có heading), Document Tree có thể flatten toàn bộ thành một list `paragraph` dài. Đây là behavior mong đợi — thà flatten an toàn còn hơn phân loại sai thành heading.

---

### 4.6 Website (HTML / URL)

```
HTML URL / File
  │
  ▼
HTTP Fetcher (nếu là URL)
  │
  ▼
HTML Parser (BeautifulSoup / lxml)
  │
  ▼
DOM Tree
  │
  ▼
Boilerplate Removal
  (loại nav, footer, ads, sidebar)
  │
  ▼
Content Extractor
  ├── h1, h2, h3 → heading
  ├── p → paragraph
  ├── ul/ol → list
  ├── table → table
  ├── img → image (src, alt)
  └── code/pre → code block
  │
  ▼
Local Vision Model (img tags) [LLaVA or Tesseract]
  │
  ▼
Document Tree
  │
  ▼
Markdown
```

---

### 4.7 Google Docs

```
Google Docs URL
  │
  ▼
Google Docs API (documents.get)
  │
  ▼
Document Structure Extractor
  ├── paragraphs (với style: HEADING_1, HEADING_2, NORMAL_TEXT)
  ├── tables
  └── inline images
  │
  ▼
Local Vision Model (inline images) [LLaVA or Tesseract]
  │
  ▼
Document Tree
  │
  ▼
Markdown
```

---

### 4.8 Google Slides

```
Google Slides URL
  │
  ▼
Google Slides API (presentations.get)
  │
  ▼
Slide-by-Slide Extractor
  ├── title shape
  ├── body shapes (text boxes)
  ├── image shapes
  ├── table shapes
  └── speaker notes
  │
  ▼
Local Vision Model (image shapes, chart shapes) [LLaVA or Tesseract]
  │
  ▼
Document Tree
  │
  ▼
Markdown
```

---

### 4.9 YouTube

```
YouTube URL
  │
  ▼
YouTube Data API
  ├── Video Title
  ├── Description
  ├── Channel
  └── Duration
  │
  ▼
Transcript Fetcher
  (youtube_transcript_api hoặc Whisper nếu không có sẵn)
  │
  ▼
Timestamp Parser
  {start: 0, end: 15, text: "In this video..."}
  │
  ▼
Chapter Extractor
  (từ Description hoặc YouTube Chapters API)
  │
  ▼
Document Tree
  │
  ▼
Markdown
```

**Document Tree cho YouTube:**

```json
{
  "type": "document",
  "source_type": "youtube",
  "title": "Hybrid Search Tutorial",
  "channel": "AI Academy",
  "children": [
    {
      "type": "section",
      "title": "Introduction",
      "timestamp_start": 0,
      "timestamp_end": 180,
      "children": [
        {
          "type": "paragraph",
          "text": "In this video we will cover Hybrid Search...",
          "timestamp_start": 0,
          "timestamp_end": 30
        }
      ]
    },
    {
      "type": "section",
      "title": "BM25 Explanation",
      "timestamp_start": 180,
      "timestamp_end": 540,
      "children": [...]
    }
  ]
}
```

---

### 4.10 Audio

```
Audio File (.mp3 / .wav / .m4a)
  │
  ▼
ASR — Automatic Speech Recognition
  (Whisper large-v3 đề xuất)
  │
  ▼
Raw Transcript với Timestamps
  {start: 0.0, end: 4.2, text: "Today we discuss..."}
  │
  ▼
Speaker Diarization (nếu nhiều người nói)
  (pyannote/speaker-diarization)
  │
  ▼
Segment Merger
  (gộp các segment ngắn thành đoạn có nghĩa)
  │
  ▼
Document Tree
  │
  ▼
Markdown
```

**Markdown output cho Audio:**

```markdown
# Audio Transcript: meeting_2026_06_13.mp3

## Speaker A

[00:00 - 00:45]

Chúng ta sẽ thảo luận về kiến trúc Hybrid Search hôm nay.

## Speaker B

[00:46 - 01:30]

BM25 kết hợp Dense Retrieval sẽ cải thiện recall đáng kể.
```

---

### 4.11 Image [AIRGAPPED]

```
Image File (.png / .jpg / .webp)
  │
  ▼
┌─────────────────────────────────────┐
│  Local Vision Pipeline (Offline)   │
│                                     │
│  Step 1: Try OCR (Tesseract)       │
│  ├─ Thành công? → Dùng text       │
│  └─ Thất bại? → Bước 2            │
│                                     │
│  Step 2: Use Vision Model (LLaVA)  │
│  ├─ Describe image content         │
│  └─ Extract labels & components   │
└─────────────────────────────────────┘
  │
  ▼
Layout Analysis
  (nếu image là scan tài liệu)
  │
  ▼
Document Tree
  │
  ▼
Markdown
```

---

### 4.12 Copy-Paste Text

```text
Raw Pasted Text
  │
  ▼
Metadata Auto-Generator
  (Tạo document_id, gán source_type = "pasted_text",
   tạo title/filename ảo từ nội dung hoặc timestamp)
  │
  ▼
Encoding Normalizer
  │
  ▼
Language Detector
  │
  ▼
Section Detector
  (heuristic: blank lines, ALL CAPS, numbered headers)
  │
  ▼
Document Tree
  │
  ▼
Markdown
```

---

### 4.13 CSV / Excel (Spreadsheet)

Spreadsheet (bảng tính) có cấu trúc dạng lưới rập khuôn. Pipeline không trích xuất theo đoạn văn mà tập trung vào việc bảo toàn hàng, cột và tiêu đề.

```text
CSV / XLSX File
  │
  ▼
Pandas / openpyxl
  │
  ▼
Table Extractor
  (Phát hiện header row, index column)
  │
  ▼
Chunking Strategy đặc biệt cho Table
  (Cắt theo block hàng/cột nếu bảng quá lớn,
   hoặc serialize thành Markdown/HTML table)
  │
  ▼
Document Tree (chứa node type "table")
  │
  ▼
Markdown Renderer
```

---

## 5. Document Tree — Định Dạng Nội Bộ Thống Nhất

Sau khi mọi định dạng đi qua parser riêng, tất cả đều được chuyển thành **Document Tree** — một cấu trúc AST thống nhất.

**Schema đầy đủ của Document Tree:**

```json
{
  "type": "document",

  "document_metadata": {
    "document_id": "doc_001",
    "filename": "hybrid_search_report.pdf",
    "source_type": "pdf",
    "language": "en",
    "author": "Son Pham",
    "ingestion_time": "2026-06-13T10:00:00Z",
    "total_pages": 5
  },

  "children": [
    {
      "type": "title",
      "text": "HYBRID SEARCH FOR ENTERPRISE RAG",
      "page": 1
    },

    {
      "type": "author",
      "text": "Son Pham"
    },

    {
      "type": "section",
      "heading_level": 2,
      "title": "Abstract",
      "page": 1,
      "children": [
        {
          "type": "paragraph",
          "text": "Hybrid Search combines sparse retrieval and dense retrieval to improve recall.",
          "page": 1
        },

        {
          "type": "figure",
          "figure_number": 1,
          "caption": "Figure 1. Hybrid Search Architecture",
          "image_path": "extracted/img_001.png",
          "description": "The figure illustrates a Hybrid Search pipeline consisting of BM25 Retriever, Dense Retriever, Fusion Layer and Reranker.",
          "page": 1
        },

        {
          "type": "paragraph",
          "text": "The architecture consists of:",
          "page": 1
        },

        {
          "type": "list",
          "list_type": "ordered",
          "items": ["BM25 Retriever", "Dense Retriever", "Reranker"],
          "page": 1
        },

        {
          "type": "table",
          "table_number": 1,
          "caption": "Table 1. Retrieval Performance",
          "headers": ["Method", "Recall", "Precision"],
          "rows": [
            ["BM25", "80", "85"],
            ["Dense", "87", "88"],
            ["Hybrid", "92", "91"]
          ],
          "page": 1
        }
      ]
    },

    {
      "type": "section",
      "heading_level": 2,
      "title": "Conclusion",
      "page": 1,
      "children": [
        {
          "type": "paragraph",
          "text": "Hybrid Search achieves the highest recall.",
          "page": 1
        }
      ]
    }
  ]
}
```

> **Nguyên tắc thiết kế Document Tree:**
>
> - Footer và page number KHÔNG được đưa vào Document Tree (đã lọc ở bước Layout Classification)
> - Caption luôn được gắn vào figure/table tương ứng, không tồn tại độc lập
> - Section có thể lồng nhau nhiều cấp (section → sub-section → sub-sub-section)
> - Mỗi node giữ thông tin `page` để phục vụ citation

---

## 6. Markdown Canonical Format

Document Tree được render thành Markdown bằng một **Tree Traversal Renderer** đơn giản (không dùng AI).

**Quy tắc render:**

| Node Type       | Markdown Output                              |
| --------------- | -------------------------------------------- |
| title           | `# {text}`                                   |
| author          | `Author: {text}`                             |
| section h2      | `## {title}`                                 |
| section h3      | `### {title}`                                |
| paragraph       | `{text}`                                     |
| list (ordered)  | `1. item\n2. item`                           |
| list (bullet)   | `- item\n- item`                             |
| figure          | `### Figure {n}. {caption}\n\n{description}` |
| table           | `### Table {n}. {caption}\n\n\| ... \|`      |
| code_block      | ` ```lang\ncode\n``` `                       |
| speaker (audio) | `## Speaker {name}\n\n[{start}-{end}]`       |
| timestamp       | `[{HH:MM:SS}]`                               |

**Markdown output hoàn chỉnh:**

```markdown
# HYBRID SEARCH FOR ENTERPRISE RAG

Author: Son Pham

## Abstract

Hybrid Search combines sparse retrieval and dense retrieval to improve recall.

### Figure 1. Hybrid Search Architecture

The figure illustrates a Hybrid Search pipeline consisting of BM25 Retriever, Dense Retriever, Fusion Layer and Reranker.

The architecture consists of:

1. BM25 Retriever
2. Dense Retriever
3. Reranker

### Table 1. Retrieval Performance

| Method | Recall | Precision |
| ------ | ------ | --------- |
| BM25   | 80     | 85        |
| Dense  | 87     | 88        |
| Hybrid | 92     | 91        |

## Conclusion

Hybrid Search achieves the highest recall.
```

---

## 7. Metadata Schema

Metadata được **kế thừa và tích lũy** xuyên suốt pipeline. Không có metadata nào bị mất.

### 6.1 Document Metadata (gắn trước khi chunk)

```json
{
  "document_id": "doc_001",
  "filename": "hybrid_search_report.pdf",
  "source_type": "pdf",
  "language": "en",
  "author": "Son Pham",
  "ingestion_time": "2026-06-13T10:00:00Z",
  "total_pages": 5
}
```

> **Lưu ý đối với Copy-Paste Text:** Dữ liệu copy-paste không có file vật lý. Pipeline sẽ tự động gán `source_type` là `"pasted_text"`, và trường `filename` sẽ được thay bằng một tiêu đề ảo (Ví dụ: tên do người dùng nhập, `"Pasted Note - 2026-06-13"`, hoặc lấy 5 từ đầu tiên của văn bản). Các trường như `total_pages` hay `author` sẽ bị bỏ trống.

### 6.2 Chunk Metadata (gắn trong lúc chunk)

Mỗi chunk **kế thừa toàn bộ Document Metadata** và bổ sung thêm:

```json
{
  "chunk_id": "chunk_015",
  "document_id": "doc_001",
  "filename": "hybrid_search_report.pdf",
  "source_type": "pdf",
  "language": "en",
  "author": "Son Pham",

  "page": 1,

  "section_path": ["HYBRID SEARCH FOR ENTERPRISE RAG", "Abstract"],

  "content_type": "paragraph",

  "chunk_index": 15,
  "token_count": 82,

  "text": "Hybrid Search combines sparse retrieval and dense retrieval to improve recall."
}
```

> **Lưu ý `section_path`:** Luôn lưu toàn bộ hierarchy, không chỉ section nhỏ nhất.  
> Ví dụ với tài liệu có 3 cấp heading `1 > 1.1 > 1.1.1`:

```json
{
  "section_path": ["Deep Learning", "CNN", "ResNet"]
}
```

### 6.3 Figure Chunk Metadata

```json
{
  "chunk_id": "chunk_016",
  "document_id": "doc_001",
  "filename": "hybrid_search_report.pdf",
  "source_type": "pdf",
  "language": "en",

  "page": 1,
  "section_path": ["HYBRID SEARCH FOR ENTERPRISE RAG", "Abstract"],

  "content_type": "figure",
  "figure_number": 1,
  "caption": "Figure 1. Hybrid Search Architecture",

  "chunk_index": 16,
  "token_count": 45,

  "text": "Figure 1. Hybrid Search Architecture\n\nThe figure illustrates a Hybrid Search pipeline consisting of BM25 Retriever, Dense Retriever, Fusion Layer and Reranker."
}
```

### 6.4 Table Chunk Metadata

```json
{
  "chunk_id": "chunk_017",
  "document_id": "doc_001",
  "filename": "hybrid_search_report.pdf",
  "source_type": "pdf",
  "language": "en",

  "page": 1,
  "section_path": ["HYBRID SEARCH FOR ENTERPRISE RAG", "Abstract"],

  "content_type": "table",
  "table_number": 1,
  "caption": "Table 1. Retrieval Performance",

  "chunk_index": 17,
  "token_count": 60,

  "text": "Table 1. Retrieval Performance\n\n| Method | Recall | Precision |\n|--------|--------|--------|\n| BM25 | 80 | 85 |\n| Dense | 87 | 88 |\n| Hybrid | 92 | 91 |"
}
```

### 6.5 YouTube Chunk Metadata

```json
{
  "chunk_id": "chunk_042",
  "document_id": "doc_yt_001",
  "filename": "Hybrid Search Tutorial",
  "source_type": "youtube",
  "language": "en",

  "timestamp_start": 180,
  "timestamp_end": 240,
  "section_path": ["Hybrid Search Tutorial", "BM25 Explanation"],

  "content_type": "transcript_segment",

  "chunk_index": 42,
  "token_count": 95,

  "text": "BM25 is a probabilistic ranking function that uses term frequency and inverse document frequency to score documents."
}
```

---

## 8. Chunking Strategy

### 7.1 Chiến lược đề xuất cho Mức 2

```
Markdown
  │
  ▼
Step 1: Header-Based Splitting
  (cắt theo H1, H2, H3)
  │
  ▼
Step 2: Size Check
  Nếu chunk > 512 tokens?
  │
  ├─ YES → Semantic Splitting
  │         (cắt tại điểm đổi chủ đề)
  │
  └─ NO  → Giữ nguyên
  │
  ▼
Step 3: Metadata Inheritance
  (gắn document_id, source_type, language,
   section_path, page, content_type, chunk_index, token_count)
  │
  ▼
Step 4: Overlap
  (50-100 token overlap giữa các chunk liền kề)
```

### 7.2 Ví dụ Chunking

**Markdown đầu vào:**

```markdown
## Abstract

Hybrid Search combines sparse retrieval and dense retrieval to improve recall.

### Figure 1. Hybrid Search Architecture

The figure illustrates a Hybrid Search pipeline...

### Table 1. Retrieval Performance

| Method | Recall | Precision |
| ------ | ------ | --------- |
| BM25   | 80     | 85        |

## Conclusion

Hybrid Search achieves the highest recall.
```

**Chunks sau khi cắt:**

```
Chunk 0:
"## Abstract\n\nHybrid Search combines sparse retrieval..."
→ content_type: paragraph, section_path: ["Title", "Abstract"]

Chunk 1:
"### Figure 1. Hybrid Search Architecture\n\nThe figure illustrates..."
→ content_type: figure, figure_number: 1

Chunk 2:
"### Table 1. Retrieval Performance\n\n| Method | Recall |..."
→ content_type: table, table_number: 1

Chunk 3:
"## Conclusion\n\nHybrid Search achieves the highest recall."
→ content_type: paragraph, section_path: ["Title", "Conclusion"]
```

### 7.3 Token Budget

| Content Type | Max Tokens per Chunk |
| ------------ | -------------------- |
| paragraph    | 512                  |
| figure       | 256                  |
| table        | 512                  |
| code_block   | 1024                 |
| transcript   | 512                  |

---

## 9. Dense Retrieval — Vector Index

### 8.1 Embedding Model

Đề xuất: `BAAI/bge-m3` (hỗ trợ cả dense và sparse, đa ngôn ngữ)

```python
from FlagEmbedding import BGEM3FlagModel

model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)

chunk_text = "Hybrid Search combines BM25 and Dense Retrieval."

output = model.encode(
    chunk_text,
    return_dense=True,
    return_sparse=True
)

dense_vector  = output["dense_vecs"]   # shape: (1024,)
sparse_vector = output["lexical_weights"]  # dict {token: weight}
```

### 8.2 Dense Vector Schema

```json
{
  "chunk_id": "chunk_015",
  "dense_vector": [0.12, -0.45, 0.89, "..."],
  "vector_dimension": 1024,
  "embedding_model": "BAAI/bge-m3"
}
```

---

## 10. Sparse Retrieval — BM25 / Sparse Vector

> **Lưu ý về BM25:** BM25 truyền thống là thuật toán đếm tần suất từ vựng (TF-IDF). Tuy nhiên, thiết kế này sử dụng **Sparse Vector từ BGE-M3** (dựa trên mô hình ngôn ngữ lớn) làm giải pháp thay thế hoàn hảo. BGE-M3 tự động học được tầm quan trọng của các từ vựng (lexical weights) đa ngôn ngữ theo ngữ cảnh, mang lại hiệu quả vượt trội so với thuật toán BM25 truyền thống trong khi vẫn dùng chung một cơ sở hạ tầng Sparse Retrieval.

### 9.1 Sparse Vector từ BGE-M3

BGE-M3 trả về `lexical_weights` — tương đương sparse vector:

```python
sparse_output = model.encode(
    "Hybrid Search combines BM25 and Dense Retrieval.",
    return_sparse=True
)

# sparse_output["lexical_weights"] ví dụ:
# {"hybrid": 2.3, "search": 1.8, "bm25": 2.1, "dense": 1.9, "retrieval": 2.0}
```

### 9.2 Chuyển thành Qdrant Sparse Format

```python
from qdrant_client.models import SparseVector

# Giả sử vocabulary mapping:
# "hybrid" → index 4512
# "search" → index 8901
# "bm25"   → index 1203
# "dense"  → index 2344

sparse_vector = SparseVector(
    indices=[4512, 8901, 1203, 2344, 5678],
    values=[2.3, 1.8, 2.1, 1.9, 2.0]
)
```

---

## 11. Qdrant Collection Design

### 10.1 Tạo Collection

```python
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, SparseVectorParams,
    Distance, Modifier
)

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
    collection_name="notebooklm_clone",

    vectors_config={
        "dense": VectorParams(
            size=1024,
            distance=Distance.COSINE
        )
    },

    sparse_vectors_config={
        "sparse": SparseVectorParams(
            modifier=Modifier.IDF
        )
    }
)
```

### 10.2 Upsert một Point

```python
from qdrant_client.models import PointStruct, SparseVector

client.upsert(
    collection_name="notebooklm_clone",
    points=[
        PointStruct(
            id="chunk_015",

            vector={
                "dense": [0.12, -0.45, 0.89, ...],     # 1024 chiều
                "sparse": SparseVector(
                    indices=[4512, 8901, 1203, 2344],
                    values=[2.3, 1.8, 2.1, 1.9]
                )
            },

            payload={
                "text": "Hybrid Search combines sparse retrieval and dense retrieval to improve recall.",
                "chunk_id": "chunk_015",
                "document_id": "doc_001",
                "filename": "hybrid_search_report.pdf",
                "source_type": "pdf",
                "language": "en",
                "author": "Son Pham",
                "page": 1,
                "section_path": [
                    "HYBRID SEARCH FOR ENTERPRISE RAG",
                    "Abstract"
                ],
                "content_type": "paragraph",
                "chunk_index": 15,
                "token_count": 82
            }
        )
    ]
)
```

> **Lưu ý:** `text` luôn được lưu trong `payload` để sau khi retrieve có thể gửi cho LLM.

---

## 12. Hybrid Search & Fusion

### 11.1 Query Encoding

```python
query = "Hybrid Search cải thiện recall như thế nào?"

query_output = model.encode(
    query,
    return_dense=True,
    return_sparse=True
)

query_dense  = query_output["dense_vecs"]
query_sparse = query_output["lexical_weights"]
```

### 11.2 Dense Search

```python
dense_results = client.search(
    collection_name="notebooklm_clone",
    query_vector=("dense", query_dense),
    limit=20,
    with_payload=True
)
```

### 11.3 Sparse Search

```python
from qdrant_client.models import SparseVector, NamedSparseVector

sparse_results = client.search(
    collection_name="notebooklm_clone",
    query_vector=NamedSparseVector(
        name="sparse",
        vector=SparseVector(
            indices=list(query_sparse_indices),
            values=list(query_sparse_values)
        )
    ),
    limit=20,
    with_payload=True
)
```

### 11.4 Weighted RRF Fusion

Kết hợp kết quả Dense và Sparse bằng Reciprocal Rank Fusion:

```python
def weighted_rrf_fusion(dense_results, sparse_results,
                        dense_weight=0.6, sparse_weight=0.4,
                        k=60):
    scores = {}

    for rank, result in enumerate(dense_results):
        chunk_id = result.id
        rrf_score = dense_weight / (k + rank + 1)
        scores[chunk_id] = scores.get(chunk_id, 0) + rrf_score

    for rank, result in enumerate(sparse_results):
        chunk_id = result.id
        rrf_score = sparse_weight / (k + rank + 1)
        scores[chunk_id] = scores.get(chunk_id, 0) + rrf_score

    # Sắp xếp theo điểm tổng hợp
    sorted_chunks = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    return sorted_chunks[:20]  # Top-20 sau fusion
```

**Trọng số đề xuất:**

| Loại Query            | dense_weight | sparse_weight |
| --------------------- | ------------ | ------------- |
| Câu hỏi ngữ nghĩa     | 0.7          | 0.3           |
| Tìm từ khoá chính xác | 0.3          | 0.7           |
| Mặc định              | 0.6          | 0.4           |

---

## 13. Reranker

Sau fusion, top-20 chunks được đưa qua Cross-Encoder Reranker để sắp xếp lại chính xác hơn.

### 12.1 Model

Đề xuất: `BAAI/bge-reranker-v2-m3`

```python
from FlagEmbedding import FlagReranker

reranker = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=True)

query = "Hybrid Search cải thiện recall như thế nào?"

# Tạo pairs (query, chunk_text)
pairs = [
    (query, chunk["text"])
    for chunk in top_20_chunks
]

# Score từng pair
scores = reranker.compute_score(pairs, normalize=True)

# Sắp xếp lại
reranked = sorted(
    zip(top_20_chunks, scores),
    key=lambda x: x[1],
    reverse=True
)

top_5_chunks = [chunk for chunk, score in reranked[:5]]
```

### 12.2 Luồng đầy đủ

```
User Query
  │
  ├── Dense Search (top-20)
  │
  └── Sparse Search (top-20)
         │
         ▼
   Weighted RRF Fusion (top-20 merged)
         │
         ▼
   Cross-Encoder Reranker
         │
         ▼
   Top-5 Chunks
         │
         ▼
   LLM (với context = top-5 chunks)
```

---

## 14. Query Pipeline End-to-End

```python
from embedding.dense_encoder import encode_dense
from embedding.sparse_encoder import encode_sparse
from retrieval.dense_search import search_dense
from retrieval.sparse_search import search_sparse
from retrieval.fusion import weighted_rrf_fusion
from retrieval.payload_fetcher import fetch_payloads
from retrieval.reranker import rerank_results
from generation.prompt_builder import build_rag_prompt
from generation.llm_client import generate_answer
from citation.citation_builder import build_citations

def query_pipeline(user_query: str, filters: dict = None) -> dict:

    # Step 1: Encode query
    query_dense = encode_dense(user_query)
    query_sparse = encode_sparse(user_query)

    # Step 2: Dense Search
    dense_results = search_dense(query_dense, filters=filters, limit=20)

    # Step 3: Sparse Search
    sparse_results = search_sparse(query_sparse, filters=filters, limit=20)

    # Step 4: RRF Fusion
    fused_results = weighted_rrf_fusion(dense_results, sparse_results)

    # Step 5: Fetch full payloads
    top_20_chunks = fetch_payloads(fused_results)

    # Step 6: Rerank
    top_5_chunks = rerank_results(user_query, top_20_chunks, top_k=5)

    # Step 7: Build context for LLM
    prompt = build_rag_prompt(user_query, top_5_chunks)

    # Step 8: LLM Generation
    response = generate_answer(prompt)

    # Step 9: Return answer + citation metadata
    citations = build_citations(top_5_chunks)

    return {
        "answer": response,
        "citations": citations
    }
```

---

## 15. Citation System

Mỗi câu trả lời của LLM được kèm theo citation metadata để người dùng có thể kiểm chứng nguồn.

### 14.1 Citation Schema

```json
{
  "answer": "Hybrid Search cải thiện recall bằng cách kết hợp BM25 và Dense Retrieval...",

  "citations": [
    {
      "citation_index": 1,
      "filename": "hybrid_search_report.pdf",
      "source_type": "pdf",
      "page": 1,
      "section_path": ["HYBRID SEARCH FOR ENTERPRISE RAG", "Abstract"],
      "content_type": "paragraph",
      "text_snippet": "Hybrid Search combines sparse retrieval and dense retrieval to improve recall."
    },
    {
      "citation_index": 2,
      "filename": "hybrid_search_report.pdf",
      "source_type": "pdf",
      "page": 1,
      "section_path": ["HYBRID SEARCH FOR ENTERPRISE RAG", "Abstract"],
      "content_type": "table",
      "caption": "Table 1. Retrieval Performance",
      "text_snippet": "| Method | Recall | Precision |..."
    }
  ]
}
```

### 14.2 Citation cho YouTube

```json
{
  "citation_index": 3,
  "filename": "Hybrid Search Tutorial",
  "source_type": "youtube",
  "timestamp_start": 180,
  "timestamp_end": 240,
  "section_path": ["Hybrid Search Tutorial", "BM25 Explanation"],
  "content_type": "transcript_segment",
  "text_snippet": "BM25 is a probabilistic ranking function..."
}
```

---

## 16. Cấu Trúc Thư Mục Dự Án

`	ext
D:\LLM_mini\
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── LICENSE
├── README.md
├── requirements.txt
├── DESIGN.md
├── pytest.ini
├── main.py
├── logs/
│   └── app.log
├── tests/
│   └── test_app.py
├── frontend/               <-- Giao diện người dùng (React, Vite, Tailwind CSS)
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── App.jsx
│   │   └── index.css
│   └── package.json
└── src/                    <-- Core Backend (FastAPI, Python)
    ├── ingestion/
    │   ├── __init__.py
    │   ├── document_tree.py        <-- Document Tree Builder
    │   ├── markdown_renderer.py    <-- Document Tree -> Markdown
    │   ├── parsers/
    │   │   ├── __init__.py
    │   │   ├── markitdown_parser.py<-- Universal Parser: PDF, DOCX, PPTX, HTML, Excel -> MD
    │   │   ├── markdown_parser.py  <-- Parse file MD -> Document Tree
    │   │   ├── web_parser.py       <-- Web URL -> HTML -> Document Tree
    │   │   ├── youtube_parser.py   <-- YouTube URL -> Document Tree
    │   │   ├── audio_parser.py     <-- Audio -> Transcript -> Document Tree
    │   │   ├── image_parser.py     <-- Image -> OCR + Vision -> Document Tree
    │   │   └── text_parser.py      <-- TXT / Copy-Paste -> Document Tree
    │   ├── layout/
    │   │   ├── __init__.py
    │   │   ├── reading_order.py    <-- Sắp xếp reading order
    │   │   ├── semantic_classifier.py<-- Phân loại title/heading/paragraph...
    │   │   └── relationship_builder.py<-- Ghép caption với figure/table
    │   └── vision/
    │       ├── __init__.py
    │       ├── local_vision_model.py<-- LLaVA + Ollama
    │       ├── tesseract_ocr.py     <-- Fallback OCR
    │       └── vision_pipeline.py   <-- Hybrid strategy
    ├── chunking/
    │   ├── __init__.py
    │   └── chunker.py              <-- Chunking Strategy (Hierarchical/Semantic)
    ├── embeddings/
    │   ├── __init__.py
    │   └── embedder.py             <-- Gọi Embedding Models (Mục 9)
    ├── vectordb/
    │   ├── __init__.py
    │   └── vector_store.py         <-- Quản lý Qdrant & BM25 (Mục 10, 11)
    ├── retrieval/
    │   ├── __init__.py
    │   ├── context_builder.py
    │   ├── hybrid_search.py
    │   ├── reranker.py
    │   └── router.py

    ├── llm/
    │   ├── __init__.py
    │   ├── llm_client.py
    │   ├── text_llm.py
    │   └── vision_llm.py
    ├── api/
    │   ├── __init__.py
    │   └── api.py                  <-- Main FastAPI endpoints
    ├── utils/
    │   ├── __init__.py
    │   ├── hardware_profiler.py
    │   ├── config.py
    │   ├── cache.py
    │   ├── observability.py
    │   ├── filters.py
    │   ├── schemas.py
    │   ├── stream_batching.py
    │   ├── worker.py
    │   └── helpers.py
    ├── rag.py                      <-- RAG Orchestrator
    ├── learning.py                 <-- RAG Notebook Generator
    ├── session.py                  <-- Quản lý Session
    └── export.py                   <-- Xuất Notebook ra PDF/Markdown
`

## 17. Tech Stack Đề Xuất (Native Local Edition)

| Thành phần          | Công nghệ                        | Ghi chú                                               |
| ------------------- | -------------------------------- | ----------------------------------------------------- |
| Universal Parser    | Microsoft MarkItDown             | Thay thế hoàn toàn PDF, DOCX, PPTX, XLSX, HTML parser |
| Markdown Parser     | mistletoe / markdown-it-py       | Phân tích Markdown thành Document Tree AST            |
| YouTube Transcript  | youtube-transcript-api           |                                                       |
| ASR (Audio)         | Whisper (small/base/medium)      | Local inference, chỉ tải On-Demand qua Web UI         |
| **Unified LLM ★**   | **Qwen 2.5 + llama.cpp**         | ✅ **Offload VRAM tự động, tối ưu cực tốt trên C++**  |
| **Vision Model**    | **Moondream2 / OCR / Qwen2-VL**  | Tự động cảnh báo và giới hạn dựa trên dung lượng VRAM |
| Embedding + Sparse  | GreenNode / sBERT                | Lựa chọn động qua Terminal để chống tràn RAM/VRAM     |
| Vector Database     | Qdrant Local (File-based)        | Chạy trực tiếp qua Python, **không cần Docker**       |
| Reranker            | BGE-M3 / mMiniLMv2               | Lựa chọn động qua Terminal để chống tràn RAM/VRAM     |
| API Framework       | FastAPI                          |                                                       |
| Frontend            | React + Vite                     | Cung cấp giao diện trực quan tại localhost:5173       |

### Khởi động Hệ Thống (Không Docker)

Thay vì phải cài đặt Docker cồng kềnh, hệ thống sử dụng cơ chế **Native Venv**:
1. Người dùng chạy `run.bat` (Windows) hoặc `run_mac.command` (Mac).
2. `hardware_profiler.py` tự động quét RAM/VRAM và tạo Menu cho phép người dùng chọn mô hình (LLM, Embedding, Reranker).
3. `launcher.py` tự động tạo Virtual Environment, cài đặt thư viện PyTorch (CPU hoặc CUDA tùy máy) và bật máy chủ Web + LLM.

---

## Tổng Kết — Nguyên Tắc Thiết Kế Mới

1. **Extractor chỉ trích xuất sự thật (facts).** Layout Parser mới suy luận ý nghĩa (semantics).
2. **Document Tree là định dạng nội bộ quan trọng nhất.** Markdown chỉ là export format để giao tiếp với LLM.
3. **Bảo vệ RAM/VRAM tuyệt đối.** Các mô hình nặng (Ảnh/Âm thanh) sẽ không bao giờ được tải ngầm. Chúng chỉ được kích hoạt (On-Demand) khi người dùng upload file tương ứng, và sẽ bị chặn lại nếu phần cứng không đủ đáp ứng.
4. **Không Docker, Không Ảo Hóa.** Mọi thứ chạy Native trên Python và C++ để vắt kiệt 100% hiệu năng của phần cứng cá nhân.

---

## 18. Đánh Giá Kiến Trúc Tổng Thể (Pros & Cons)

Sự chuyển dịch từ kiến trúc Docker/Ollama sang kiến trúc **Native Local (llama.cpp + FastAPI + File-based Qdrant)** là một bước tiến mang tính cách mạng cho dự án NotebookLM Mini.

### Ưu Điểm (Pros)
1. **Khả năng tiếp cận vô song (Plug & Play):** Việc loại bỏ Docker giúp bất kỳ ai (dù không rành IT) cũng có thể nhấp đúp file `.bat` để chạy phần mềm. 
2. **Bảo mật tuyệt đối (100% Offline/Airgapped):** Toàn bộ dữ liệu nằm trên ổ cứng người dùng.
3. **Tối ưu Phần Cứng Cực Hạn:** `llama.cpp` cho phép chạy các mô hình lớn (như Qwen 14B) ngay cả khi VRAM rất nhỏ (bằng cách offload sang RAM thường). Cơ chế kiểm soát VRAM tự động hạ cấp các mô hình vệ tinh (Embedding/Reranker) xuống CPU giúp tránh crash hệ thống.
4. **On-Demand Loading:** Xử lý Đa phương thức (Multimodal) khôn ngoan bằng cách chỉ nạp mô hình Vision/Audio khi có tín hiệu từ người dùng.

### Nhược Điểm & Thách Thức (Cons & Limitations)
1. **Phụ thuộc vào Internet ở lần chạy đầu:** Quá trình tải các file model `.gguf` (khoảng 3GB-10GB) tốn nhiều băng thông.
2. **Xử lý Ingestion Chậm trên Máy Yếu:** Chuyển văn bản thành Vector (Embedding) và trích xuất Âm thanh (Whisper) bằng CPU sẽ khá chậm so với GPU.
3. **Bảo trì Web/YouTube Parser:** Các trang web và YouTube thường xuyên thay đổi cấu trúc HTML hoặc cơ chế chống bot.

**Kết luận:** Bản thiết kế này đã phá bỏ rào cản của những hệ thống AI cồng kềnh, mang lại trải nghiệm **RAG đa phương thức cấp doanh nghiệp** gói gọn trong một chiếc Laptop cá nhân yếu ớt.
