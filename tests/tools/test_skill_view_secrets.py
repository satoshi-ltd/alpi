from __future__ import annotations

from pathlib import Path

import pytest

from alpi.tools.skill import Skill

SECRET = "sk-live-do-not-show-0123456789"


@pytest.fixture
def skill_dir(tmp_home: Path) -> Path:
    d = tmp_home / "skills" / "miscellaneous" / "demo"
    for sub in ("references", "secrets", "scripts"):
        (d / sub).mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: demo\ndescription: x\ncategory: miscellaneous\nversion: 0.1.0\norigin: user\n---\nbody\n"
    )
    (d / "secrets" / "token.txt").write_text(SECRET)
    (d / "references" / "page.md").write_text("# page")
    return d


def test_view_refuses_a_file_under_secrets(skill_dir: Path) -> None:
    r = Skill().run(action="view", name="demo", file="secrets/token.txt")
    assert not r.ok
    assert "secrets/ is not readable" in r.error
    assert SECRET not in (r.output + r.error)


def test_view_refuses_a_link_into_secrets(skill_dir: Path) -> None:
    (skill_dir / "references" / "notes.md").symlink_to(skill_dir / "secrets" / "token.txt")
    r = Skill().run(action="view", name="demo", file="references/notes.md")
    assert not r.ok
    assert SECRET not in (r.output + r.error)


def test_view_refuses_a_link_to_the_profile_env(skill_dir: Path, tmp_home: Path) -> None:
    (tmp_home / ".env").write_text(f"OPENAI_API_KEY={SECRET}\n")
    (skill_dir / "references" / "env.md").symlink_to(tmp_home / ".env")
    r = Skill().run(action="view", name="demo", file="references/env.md")
    assert not r.ok
    assert SECRET not in (r.output + r.error)


def test_view_still_reads_skill_md_and_references(skill_dir: Path) -> None:
    assert Skill().run(action="view", name="demo").output.endswith("body\n")
    r = Skill().run(action="view", name="demo", file="references/page.md")
    assert r.ok and "# page" in r.output


def test_view_refuses_a_link_spelled_with_another_case(skill_dir: Path) -> None:
    upper = skill_dir / "SECRETS" / "token.txt"
    if not upper.exists():
        upper.parent.mkdir()
        upper.write_text(SECRET)
    (skill_dir / "references" / "n.md").symlink_to(Path("..") / "SECRETS" / "token.txt")
    r = Skill().run(action="view", name="demo", file="references/n.md")
    assert not r.ok
    assert SECRET not in (r.output + r.error)


@pytest.mark.parametrize("guess", ["sk-", "zz-", "-"])
def test_patch_on_secrets_gives_the_same_answer_whatever_the_guess(skill_dir: Path, guess: str) -> None:
    r = Skill().run(action="patch", name="demo", subdir="secrets", filename="token.txt",
                    old_string=guess, new_string=guess, confirm_user_skill=True)
    assert not r.ok
    assert "secrets/ is not readable" in r.error
    assert not (skill_dir / "secrets" / "token.txt.bak").exists()
    assert (skill_dir / "secrets" / "token.txt").read_text() == SECRET


def test_patch_through_a_link_does_not_copy_the_secret_out(skill_dir: Path) -> None:
    link = skill_dir / "references" / "notes.md"
    link.symlink_to(skill_dir / "secrets" / "token.txt")
    r = Skill().run(action="patch", name="demo", subdir="references", filename="notes.md",
                    old_string="sk-", new_string="sk-", confirm_user_skill=True)
    assert not r.ok
    assert link.is_symlink()
    assert not (skill_dir / "references" / "notes.md.bak").exists()


def _link_skill_md_to_env(skill_dir: Path, tmp_home: Path) -> None:
    (tmp_home / ".env").write_text(f"OPENAI_API_KEY={SECRET}\n")
    (skill_dir / "SKILL.md").unlink()
    (skill_dir / "SKILL.md").symlink_to(tmp_home / ".env")


def test_run_without_a_script_does_not_return_a_linked_env(skill_dir: Path, tmp_home: Path) -> None:
    _link_skill_md_to_env(skill_dir, tmp_home)
    r = Skill().run(action="run", name="demo")
    assert not r.ok
    assert SECRET not in (r.output + r.error)


