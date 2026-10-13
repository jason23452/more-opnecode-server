import pytest

from opencode_project.clipboard import (
    MAX_CLIPBOARD_FILE_BYTES,
    MAX_CLIPBOARD_IMAGE_BYTES,
    _clipboard_files_from_paths,
    _decode_base64_path_lines,
    _parse_uri_list,
    _validated_image,
)


@pytest.mark.parametrize(
    ("mime_type", "data"),
    [
        ("image/png", b"\x89PNG\r\n\x1a\nimage"),
        ("image/jpeg", b"\xff\xd8\xffimage"),
        ("image/webp", b"RIFF\x04\x00\x00\x00WEBPimage"),
        ("image/gif", b"GIF89aimage"),
    ],
)
def test_validated_image_accepts_supported_mime_types(mime_type: str, data: bytes) -> None:
    image = _validated_image(mime_type, data)

    assert image is not None
    assert image.mime_type == mime_type
    assert image.data == data


def test_validated_image_rejects_unknown_mime_malformed_data_and_oversize_payload() -> None:
    assert _validated_image("text/plain", b"hello") is None
    assert _validated_image("image/png", b"not-png") is None
    assert _validated_image("image/png", b"\x89PNG\r\n\x1a\n" + b"x" * MAX_CLIPBOARD_IMAGE_BYTES) is None


def test_uri_list_parses_multiple_file_urls_and_ignores_comments_and_other_schemes() -> None:
    paths = _parse_uri_list(
        "# copied files\r\nfile:///tmp/first%20file.txt\r\nhttps://example.test/file.txt\r\n"
        "file:///tmp/second.png\r\n"
    )

    assert paths == ["/tmp/first file.txt", "/tmp/second.png"]


def test_base64_path_list_decodes_unicode_windows_file_paths() -> None:
    import base64

    encoded = base64.b64encode("C:\\Users\\User\\Pictures\\截圖.png".encode()).decode()

    assert _decode_base64_path_lines(encoded + "\r\ninvalid!") == ["C:\\Users\\User\\Pictures\\截圖.png"]


def test_file_clipboard_reads_multiple_regular_files_and_skips_oversize_and_directories(tmp_path) -> None:
    first = tmp_path / "notes.txt"
    first.write_text("hello", encoding="utf-8")
    oversized = tmp_path / "large.bin"
    oversized.write_bytes(b"x" * (MAX_CLIPBOARD_FILE_BYTES + 1))
    folder = tmp_path / "folder"
    folder.mkdir()

    files = _clipboard_files_from_paths([str(first), str(oversized), str(folder)])

    assert [(item.name, item.mime_type, item.data) for item in files] == [
        ("notes.txt", "text/plain", b"hello"),
    ]
