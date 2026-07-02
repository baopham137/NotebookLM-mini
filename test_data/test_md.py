import urllib.request
from markitdown import MarkItDown

urllib.request.urlretrieve('https://calibre-ebook.com/downloads/demos/demo.docx', 'd:/LLM_mini/test_data/demo.docx')
md = MarkItDown()
with open('d:/LLM_mini/test_data/demo.md', 'w', encoding='utf-8') as f:
    f.write(md.convert('d:/LLM_mini/test_data/demo.docx').text_content)
