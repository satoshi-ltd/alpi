from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PUBLISH = ROOT / ".github" / "workflows" / "publish.yml"
PUBLISH_SITE = ROOT / ".github" / "workflows" / "publish-site.yml"


def test_publish_runs_site_deploy_after_pypi() -> None:
    """Site deploy is the final step of the release chain — no polling."""
    text = PUBLISH.read_text()

    site_build = text.split("  site-build:", 1)[1].split("\n  deploy-site:", 1)[0]
    deploy_site = text.split("  deploy-site:", 1)[1]

    assert "node site/scripts/build.mjs" in site_build
    assert "needs: check-version" in site_build

    # deploy-site must run AFTER publish-pypi so the site reflects
    # what's actually live on PyPI.
    assert "publish-pypi" in deploy_site
    assert "site-build" in deploy_site
    assert "cloudflare/wrangler-action@v3" in deploy_site
    assert "CLOUDFLARE_ACCOUNT_ID" in deploy_site
    assert "CLOUDFLARE_API_TOKEN" in deploy_site
    assert "CLOUDFLARE_PAGES_PROJECT_NAME" in deploy_site
    assert "pages deploy site-dist" in deploy_site


def test_publish_site_is_workflow_dispatch_only() -> None:
    """``publish-site.yml`` exists for on-demand redeploys without a release."""
    text = PUBLISH_SITE.read_text()
    assert "workflow_dispatch:" in text
    # Must not auto-fire on push — that's what publish.yml owns.
    on_block = text.split("on:", 1)[1].split("\n\n", 1)[0]
    assert "push:" not in on_block
    assert "node site/scripts/build.mjs" in text
    assert "cloudflare/wrangler-action@v3" in text
    assert "pages deploy site-dist" in text
