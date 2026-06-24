import os
import sys
import json

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import MarkItDownParser
from src.ingestion.parsers.markitdown_parser import MarkItDownParser

def main():
    # Đầu vào 1: Đường dẫn file
    file_path = os.path.join(project_root, "test_data", "03_Ketoan.docx")
    
    print(f"1. Khởi tạo MarkItDownParser")
    parser = MarkItDownParser()
    
    print(f"2. Thực hiện parse() TRƯỚC, gán metadata SAU (giống trong api.py hiện tại)")
    # KHÔNG truyền metadata vào lúc parse
    tree = parser.parse(file_path)
    
    # SAU KHI parse xong mới gán notebook_id vào cây
    tree.metadata["notebook_id"] = "nb_fake_123"
    tree.metadata["uploader"] = "test_user"
    
    print("\n3. ĐÂY LÀ KẾT QUẢ OUTPUT TREE (to_dict):")
    print("="*60)
    # In thẳng ra JSON để bạn thấy rõ từng Node, từng Children nó chia như thế nào
    json_str = json.dumps(tree.to_dict(), indent=2, ensure_ascii=False)
    print(json_str[:1500] + "\n... [Đã cắt bớt để không tràn màn hình] ...")
    print("="*60)
    
    # Lưu ra file để dễ nhìn toàn bộ
    output_path = os.path.join(project_root, "scratch", "document_tree_output_3.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json_str)
        
    print(f"\n✅ Đã lưu toàn bộ kết quả JSON vào file: {output_path}")

if __name__ == "__main__":
    main()
