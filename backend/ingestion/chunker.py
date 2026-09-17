import re
from typing import List, Dict, Any

class DocumentChunker:
    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text_into_chunks(self, text: str, page_number: int = 1) -> List[Dict[str, Any]]:
        """
        Splits text into overlapping semantic chunks, preserving sections and headers.
        """
        clean_text = text.strip()
        if not clean_text:
            return []

        # Split on double newlines (paragraphs) first
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", clean_text) if p.strip()]
        chunks = []
        current_chunk_text = ""
        current_section = None
        chunk_idx = 0

        for para in paragraphs:
            # Check if paragraph looks like a section header (e.g. "Section 4. Customer Due Diligence", "Chapter II - General")
            if re.match(r"^(Chapter|Section|Clause|Part|Article|\d+\.|\b[A-Z\s]{4,}\b)", para) and len(para) < 120:
                current_section = para.split("\n")[0].strip()

            if len(current_chunk_text) + len(para) <= self.chunk_size:
                if current_chunk_text:
                    current_chunk_text += "\n\n" + para
                else:
                    current_chunk_text = para
            else:
                if current_chunk_text:
                    chunks.append({
                        "chunk_index": chunk_idx,
                        "page_number": page_number,
                        "section": current_section or f"Page {page_number}",
                        "chunk_text": current_chunk_text.strip()
                    })
                    chunk_idx += 1
                    # Keep overlap from previous text
                    words = current_chunk_text.split()
                    overlap_words = words[-max(1, self.chunk_overlap // 6):]
                    current_chunk_text = " ".join(overlap_words) + "\n\n" + para
                else:
                    # Single paragraph exceeds chunk size, split by sentences
                    sentences = re.split(r"(?<=[.?!])\s+", para)
                    temp_chunk = ""
                    for s in sentences:
                        if len(temp_chunk) + len(s) <= self.chunk_size:
                            temp_chunk += " " + s if temp_chunk else s
                        else:
                            if temp_chunk:
                                chunks.append({
                                    "chunk_index": chunk_idx,
                                    "page_number": page_number,
                                    "section": current_section or f"Page {page_number}",
                                    "chunk_text": temp_chunk.strip()
                                })
                                chunk_idx += 1
                            temp_chunk = s
                    if temp_chunk:
                        current_chunk_text = temp_chunk.strip()

        if current_chunk_text.strip():
            chunks.append({
                "chunk_index": chunk_idx,
                "page_number": page_number,
                "section": current_section or f"Page {page_number}",
                "chunk_text": current_chunk_text.strip()
            })

        return chunks

    def chunk_document_pages(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Chunks all pages of a document and assigns overall chunk indices."""
        all_chunks = []
        overall_index = 0
        for p in pages:
            page_num = p.get("page_number", 1)
            page_text = p.get("text", "")
            page_chunks = self.split_text_into_chunks(page_text, page_number=page_num)
            for c in page_chunks:
                c["chunk_index"] = overall_index
                all_chunks.append(c)
                overall_index += 1
        return all_chunks

document_chunker = DocumentChunker()
