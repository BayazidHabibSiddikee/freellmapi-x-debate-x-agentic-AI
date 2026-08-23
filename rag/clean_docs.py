#!/usr/bin/env python3
# clean_docs.py — removes PDFs that PyPDFLoader can't load (unsuitable for FAISS)

import os
from langchain_community.document_loaders import PyPDFLoader

DOC_DIR = "doc"

def is_bad_pdf(path):
    try:
        pages = PyPDFLoader(path).load()
        if not pages or all(p.page_content.strip() == "" for p in pages):
            return "empty or no extractable text"
        return None
    except Exception as e:
        return str(e)

def clean():
    if not os.path.exists(DOC_DIR):
        print(f"[!] Directory '{DOC_DIR}' not found.")
        return

    pdfs = [f for f in os.listdir(DOC_DIR) if f.lower().endswith(".pdf")]
    if not pdfs:
        print("[!] No PDFs found.")
        return

    print(f"[*] Scanning {len(pdfs)} PDFs in '{DOC_DIR}'...\n")

    bad, good = [], []

    for pdf in pdfs:
        path = os.path.join(DOC_DIR, pdf)
        reason = is_bad_pdf(path)
        if reason:
            bad.append((pdf, reason))
            print(f"  [BAD]  {pdf} — {reason}")
        else:
            good.append(pdf)
            print(f"  [OK]   {pdf}")

    print(f"\n[*] Results: {len(good)} good, {len(bad)} bad")

    if not bad:
        print("[✓] Nothing to remove.")
        return

    print("\nFiles to remove:")
    for pdf, reason in bad:
        print(f"  - {pdf} ({reason})")

    confirm = input("\nDelete these files? [y/N]: ").strip().lower()
    if confirm == "y":
        for pdf, _ in bad:
            os.remove(os.path.join(DOC_DIR, pdf))
            print(f"  [deleted] {pdf}")
        print(f"\n[✓] Removed {len(bad)} bad PDFs.")
    else:
        print("[!] Aborted. Nothing deleted.")

if __name__ == "__main__":
    clean()
