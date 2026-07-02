$files_to_delete = @(
    'test_doc.md',
    'test_notebooks.json',
    'test_omega.pdf',
    'implementation_plan.md',
    'notebook_sessions.db',
    'scratch/document_tree_output.json',
    'scratch/document_tree_output_1.json',
    'scratch/document_tree_output_2.json',
    'scratch/document_tree_output_3.json',
    'scratch/raw_03_Ketoan_output.md',
    'test_data/~$_Ketoan.docx',
    'test_data/test_doc_1.md',
    'test_data/test_doc_2.csv',
    'test_data/test_doc_3.png',
    'test_data/test_doc_4.wav',
    'test_data/test_doc_5.pdf',
    'test_data/test_md.py',
    'test_data/demo.docx',
    'test_data/demo.md',
    'tests/ragbench_hotpotqa_20260625_024950.csv',
    'tests/ragbench_hotpotqa_20260625_025829.csv',
    'test_data/ragbench/hotpotqa_raw.jsonl',
    'test_data/ragbench/pubmedqa.json',
    'test_data/ragbench/msmarco.json',
    'test_data/ragbench/hotpotqa.json'
)

foreach ($f in $files_to_delete) {
    if (Test-Path $f) {
        Remove-Item -Force $f
        Write-Host "Deleted $f"
    }
}

git add -A
git commit -m "clear file"
git push origin main
