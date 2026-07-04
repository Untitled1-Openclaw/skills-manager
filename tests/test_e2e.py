from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright


def login(page, base_url: str, password: str = "changeme123") -> None:
    page.goto(base_url)
    page.get_by_label("Username").fill("user")
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()
    expect(page.locator("#app-shell")).to_be_visible()
    expect(page.locator("#section-title")).to_have_text("Skills")
    expect(page.locator("#skills-grid")).to_contain_text("alpha-skill")


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


def test_login_wrong_password_and_skills_search(browser, server: str):
    context = browser.new_context()
    page = context.new_page()
    page.goto(server)
    expect(page.locator("#login-screen")).to_be_visible()
    expect(page.locator("#app-shell")).not_to_be_visible()
    page.get_by_label("Username").fill("user")
    page.get_by_label("Password").fill("wrong")
    page.get_by_role("button", name="Sign in").click()
    expect(page.get_by_text("Invalid username or password")).to_be_visible()
    page.get_by_label("Password").fill("changeme123")
    page.get_by_role("button", name="Sign in").click()
    expect(page.locator("#login-screen")).not_to_be_visible()
    expect(page.locator("#app-shell")).to_be_visible()
    assert page.locator("#login-screen").evaluate("element => getComputedStyle(element).display") == "none"
    assert page.locator("#app-shell").evaluate("element => getComputedStyle(element).display") == "grid"
    expect(page.get_by_text("alpha-skill")).to_be_visible()
    page.get_by_label("Search skills").fill("github")
    expect(page.locator("#skills-grid h2", has_text="single")).to_be_visible()
    expect(page.get_by_text("alpha-skill")).not_to_be_visible()
    context.close()


def test_skill_detail_view_edit_download_and_upload(browser, server: str, tmp_path: Path):
    context = browser.new_context()
    page = context.new_page()
    login(page, server)
    page.get_by_text("alpha-skill").click()
    expect(page.get_by_role("heading", name="Files")).to_be_visible()
    expect(page.get_by_role("button", name="SKILL.md")).to_be_visible()
    expect(page.locator(".markdown")).to_contain_text("Rendered markdown")
    page.get_by_role("button", name="Edit").click()
    page.locator("#editor").fill("---\ndescription: Alpha description\n---\n# Alpha\n\nEdited markdown.\n")
    page.get_by_role("button", name="Save").click()
    page.get_by_role("button", name="Save").last.click()
    expect(page.get_by_text("File saved")).to_be_visible()
    expect(page.locator(".markdown")).to_contain_text("Edited markdown")

    with page.expect_download() as download_info:
        page.get_by_role("link", name="Download skill").click()
    download = download_info.value
    assert download.suggested_filename == "alpha-skill.zip"

    page.get_by_role("link", name="Upload").click()
    md_path = tmp_path / "uploaded.md"
    md_path.write_text("---\ndescription: Uploaded\n---\n# Uploaded\n", encoding="utf-8")
    page.locator("#upload-input").set_input_files(str(md_path))
    expect(page.get_by_text("Uploaded to")).to_be_visible()

    zip_path = tmp_path / "packed.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("packed-skill/SKILL.md", "---\ndescription: Packed\n---\n# Packed\n")
    page.locator("#upload-input").set_input_files(str(zip_path))
    expect(page.get_by_text("incoming/packed")).to_be_visible()
    page.get_by_role("navigation", name="Primary").get_by_role("link", name="Skills", exact=True).click()
    page.get_by_label("Filter category").select_option("incoming")
    expect(page.locator("#skills-grid h2", has_text="uploaded")).to_be_visible()
    context.close()


def test_password_change_flow(browser, server: str):
    context = browser.new_context()
    page = context.new_page()
    login(page, server)
    page.get_by_role("navigation", name="Primary").get_by_role("link", name="Settings", exact=True).click()
    page.get_by_label("Current password").fill("changeme123")
    page.get_by_label("New password").fill("changed456")
    page.get_by_role("button", name="Update password").click()
    expect(page.get_by_text("Password updated.")).to_be_visible()
    page.get_by_role("button", name="Sign out").click()
    page.get_by_label("Password").fill("changed456")
    page.get_by_label("Username").fill("user")
    page.get_by_role("button", name="Sign in").click()
    expect(page.locator("#app-shell")).to_be_visible()
    expect(page.locator("#section-title")).to_have_text("Skills")
    context.close()


def test_mobile_viewport_renders_navigation(browser, server: str):
    context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True)
    page = context.new_page()
    login(page, server)
    expect(page.get_by_role("button", name="Toggle navigation")).to_be_visible()
    expect(page.get_by_text("alpha-skill")).to_be_visible()
    context.close()
