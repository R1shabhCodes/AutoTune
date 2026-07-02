# extract_pdf.py
# Helper script to convert downloaded PDFs into clean text files for your corpus.
# Install pdfplumber first: pip install pdfplumber

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

def convert_pdf_to_txt(pdf_path: str, txt_path: str):
    print(f"Extracting text from {os.path.basename(pdf_path)}...")
    with pdfplumber.open(pdf_path) as pdf:
        text_content = []
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                text_content.append(f"--- Page {i+1} ---\n{text}\n")
    
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(text_content))
    print(f"Saved text to {txt_path} ({os.path.getsize(txt_path) / 1024:.1f} KB)")

def main():
    # Look for any PDFs in the current directory
    pdf_files = glob.glob("*.pdf")
    if not pdf_files:
        print("No .pdf files found in the current directory.")
        print("Place your downloaded PDFs in D:\\RAG-Finance\\ and run this script again.")
        return

    os.makedirs("corpus", exist_ok=True)
    for pdf in pdf_files:
        txt_name = os.path.splitext(pdf)[0] + ".txt"
        txt_path = os.path.join("corpus", txt_name)
        convert_pdf_to_txt(pdf, txt_path)

if __name__ == "__main__":
    main()
