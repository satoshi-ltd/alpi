from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PUBLISH = ROOT / ".github" / "workflows" / "publish.yml"
PUBLISH_DESKTOP = ROOT / ".github" / "workflows" / "publish-desktop.yml"
PUBLISH_SITE = ROOT / ".github" / "workflows" / "publish-site.yml"


def test_publish_site_is_single_source_of_truth() -> None:
    """``publish-site.yml`` owns the site rebuild + deploy. Other release workflows must not duplicate it."""
    publish = PUBLISH.read_text()
    desktop = PUBLISH_DESKTOP.read_text()

    assert "node site/scripts/build.mjs" not in publish
    assert "cloudflare/wrangler-action" not in publish
    assert "pages deploy" not in publish

    assert "node site/scripts/build.mjs" not in desktop
    assert "cloudflare/wrangler-action" not in desktop
    assert "pages deploy" not in desktop


def test_publish_site_auto_fires_after_release_workflows() -> None:
    """A successful ``publish`` or ``publish-desktop`` must rebuild the site automatically."""
    text = PUBLISH_SITE.read_text()
    on_block = text.split("on:", 1)[1].split("\njobs:", 1)[0]

    assert "workflow_dispatch:" in on_block
    assert "workflow_run:" in on_block
    assert '"publish"' in on_block
    assert '"publish-desktop"' in on_block
    assert "branches: [main]" in on_block

    assert "push:" in on_block
    assert '"site/**"' in on_block

    assert "github.event.workflow_run.conclusion == 'success'" in text

    assert "node site/scripts/build.mjs" in text
    assert "cloudflare/wrangler-action@v3" in text
    assert "CLOUDFLARE_ACCOUNT_ID" in text
    assert "CLOUDFLARE_API_TOKEN" in text
    assert "CLOUDFLARE_PAGES_PROJECT_NAME" in text
    assert "pages deploy site-dist" in text
