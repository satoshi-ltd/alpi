import errno
import os
import subprocess
import sys
from pathlib import Path
from stat import S_IMODE
from types import SimpleNamespace

import pytest

from alpi.tools import _mutations, edit_file
from alpi.tools.edit_file import EditFile


def test_edit_preserves_mode_without_a_backup(tmp_path: Path) -> None:
    target = tmp_path / "script.sh"
    target.write_text("echo before\n")
    target.chmod(0o710)
    mode = S_IMODE(target.stat().st_mode)

    result = EditFile().run(str(target), "before", "after")

    assert result.ok
    assert target.read_text() == "echo after\n"
    assert S_IMODE(target.stat().st_mode) == mode
    assert list(tmp_path.iterdir()) == [target]


def test_failed_edit_write_keeps_original_and_records_no_mutation(tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    original = b"before\n"
    target.write_bytes(original)
    token = _mutations.begin_batch()
    try:
        result = EditFile().run(str(target), "before", "\ud800")
    finally:
        records = _mutations.end_batch(token)

    assert not result.ok and "encoding" in result.error
    assert target.read_bytes() == original
    assert list(tmp_path.iterdir()) == [target]
    assert records == []


def test_failed_replacement_keeps_original_and_cleans_up(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "note.txt"
    original = b"before\n"
    target.write_bytes(original)
    target.chmod(0o640)
    mode = S_IMODE(target.stat().st_mode)

    def refuse_replacement(source: Path, dest: Path) -> None:
        assert source.parent == dest.parent == target.parent
        assert source.read_bytes() == b"after\n"
        assert dest == target
        assert target.read_bytes() == original
        raise OSError(errno.EIO, "replacement failed")

    monkeypatch.setattr(edit_file.os, "replace", refuse_replacement)
    token = _mutations.begin_batch()
    try:
        result = EditFile().run(str(target), "before", "after")
    finally:
        records = _mutations.end_batch(token)

    assert not result.ok
    assert "Cannot write" in result.error
    assert target.read_bytes() == original
    assert S_IMODE(target.stat().st_mode) == mode
    assert list(tmp_path.iterdir()) == [target]
    assert records == []


def _run_recorded(target: Path, old: str, new: str):
    token = _mutations.begin_batch()
    try:
        result = EditFile().run(str(target), old, new)
    finally:
        records = _mutations.end_batch(token)
    return result, records


@pytest.mark.parametrize("code", [errno.EBUSY, errno.EXDEV, errno.EACCES, errno.EPERM])
def test_a_target_that_cannot_be_replaced_is_edited_in_place(tmp_path: Path, monkeypatch, code: int) -> None:
    target = tmp_path / "mounted.conf"
    target.write_text("key = before\n")
    inode = target.stat().st_ino

    def refuse(source: Path, dest: Path) -> None:
        raise OSError(code, os.strerror(code))

    monkeypatch.setattr(edit_file.os, "replace", refuse)
    result, records = _run_recorded(target, "before", "after")

    assert result.ok
    assert target.read_text() == "key = after\n"
    assert target.stat().st_ino == inode
    assert list(tmp_path.iterdir()) == [target]
    assert [record.op for record in records] == ["edit"]


def _as_before(target: Path, **changed) -> SimpleNamespace:
    st = target.stat()
    seen = {"st_nlink": st.st_nlink, "st_uid": st.st_uid, "st_gid": st.st_gid, "st_mode": st.st_mode, "st_flags": 0}
    return SimpleNamespace(**{**seen, **changed})


def test_the_staged_copy_takes_another_owner_before_it_replaces_the_file(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "owned.txt"
    target.write_text("before\n")
    order: list[tuple] = []
    replace = os.replace
    monkeypatch.setattr(edit_file.os, "fchown", lambda fd, uid, gid: order.append(("fchown", uid, gid)))
    monkeypatch.setattr(edit_file.os, "replace", lambda source, dest: (order.append(("replace",)), replace(source, dest))[1])

    theirs = _as_before(target, st_uid=target.stat().st_uid + 1)
    assert edit_file._replaced(target, b"after\n", theirs) is True
    assert order == [("fchown", theirs.st_uid, theirs.st_gid), ("replace",)]

    order.clear()
    assert edit_file._replaced(target, b"again\n", _as_before(target)) is True
    assert order == [("replace",)]
    assert target.read_bytes() == b"again\n"


@pytest.mark.parametrize("call", ["fchown", "fchmod"])
@pytest.mark.parametrize("code", [errno.EPERM, errno.EINVAL, errno.ENOTSUP])
def test_an_owner_or_mode_the_staged_copy_cannot_take_means_in_place(tmp_path: Path, monkeypatch, call: str, code: int) -> None:
    target = tmp_path / "theirs.txt"
    target.write_text("before\n")

    def refuse(fd, *args) -> None:
        raise OSError(code, os.strerror(code))

    monkeypatch.setattr(edit_file.os, call, refuse)
    theirs = _as_before(target, st_uid=target.stat().st_uid + 1)

    assert edit_file._replaced(target, b"after\n", theirs) is False
    assert target.read_text() == "before\n"
    assert list(tmp_path.iterdir()) == [target]


def test_a_mode_the_staged_copy_silently_does_not_take_means_in_place(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "shared.txt"
    target.write_text("before\n")
    target.chmod(0o664)
    monkeypatch.setattr(edit_file.os, "fchmod", lambda fd, mode: None)

    assert edit_file._replaced(target, b"after\n", _as_before(target)) is False
    assert target.read_text() == "before\n"
    assert list(tmp_path.iterdir()) == [target]


def test_a_plain_file_is_replaced_not_rewritten(tmp_path: Path) -> None:
    target = tmp_path / "plain.txt"
    target.write_text("before\n")
    inode = target.stat().st_ino
    handle = target.open()

    assert EditFile().run(str(target), "before", "after").ok

    assert target.stat().st_ino != inode
    assert handle.read() == "before\n"
    handle.close()


def _tagged(path: Path) -> bool:
    if hasattr(os, "setxattr"):
        try:
            os.setxattr(path, "user.alpi.test", b"1")
        except OSError:
            return False
        return True
    return sys.platform == "darwin" and subprocess.run(["xattr", "-w", "com.example.tag", "1", str(path)]).returncode == 0


def test_an_extended_attribute_survives_an_edit(tmp_path: Path) -> None:
    target = tmp_path / "tagged.txt"
    target.write_text("before\n")
    if not _tagged(target):
        pytest.skip("this filesystem stores no extended attributes")
    inode = target.stat().st_ino

    assert EditFile().run(str(target), "before", "after").ok

    assert target.read_text() == "after\n"
    assert target.stat().st_ino == inode
    assert edit_file._carries_attributes(target)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS access control lists")
def test_an_access_control_list_survives_an_edit_on_macos(tmp_path: Path) -> None:
    target = tmp_path / "shared.txt"
    target.write_text("before\n")
    subprocess.run(["chmod", "+a", "everyone allow read", str(target)], check=True)
    inode = target.stat().st_ino

    assert EditFile().run(str(target), "before", "after").ok

    assert target.stat().st_ino == inode
    assert "everyone allow read" in subprocess.run(["ls", "-le", str(target)], capture_output=True, text=True).stdout


@pytest.mark.parametrize("before, names, replaced", [
    ({"st_flags": 0x8000}, [], False),
    ({}, ["user.tag"], False),
    ({}, ["system.posix_acl_access", "security.selinux"], False),
    ({}, ["com.apple.quarantine", "com.apple.provenance"], False),
    ({}, ["access control list"], False),
    ({}, ["security.selinux"], True),
    ({}, ["com.apple.provenance"], True),
    ({}, [], True),
])
def test_a_file_with_flags_or_extended_attributes_is_never_replaced(tmp_path: Path, monkeypatch, before, names, replaced) -> None:
    target = tmp_path / "tagged.txt"
    target.write_text("before\n")
    monkeypatch.setattr(edit_file, "_attribute_names", lambda path: set(names))

    assert edit_file._replaced(target, b"after\n", _as_before(target, **before)) is replaced

    assert target.read_bytes() == (b"after\n" if replaced else b"before\n")
    assert list(tmp_path.iterdir()) == [target]


def test_every_name_of_a_hard_linked_file_sees_the_edit(tmp_path: Path) -> None:
    target = tmp_path / "one.txt"
    target.write_text("before\n")
    other = tmp_path / "two.txt"
    os.link(target, other)

    assert EditFile().run(str(target), "before", "after").ok

    assert other.read_text() == "after\n"
    assert other.stat().st_ino == target.stat().st_ino


def test_a_file_edited_in_place_keeps_its_special_permission_bits(tmp_path: Path) -> None:
    target = tmp_path / "tool.sh"
    target.write_text("echo before\n")
    os.link(target, tmp_path / "alias.sh")
    target.chmod(0o2750)
    mode = S_IMODE(target.stat().st_mode)

    assert EditFile().run(str(target), "before", "after").ok

    assert S_IMODE(target.stat().st_mode) == mode


@pytest.mark.parametrize("code", [errno.EACCES, errno.EPERM, errno.EROFS, errno.ENAMETOOLONG])
def test_a_file_in_a_directory_that_takes_no_new_entries_is_still_edited(tmp_path: Path, monkeypatch, code: int) -> None:
    target = tmp_path / "note.txt"
    target.write_text("before\n")

    def no_room(*args, **kwargs):
        raise OSError(code, os.strerror(code))

    monkeypatch.setattr(edit_file, "NamedTemporaryFile", no_room)
    result, records = _run_recorded(target, "before", "after")

    assert result.ok
    assert target.read_text() == "after\n"
    assert len(records) == 1


@pytest.mark.parametrize("code", [errno.ENOSPC, errno.EDQUOT, errno.EIO, errno.ENFILE])
def test_a_volume_that_cannot_hold_the_staged_copy_is_not_written_in_place(tmp_path: Path, monkeypatch, code: int) -> None:
    target = tmp_path / "note.txt"
    target.write_bytes(b"before\n")
    inode = target.stat().st_ino

    def full(*args, **kwargs):
        raise OSError(code, os.strerror(code))

    monkeypatch.setattr(edit_file, "NamedTemporaryFile", full)
    monkeypatch.setattr(Path, "write_bytes", lambda self, data: pytest.fail("the original was opened for a truncating write"))
    result, records = _run_recorded(target, "before", "after")

    assert not result.ok and "Cannot write" in result.error
    assert target.read_bytes() == b"before\n" and target.stat().st_ino == inode
    assert records == []


def test_an_in_place_write_that_fails_is_reported(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "mounted.conf"
    target.write_text("before\n")

    def busy(source, dest) -> None:
        raise OSError(errno.EBUSY, "Device or resource busy")

    def broken(self, data) -> None:
        raise OSError(errno.EIO, "Input/output error")

    monkeypatch.setattr(edit_file.os, "replace", busy)
    monkeypatch.setattr(Path, "write_bytes", broken)
    result, records = _run_recorded(target, "before", "after")

    assert not result.ok and "Input/output error" in result.error
    assert list(tmp_path.iterdir()) == [target]
    assert records == []


def test_a_staged_copy_that_cannot_be_written_never_touches_the_original(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "note.txt"
    target.write_bytes(b"before\n")

    def full(fd: int) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(edit_file.os, "fsync", full)
    result, records = _run_recorded(target, "before", "after")

    assert not result.ok
    assert "No space left" in result.error
    assert target.read_bytes() == b"before\n"
    assert list(tmp_path.iterdir()) == [target]
    assert records == []


def test_windows_line_endings_survive_and_a_plain_newline_still_matches(tmp_path: Path) -> None:
    target = tmp_path / "dos.txt"
    target.write_bytes(b"one\r\ntwo\r\nthree\r\n")

    result, records = _run_recorded(target, "one\ntwo", "uno\ndos\nmore")

    assert result.ok
    assert target.read_bytes() == b"uno\r\ndos\r\nmore\r\nthree\r\n"
    assert records[0].bytes_after == len(target.read_bytes())


@pytest.mark.parametrize("raw, old, new, expected", [
    (b"one\r\ntwo\nthree\rfour before\n", "before", "after", b"one\r\ntwo\nthree\rfour after\n"),
    (b"one\r\ntwo\r\nthree\n", "one\ntwo", "uno\ndos", b"uno\r\ndos\r\nthree\n"),
    (b"one\r\ntwo\r\nthree\nfour", "two\nthree", "dos\ntres", b"one\r\ndos\r\ntres\nfour"),
    (b"one\rtwo\rthree\r", "one\ntwo", "uno\ndos\nmore", b"uno\rdos\rmore\rthree\r"),
    (b"one\r\ntwo\r\n", "one\r\ntwo", "uno\r\ndos", b"uno\r\ndos\r\n"),
    (b"one\ntwo\n", "one\r\ntwo", "uno\r\ndos", b"uno\ndos\n"),
    (b"one\r\ntwo\r\n", "two", "dos\nmore", b"one\r\ndos\r\nmore\r\n"),
    (b"no newline", "no", "one\nmore", b"one\nmore newline"),
    (b"header\r\nalpha\nbeta\ngamma\n", "beta", "beta\nbeta2", b"header\r\nalpha\nbeta\nbeta2\ngamma\n"),
    (b"one\r\ntwo\nlast", "last", "last\nmore", b"one\r\ntwo\nlast\nmore"),
    (b"one\r\nlast", "last", "last\nmore", b"one\r\nlast\r\nmore"),
    (b"x\r\n\r\ny\r\nx\r\ny\r\n", "x\n\ny", "z", b"z\r\nx\r\ny\r\n"),
    (b"a.b(c)*[d]+ and axb\n", "a.b(c)*[d]+", "\\1\\g<0> C:\\new", b"\\1\\g<0> C:\\new and axb\n"),
    (b"bar\r\n", "bar", "progress\rdone", b"progress\rdone\r\n"),
])
def test_an_edit_matches_across_any_line_ending_and_writes_the_one_it_found(tmp_path: Path, raw, old, new, expected) -> None:
    target = tmp_path / "mixed.txt"
    target.write_bytes(raw)

    result = EditFile().run(str(target), old, new)

    assert result.ok, result.error
    assert target.read_bytes() == expected


@pytest.mark.parametrize("raw, old", [
    (b"x\r\ny\r\n", "x\n\ny"),
    (b"foo" + b"\r\n" * 61 + b"bar", "foo" + "\n" * 60 + "bar"),
    (b"x\ny\n", "x\n\ny"),
])
def test_one_line_ending_in_the_file_never_stands_for_two_in_the_search(tmp_path: Path, raw: bytes, old: str) -> None:
    target = tmp_path / "blank.txt"
    target.write_bytes(raw)

    result = EditFile().run(str(target), old, "z")

    assert not result.ok and result.error == "old_string not found"
    assert target.read_bytes() == raw


@pytest.mark.parametrize("raw, old, new, expected", [
    (b"x\ry\n", "y", "\ny", b"x\r\ry\n"),
    (b"a\rb\nc", "a\nb", "A\nB\n", b"A\nB\n\nc"),
])
def test_a_new_line_ending_never_fuses_with_the_one_beside_it(tmp_path: Path, raw, old, new, expected) -> None:
    target = tmp_path / "old-mac.txt"
    target.write_bytes(raw)

    assert EditFile().run(str(target), old, new).ok

    assert target.read_bytes() == expected


def test_a_carriage_return_that_would_join_the_next_line_ending_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "lines.txt"
    target.write_bytes(b"one\ntwo\n")

    result = EditFile().run(str(target), "one", "one\r")

    assert not result.ok and "merge" in result.error
    assert target.read_bytes() == b"one\ntwo\n"


def test_a_match_that_is_unique_only_by_its_line_ending_is_still_ambiguous(tmp_path: Path) -> None:
    target = tmp_path / "twice.txt"
    target.write_bytes(b"x\ry\nx\ny\n")

    result = EditFile().run(str(target), "x\ny", "z")

    assert not result.ok and "matches 2 times" in result.error
    assert target.read_bytes() == b"x\ry\nx\ny\n"


def test_a_file_with_old_mac_line_endings_is_linted_as_its_lines(tmp_path: Path) -> None:
    target = tmp_path / "c.toml"
    target.write_bytes(b"a = 1\rb = 2\n")

    assert EditFile().run(str(target), "a = 1", "a = 3").ok

    assert target.read_bytes() == b"a = 3\rb = 2\n"


def test_an_edit_through_a_symlink_changes_its_target_and_keeps_the_link(tmp_path: Path) -> None:
    real = tmp_path / "real.txt"
    real.write_text("before\n")
    link = tmp_path / "link.txt"
    link.symlink_to(real)

    assert EditFile().run(str(link), "before", "after").ok

    assert link.is_symlink() and real.read_text() == "after\n"


def test_a_file_the_process_may_not_write_is_not_replaced_behind_its_permissions(tmp_path: Path) -> None:
    target = tmp_path / "locked.txt"
    target.write_text("before\n")
    target.chmod(0o444)
    inode = target.stat().st_ino

    result = EditFile().run(str(target), "before", "after")

    if os.access(target, os.W_OK):
        assert result.ok
    else:
        assert not result.ok and "Cannot open" in result.error
        assert target.read_text() == "before\n" and target.stat().st_ino == inode
    assert list(tmp_path.iterdir()) == [target]


def test_a_file_whose_folder_cannot_be_entered_is_a_result_not_a_crash(tmp_path: Path) -> None:
    folder = tmp_path / "closed"
    folder.mkdir()
    target = folder / "note.txt"
    target.write_text("before\n")
    folder.chmod(0o000)
    try:
        result = EditFile().run(str(target), "before", "after")
    finally:
        folder.chmod(0o755)

    assert result.ok or "Cannot open" in result.error or "File not found" in result.error
    assert result.ok == (target.read_text() == "after\n")


def test_a_yaml_value_the_parser_rejects_is_a_refusal_not_a_crash(tmp_path: Path) -> None:
    target = tmp_path / "plan.yaml"
    target.write_text("when: 2001-01-01\n")

    result = EditFile().run(str(target), "2001-01-01", "2001-13-45")

    assert not result.ok and "unparseable" in result.error
    assert target.read_text() == "when: 2001-01-01\n"


def test_a_directory_and_a_binary_file_are_refused_with_their_reason(tmp_path: Path) -> None:
    folder = tmp_path / "folder"
    folder.mkdir()
    binary = tmp_path / "blob.bin"
    binary.write_bytes(b"\xff\xfe before \x80")

    assert "Not a regular file" in EditFile().run(str(folder), "a", "b").error
    result = EditFile().run(str(binary), "before", "after")
    assert not result.ok and "Cannot open" in result.error
    assert binary.read_bytes() == b"\xff\xfe before \x80"


def test_the_staged_copy_is_a_hidden_sibling_named_after_the_file(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / ("long" * 80 + ".txt")[-200:]
    target.write_text("before\n")
    seen: list[str] = []
    replace = os.replace
    monkeypatch.setattr(edit_file.os, "replace", lambda source, dest: (seen.append(Path(source).name), replace(source, dest))[1])

    assert EditFile().run(str(target), "before", "after").ok

    assert seen[0].startswith(f".{target.name[:64]}.") and seen[0].endswith(".tmp")


def test_special_permission_bits_are_kept(tmp_path: Path) -> None:
    target = tmp_path / "tool.sh"
    target.write_text("echo before\n")
    target.chmod(0o2750)
    mode = S_IMODE(target.stat().st_mode)

    assert EditFile().run(str(target), "before", "after").ok

    assert S_IMODE(target.stat().st_mode) == mode
