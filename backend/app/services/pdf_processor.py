# app/services/pdf_processor.py
import pdfplumber
import re
from typing import List, Dict

class PDFProcessor:
    def __init__(self, chunk_size: int = 600, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def extract_text(self, file_path: str) -> str:
        """Extracts text from a PDF file."""
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return self.clean_text(text)

    def clean_text(self, text: str) -> str:
        """Basic text cleaning."""
        # Remove multiple newlines
        text = re.sub(r'\n+', '\n', text)
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def create_chunks(self, text: str, meta: Dict) -> List[Dict]:
        """Splits text into overlapping chunks with metadata."""
        words = text.split()
        chunks = []
        filename = meta.get("source", "Unknown")

        for i in range(0, len(words), self.chunk_size - self.overlap):
            chunk_words = words[i : i + self.chunk_size]
            chunk_text = " ".join(chunk_words)
            
            # Skip chunks that are too small (e.g., footer noise)
            if len(chunk_words) < 50:
                continue
            
            enhanced_chunk = f"Source Document: {filename}\nSection: Policy Details\nContent: {chunk_text}"

            chunks.append({
                "text": enhanced_chunk,
                "metadata": {
                    **meta,
                    "chunk_index": len(chunks),
                    "word_count": len(chunk_words)
                }
            })
            
            # Stop if we've reached the end
            if i + self.chunk_size >= len(words):
                break
                
        return chunks