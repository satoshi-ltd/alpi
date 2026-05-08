from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-site.yml"


def test_site_deploy_waits_for_checks_and_release_contract() -> None:
    text = WORKFLOW.read_text()
    deploy = text.split("  deploy:", 1)[1]

    assert "pytest -q" in text
    assert "pytest --integration -q" in text
    assert "runs-on: ubuntu-22.04" in text
    assert "uv build" in text
    assert "uvx twine check dist/*" in text
    assert "node site/scripts/build.mjs" in text
    assert "pypi.org/pypi/alpi-agent/json" in text
    assert 'gh", "release", "view", tag' in text
    assert "desktop-release.json" in text

    assert "      - site-build" in deploy
    assert "      - release-contract" in deploy
    assert "cloudflare/wrangler-action@v3" in deploy
    assert "CLOUDFLARE_ACCOUNT_ID" in deploy
    assert "CLOUDFLARE_API_TOKEN" in deploy
    assert "CLOUDFLARE_PAGES_PROJECT_NAME" in deploy
    assert "pages deploy site-dist" in deploy
