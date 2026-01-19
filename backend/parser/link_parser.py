"""Парсинг DOCX и PDF файлов"""
from typing import Tuple, Optional
import requests
from docx import Document as DocxDocument
from PyPDF2 import PdfReader
from io import BytesIO


def download_file(url: str, timeout: int = 30) -> Tuple[Optional[bytes], str]:
    """Скачать файл по URL"""
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.content, ''
    except Exception as e:
        return None, str(e)


def parse_docx(content: bytes) -> Tuple[Optional[str], Optional[dict], str]:
    """Парсинг DOCX файла"""
    try:
        doc = DocxDocument(BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = '\n'.join(paragraphs)
        stats = {
            'format': 'docx',
            'paragraphs': len(paragraphs),
            'text_length': len(text)
        }
        return text, stats, ''
    except Exception as e:
        return None, None, str(e)


def parse_pdf(content: bytes) -> Tuple[Optional[str], Optional[dict], str]:
    """Парсинг PDF файла"""
    try:
        reader = PdfReader(BytesIO(content))
        pages_text = []
        for page in reader.pages:
            pages_text.append(page.extract_text())
        text = '\n'.join(pages_text)
        stats = {
            'format': 'pdf',
            'pages': len(reader.pages),
            'text_length': len(text)
        }
        return text, stats, ''
    except Exception as e:
        return None, None, str(e)
