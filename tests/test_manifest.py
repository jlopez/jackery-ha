import json
from pathlib import Path

INTEGRATION_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "jackery"


def test_manifest_is_valid_json():
    manifest_path = INTEGRATION_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert isinstance(manifest, dict)


def test_manifest_required_fields():
    manifest_path = INTEGRATION_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["domain"] == "jackery"
    assert manifest["name"] == "Jackery Power Stations"
    assert manifest["config_flow"] is True
    assert manifest["integration_type"] == "hub"
    assert manifest["iot_class"] == "cloud_push"
    assert "socketry>=0.2.0" in manifest["requirements"]
    assert manifest["version"] == "0.1.0"
    assert "@jlopez" in manifest["codeowners"]


def test_strings_is_valid_json():
    strings_path = INTEGRATION_DIR / "strings.json"
    strings = json.loads(strings_path.read_text())
    assert isinstance(strings, dict)


def test_strings_config_flow_coverage():
    strings_path = INTEGRATION_DIR / "strings.json"
    strings = json.loads(strings_path.read_text())
    config = strings["config"]

    # Step definitions
    user_step = config["step"]["user"]
    assert "title" in user_step
    assert "email" in user_step["data"]
    assert "password" in user_step["data"]

    # Error definitions
    errors = config["error"]
    assert "invalid_auth" in errors
    assert "cannot_connect" in errors
    assert "no_devices" in errors
    assert "unknown" in errors

    # Abort definitions
    abort = config["abort"]
    assert "already_configured" in abort
