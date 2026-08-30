"""
Unit tests for attachment processor.
Tests text extraction from PDFs, Word docs, and Excel files.
"""

import pytest
from pathlib import Path

from processors.attachment_processor import AttachmentProcessor
from models.email_data import EmailAttachment


@pytest.fixture
def attachment_processor():
    """Create an attachment processor instance."""
    return AttachmentProcessor()


@pytest.fixture
def sample_pdf_attachment(tmp_path):
    """Create a sample PDF attachment (mock)."""
    # Note: In real tests, you'd create actual PDF files
    # For now, this is a placeholder
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"fake pdf content")

    return EmailAttachment(
        filename="test.pdf",
        mime_type="application/pdf",
        size_bytes=100,
        attachment_id="att_pdf",
        local_path=str(pdf_path)
    )


@pytest.fixture
def sample_word_attachment(tmp_path):
    """Create a sample Word attachment (mock)."""
    docx_path = tmp_path / "test.docx"
    docx_path.write_bytes(b"fake docx content")

    return EmailAttachment(
        filename="test.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=100,
        attachment_id="att_docx",
        local_path=str(docx_path)
    )


@pytest.fixture
def sample_image_attachment(tmp_path):
    """Create a sample image attachment."""
    image_path = tmp_path / "test.jpg"
    image_path.write_bytes(b"fake image data")

    return EmailAttachment(
        filename="test.jpg",
        mime_type="image/jpeg",
        size_bytes=100,
        attachment_id="att_img",
        local_path=str(image_path)
    )


def test_process_all_attachments_images_only(attachment_processor, sample_image_attachment):
    """Test processing attachments with only images."""
    result = attachment_processor.process_all_attachments([sample_image_attachment])

    # Images should be separated, not in combined text
    assert len(result["images"]) == 1
    assert result["images"][0].filename == "test.jpg"
    assert result["combined_text"] == ""
    assert len(result["unsupported"]) == 0


def test_process_all_attachments_unsupported(attachment_processor, tmp_path):
    """Test processing unsupported attachment types."""
    # Create an unsupported file type
    unsupported_path = tmp_path / "test.dwg"
    unsupported_path.write_bytes(b"fake dwg data")

    attachment = EmailAttachment(
        filename="test.dwg",
        mime_type="application/acad",
        size_bytes=100,
        attachment_id="att_dwg",
        local_path=str(unsupported_path)
    )

    result = attachment_processor.process_all_attachments([attachment])

    # Should be marked as unsupported
    assert len(result["unsupported"]) == 1
    assert "test.dwg" in result["unsupported"]
    assert result["combined_text"] == ""


def test_process_all_attachments_mixed(
    attachment_processor,
    sample_image_attachment,
    tmp_path
):
    """Test processing mix of attachment types."""
    # Create a CSV attachment
    csv_path = tmp_path / "test.csv"
    csv_path.write_text("Name,Value\nTest,123")

    csv_attachment = EmailAttachment(
        filename="test.csv",
        mime_type="text/csv",
        size_bytes=50,
        attachment_id="att_csv",
        local_path=str(csv_path)
    )

    result = attachment_processor.process_all_attachments([
        sample_image_attachment,
        csv_attachment
    ])

    # Image should be separated
    assert len(result["images"]) == 1

    # CSV text should be extracted
    assert "test.csv" in result["combined_text"]
    assert "Test" in result["combined_text"]


def test_format_table_as_markdown(attachment_processor):
    """Test formatting table data as markdown."""
    table_data = [
        ["Name", "Age", "City"],
        ["Alice", "30", "London"],
        ["Bob", "25", "Paris"]
    ]

    markdown = attachment_processor._format_table_as_markdown(table_data)

    # Check markdown structure
    assert "| Name | Age | City |" in markdown
    assert "| --- | --- | --- |" in markdown
    assert "| Alice | 30 | London |" in markdown


def test_format_table_as_markdown_empty(attachment_processor):
    """Test formatting empty table."""
    markdown = attachment_processor._format_table_as_markdown([])
    assert markdown == ""


def test_format_table_as_markdown_truncation(attachment_processor):
    """Test that large tables are truncated."""
    # Create table with 30 rows
    table_data = [["Header"]] + [[f"Row {i}"] for i in range(30)]

    markdown = attachment_processor._format_table_as_markdown(table_data)

    # Should indicate truncation
    assert "more rows" in markdown


def test_process_attachments_no_local_path(attachment_processor):
    """Test handling attachments without local_path."""
    attachment = EmailAttachment(
        filename="test.pdf",
        mime_type="application/pdf",
        size_bytes=100,
        attachment_id="att_123",
        local_path=None  # No local path
    )

    result = attachment_processor.process_all_attachments([attachment])

    # Should handle gracefully
    assert result["combined_text"] == ""
    assert len(result["images"]) == 0


def test_process_attachments_file_not_found(attachment_processor):
    """Test handling attachments where file doesn't exist."""
    attachment = EmailAttachment(
        filename="nonexistent.pdf",
        mime_type="application/pdf",
        size_bytes=100,
        attachment_id="att_123",
        local_path="/nonexistent/path/file.pdf"
    )

    result = attachment_processor.process_all_attachments([attachment])

    # Should be marked as unsupported due to error
    assert "nonexistent.pdf" in result["unsupported"]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
