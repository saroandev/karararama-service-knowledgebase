import io
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib

import pymupdf
from pymupdf import Document

logger = logging.getLogger(__name__)


@dataclass
class PageContent:
    """Data class for page content"""
    page_number: int
    text: str
    metadata: Dict[str, Any]


@dataclass
class DocumentMetadata:
    """Data class for document metadata"""
    title: Optional[str]
    author: Optional[str]
    subject: Optional[str]
    keywords: Optional[str]
    creator: Optional[str]
    producer: Optional[str]
    creation_date: Optional[str]
    modification_date: Optional[str]
    page_count: int
    file_size: int
    document_hash: str


class PDFParser:
    def __init__(self):
        self.supported_formats = ['.pdf']
    
    def extract_text_from_pdf(self, file_data: bytes) -> Tuple[List[PageContent], DocumentMetadata]:
        """
        Extract text and metadata from PDF
        
        Args:
            file_data: PDF file bytes
        
        Returns:
            Tuple of (list of PageContent, DocumentMetadata)
        """
        pages = []
        
        try:
            # Open PDF from bytes
            pdf_stream = io.BytesIO(file_data)
            doc: Document = pymupdf.open(stream=pdf_stream, filetype="pdf")
            
            # Extract metadata
            metadata = self._extract_metadata(doc, file_data)
            
            # Extract text from each page
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Extract text
                text = page.get_text("text")
                
                # Clean text
                text = self._clean_text(text)
                
                # Skip empty pages
                if not text.strip():
                    continue
                
                # Extract additional page metadata
                page_metadata = {
                    "page_number": page_num + 1,
                    "width": page.rect.width,
                    "height": page.rect.height,
                    "rotation": page.rotation,
                    "has_images": len(page.get_images()) > 0,
                    "has_links": len(page.get_links()) > 0,
                    "char_count": len(text),
                    "word_count": len(text.split())
                }
                
                # Check for tables
                tables = self._detect_tables(page)
                if tables:
                    page_metadata["has_tables"] = True
                    page_metadata["table_count"] = len(tables)
                
                pages.append(PageContent(
                    page_number=page_num + 1,
                    text=text,
                    metadata=page_metadata
                ))
            
            doc.close()
            
            logger.info(f"Extracted {len(pages)} pages from PDF")
            return pages, metadata
            
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            raise
    
    def _extract_metadata(self, doc: Document, file_data: bytes) -> DocumentMetadata:
        """Extract document metadata"""
        meta = doc.metadata
        
        # Calculate document hash
        doc_hash = hashlib.sha256(file_data).hexdigest()
        
        # Format dates
        creation_date = None
        modification_date = None
        
        if meta.get("creationDate"):
            try:
                creation_date = self._parse_pdf_date(meta["creationDate"])
            except:
                creation_date = meta.get("creationDate")
        
        if meta.get("modDate"):
            try:
                modification_date = self._parse_pdf_date(meta["modDate"])
            except:
                modification_date = meta.get("modDate")
        
        return DocumentMetadata(
            title=meta.get("title", "").strip() or None,
            author=meta.get("author", "").strip() or None,
            subject=meta.get("subject", "").strip() or None,
            keywords=meta.get("keywords", "").strip() or None,
            creator=meta.get("creator", "").strip() or None,
            producer=meta.get("producer", "").strip() or None,
            creation_date=creation_date,
            modification_date=modification_date,
            page_count=len(doc),
            file_size=len(file_data),
            document_hash=doc_hash
        )
    
    def _parse_pdf_date(self, date_str: str) -> str:
        """Parse PDF date string to ISO format"""
        # PDF date format: D:YYYYMMDDHHmmSS
        if date_str.startswith("D:"):
            date_str = date_str[2:]
        
        try:
            # Parse basic format
            year = int(date_str[0:4])
            month = int(date_str[4:6]) if len(date_str) > 4 else 1
            day = int(date_str[6:8]) if len(date_str) > 6 else 1
            hour = int(date_str[8:10]) if len(date_str) > 8 else 0
            minute = int(date_str[10:12]) if len(date_str) > 10 else 0
            second = int(date_str[12:14]) if len(date_str) > 12 else 0
            
            dt = datetime(year, month, day, hour, minute, second)
            return dt.isoformat()
        except:
            return date_str
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text"""
        # Remove excessive whitespace
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Remove leading/trailing whitespace
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Replace multiple spaces with single space
            line = ' '.join(line.split())
            
            cleaned_lines.append(line)
        
        # Join with single newline
        cleaned_text = '\n'.join(cleaned_lines)
        
        # Remove control characters (except newlines and tabs)
        cleaned_text = ''.join(
            char for char in cleaned_text 
            if char == '\n' or char == '\t' or (ord(char) >= 32 and ord(char) <= 126) or ord(char) > 127
        )
        
        return cleaned_text
    
    def _detect_tables(self, page) -> List[Dict[str, Any]]:
        """Detect tables in a page (basic detection)"""
        tables = []
        
        try:
            # PyMuPDF table detection (if available)
            # This is a simplified approach - more sophisticated methods exist
            tabs = page.find_tables()
            if tabs:
                for i, tab in enumerate(tabs):
                    tables.append({
                        "index": i,
                        "bbox": tab.bbox,
                        "rows": tab.row_count,
                        "cols": tab.col_count
                    })
        except:
            # Fallback: look for patterns that suggest tables
            pass
        
        return tables
    
    def extract_text_with_layout(self, file_data: bytes) -> List[PageContent]:
        """
        Extract text while preserving layout information
        
        Args:
            file_data: PDF file bytes
        
        Returns:
            List of PageContent with layout preserved
        """
        pages = []
        
        try:
            pdf_stream = io.BytesIO(file_data)
            doc: Document = pymupdf.open(stream=pdf_stream, filetype="pdf")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Extract text with layout
                blocks = page.get_text("dict")
                
                # Process blocks to preserve structure
                structured_text = self._process_blocks(blocks)
                
                if structured_text.strip():
                    pages.append(PageContent(
                        page_number=page_num + 1,
                        text=structured_text,
                        metadata={
                            "page_number": page_num + 1,
                            "extraction_method": "layout_preserved"
                        }
                    ))
            
            doc.close()
            return pages
            
        except Exception as e:
            logger.error(f"Error extracting text with layout: {e}")
            raise
    
    def _process_blocks(self, blocks: Dict[str, Any]) -> str:
        """Process text blocks to preserve structure"""
        text_parts = []
        
        for block in blocks.get("blocks", []):
            if block.get("type") == 0:  # Text block
                block_text = []
                for line in block.get("lines", []):
                    line_text = []
                    for span in line.get("spans", []):
                        line_text.append(span.get("text", ""))
                    
                    if line_text:
                        block_text.append("".join(line_text))
                
                if block_text:
                    text_parts.append("\n".join(block_text))
        
        return "\n\n".join(text_parts)
    
    def extract_images(self, file_data: bytes) -> List[Dict[str, Any]]:
        """
        Extract images from PDF
        
        Args:
            file_data: PDF file bytes
        
        Returns:
            List of image metadata
        """
        images = []
        
        try:
            pdf_stream = io.BytesIO(file_data)
            doc: Document = pymupdf.open(stream=pdf_stream, filetype="pdf")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    images.append({
                        "page_number": page_num + 1,
                        "image_index": img_index,
                        "xref": img[0],
                        "width": img[2],
                        "height": img[3],
                        "colorspace": img[4],
                        "bits": img[5]
                    })
            
            doc.close()
            logger.info(f"Found {len(images)} images in PDF")
            return images
            
        except Exception as e:
            logger.error(f"Error extracting images: {e}")
            return []


# Singleton instance
pdf_parser = PDFParser()