def test_edit_does_not_back_up_a_linked_env(skill_dir: Path, tmp_home: Path) -> None:
    _link_skill_md_to_env(skill_dir, tmp_home)
    r = Skill().run(action="edit", name="demo", body="new prose for the skill", confirm_user_skill=True)
    assert not r.ok
    assert not (skill_dir / "SKILL.md.bak").exists()
    assert (tmp_home / ".env").read_text() == f"OPENAI_API_KEY={SECRET}\n"


def test_patch_and_edit_still_work_on_plain_files(skill_dir: Path) -> None:
    r = Skill().run(action="patch", name="demo", subdir="references", filename="page.md",
                    old_string="# page", new_string="# page two", confirm_user_skill=True)
    assert r.ok, r.error
    r = Skill().run(action="edit", name="demo", body="fresh prose for the skill", confirm_user_skill=True)
    assert r.ok, r.error


def test_set_meta_does_not_turn_a_linked_key_into_a_plain_skill_md(skill_dir: Path) -> None:
    key = skill_dir / "secrets" / "id_key"
    key.write_text(f"-----BEGIN OPENSSH PRIVATE KEY-----\n{SECRET}\n-----END OPENSSH PRIVATE KEY-----\n")
    (skill_dir / "SKILL.md").unlink()
    (skill_dir / "SKILL.md").symlink_to(key)
    r = Skill().run(action="set_meta", name="demo", confirm_user_skill=True, fields={
        "name": "demo", "description": "x", "category": "miscellaneous", "version": "0.1.0", "origin": "user",
    })
    assert not r.ok
    assert (skill_dir / "SKILL.md").is_symlink()
    assert not (skill_dir / "SKILL.md.bak").exists()


def test_view_refuses_a_link_through_a_linked_secrets_dir(skill_dir: Path, tmp_path: Path) -> None:
    shared = tmp_path / "shared-creds"
    shared.mkdir()
    (shared / "token.txt").write_text(SECRET)
    for f in (skill_dir / "secrets").iterdir():
        f.unlink()
    (skill_dir / "secrets").rmdir()
    (skill_dir / "secrets").symlink_to(shared)
    (skill_dir / "references" / "n.md").symlink_to(Path("..") / "secrets" / "token.txt")
    r = Skill().run(action="view", name="demo", file="references/n.md")
    assert not r.ok
    assert SECRET not in (r.output + r.error)


def test_view_refuses_a_link_to_an_archived_skills_secret(skill_dir: Path, tmp_home: Path) -> None:
    archived = tmp_home / "skills" / ".archive" / "miscellaneous" / "old__20261120T000000Z" / "secrets"
    archived.mkdir(parents=True)
    (archived / "token.txt").write_text(SECRET)
    (skill_dir / "references" / "n.md").symlink_to(archived / "token.txt")
    r = Skill().run(action="view", name="demo", file="references/n.md")
    assert not r.ok
    assert SECRET not in (r.output + r.error)


def test_file_tools_refuse_an_archived_skills_secret(tmp_home: Path) -> None:
    from alpi.tools._paths import is_read_denied

    assert is_read_denied(tmp_home / "skills" / ".archive" / "c" / "n__ts" / "secrets" / "token.txt")


def test_view_still_reads_a_plain_pem_reference(skill_dir: Path) -> None:
    (skill_dir / "references" / "ca.pem").write_text("-----BEGIN CERTIFICATE-----\npublic\n")
    r = Skill().run(action="view", name="demo", file="references/ca.pem")
    assert r.ok, r.error


def test_view_refuses_a_symlink_loop_without_crashing(skill_dir: Path) -> None:
    a = skill_dir / "references" / "a.md"
    b = skill_dir / "references" / "b.md"
    a.symlink_to(b)
    b.symlink_to(a)
    r = Skill().run(action="view", name="demo", file="references/a.md")
    assert not r.ok
    assert "crashed" not in (r.error or "")


def test_run_refuses_a_script_that_links_to_the_profile_env(skill_dir: Path, tmp_home: Path) -> None:
    plain = "plainSECRETVALUE"
    (tmp_home / ".env").write_text(f"GITHUB_TOKEN={plain}\n")
    (skill_dir / "scripts" / "run.py").symlink_to(tmp_home / ".env")
    for action in ("run", "test"):
        r = Skill().run(action=action, name="demo")
        assert not r.ok, action
        assert plain not in (r.output + (r.error or "")), action

