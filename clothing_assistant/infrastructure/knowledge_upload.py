"""Pure knowledge-upload validation helpers with no Streamlit dependency."""

from collections import Counter
import hashlib

from clothing_assistant.config_data import KNOWLEDGE_FILES


EXPECTED_FILE_NAMES = set(KNOWLEDGE_FILES)


def validate_uploaded_files(uploaded_files):
    """Validate that an upload has exactly the configured knowledge file names.

    Args:
        uploaded_files: Objects exposing a ``name`` attribute, such as Streamlit uploads.

    Returns:
        User-facing validation errors; an empty list means the upload is valid.
    """
    uploaded_names = [uploaded_file.name for uploaded_file in uploaded_files]
    name_counter = Counter(uploaded_names)
    duplicate_names = sorted(file_name for file_name, count in name_counter.items() if count > 1)
    uploaded_name_set = set(uploaded_names)
    missing_names = sorted(EXPECTED_FILE_NAMES - uploaded_name_set)
    unexpected_names = sorted(uploaded_name_set - EXPECTED_FILE_NAMES)
    error_messages = []

    if len(uploaded_files) != len(KNOWLEDGE_FILES):
        error_messages.append(
            f"必须上传 {len(KNOWLEDGE_FILES)} 个文件，当前上传了 {len(uploaded_files)} 个。"
        )

    if duplicate_names:
        error_messages.append(f"发现重复文件：{', '.join(duplicate_names)}")

    if missing_names:
        error_messages.append(f"缺少文件：{', '.join(missing_names)}")

    if unexpected_names:
        error_messages.append(f"存在未约定的文件：{', '.join(unexpected_names)}")

    return error_messages


def calculate_file_md5(file_bytes):
    """Return a content hash used only to skip unchanged local uploads.

    Args:
        file_bytes: Raw uploaded file bytes.

    Returns:
        The MD5 digest for change detection, not for security verification.
    """
    return hashlib.md5(file_bytes).hexdigest()


def compare_uploaded_files(file_snapshots, hash_record):
    """Split uploaded files into changed and unchanged sets by content hash.

    Args:
        file_snapshots: Upload dictionaries containing ``name`` and ``md5``.
        hash_record: Previously persisted file-name to hash mapping.

    Returns:
        Changed names, unchanged names, and the updated hash mapping.
    """
    changed_files = []
    unchanged_files = []
    updated_hash_record = hash_record.copy()

    for snapshot in file_snapshots:
        file_name = snapshot["name"]
        old_md5 = hash_record.get(file_name)
        new_md5 = snapshot["md5"]

        if old_md5 == new_md5:
            unchanged_files.append(file_name)
        else:
            changed_files.append(file_name)
            updated_hash_record[file_name] = new_md5

    return changed_files, unchanged_files, updated_hash_record
