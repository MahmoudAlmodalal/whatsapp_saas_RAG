from docx import Document

def docx_to_markdown(file_path: str) -> str:
    doc = Document(file_path)
    lines = []
    for para in doc.paragraphs:
        if not para.text.strip():
            continue
        if para.style.name.startswith("Heading"):
            try:
                level = int(para.style.name.split()[-1])
            except (ValueError, IndexError):
                level = 1
            lines.append(f"{'#' * level} {para.text}")
        else:
            lines.append(para.text)
    return "\n\n".join(lines)
