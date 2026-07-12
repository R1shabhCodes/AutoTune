# extract_pdf.py
# Helper script to convert downloaded PDFs into clean text files for your corpus.

import os
import sys
import glob

try:
    import pdfplumber
except ImportError:
    print("pdfplumber is required. Installing it now...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pdfplumber"])
    import pdfplumber

def convert_pdf_to_txt(pdf_path: str, txt_path_list: list):
    print(f"Extracting text from {os.path.basename(pdf_path)}...")
    with pdfplumber.open(pdf_path) as pdf:
        text_content = []
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                text_content.append(f"--- Page {i+1} ---\n{text}\n")
    
    full_text = "\n".join(text_content)
    for txt_path in txt_path_list:
        os.makedirs(os.path.dirname(txt_path), exist_ok=True)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        print(f"Saved text to {txt_path} ({os.path.getsize(txt_path) / 1024:.1f} KB)")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(script_dir))
    budget_dir = os.path.join(root_dir, "Budget")
    
    if not os.path.exists(budget_dir):
        print(f"Budget directory not found: {budget_dir}")
        return

    pdf_files = glob.glob(os.path.join(budget_dir, "*.pdf"))
    if not pdf_files:
        print(f"No .pdf files found in directory: {budget_dir}")
        return

    # Define the two output directories we need to sync to
    app_doc_dir = os.path.join(script_dir, "documents")
    engine_corp_dir = os.path.join(root_dir, "engine", "corpus")

    for pdf_path in pdf_files:
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        txt_filename = base_name.lower().replace(" ", "_") + ".txt"
        
        target_paths = [
            os.path.join(app_doc_dir, txt_filename),
            os.path.join(engine_corp_dir, txt_filename)
        ]
        convert_pdf_to_txt(pdf_path, target_paths)

if __name__ == "__main__":
    main()
