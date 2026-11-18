"""Regression checks for the Windows native app/installer.

Run on Linux CI (no Windows GUI or Bluetooth required) and Windows packaging CI.
These tests never open the BLE link or energize a motor.
"""
from __future__ import annotations

from pathlib import Path

import desktop_entry
import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "installer" / "CabbageStudio.iss"
WORKFLOW = ROOT.parent / ".github" / "workflows" / "windows-candidate-build.yml"


def test_installer_is_user_scoped_and_does_not_need_admin():
    text = INSTALLER.read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in text
    assert r"DefaultDirName={localappdata}\Programs\CabbageControlStudio" in text
    assert "ChangesEnvironment=no" in text
    assert "MinVersion=10.0" in text
    assert 'Source: "..\\dist\\CabbageControlStudio.exe"' in text
    assert "CloseApplications=no" in text
    assert 'Source: "..\\..\\unreal-visualizer\\*"' in text
    assert r'DestDir: "{app}\unreal-visualizer"' in text
    assert "recursesubdirs createallsubdirs" in text
    assert 'Source: "..\\SPATIAL_LAB_INTEGRATION.md"' in text


def test_installer_creates_live_buggy_shortcuts_without_simulator():
    text = INSTALLER.read_text(encoding="utf-8")
    assert r'{group}\Cabbage Control Studio' in text
    assert r'{autodesktop}\Cabbage Control Studio' in text
    assert 'Parameters: "--demo"' not in text
    assert 'Demo (No Motors)' not in text
    assert "Flags: unchecked" in text
    assert "UninstallDisplayName=" in text
    assert "Filename: \"{uninstallexe}\"" in text
    assert "[Run]" in text and "postinstall skipifsilent unchecked" in text
    # No startup-at-login or background auto-connection task.
    assert r"{userstartup}" not in text and r"{commonstartup}" not in text


def test_packaging_is_genuinely_windowed_and_has_installer_artifact():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "--windowed" in text
    assert "desktop_entry.py" in text
    assert "--onefile" in text
    assert "branding/CabbageStudio.ico" in text
    assert "installer/CabbageStudio.iss" in text
    assert "CABBAGE-Studio-v1.8.2-Windows-INSTALLER-LIVE" in text
    assert "CABBAGE-Studio-v1.8.2-PORTABLE-WITH-SPATIAL-LAB" in text
    assert 'Copy-Item -Path "../unreal-visualizer"' in text
    assert 'dist/portable/unreal-visualizer/BuggySensorViz.uproject' in text
    assert 'tests/test_spatial_lab_launcher.py' in text


def test_no_automatic_hardware_arming_in_desktop_launcher():
    src = (ROOT / "desktop_entry.py").read_text(encoding="utf-8")
    assert "from app import main" in src
    assert ".set_motor(" not in src
    assert ".connect(" not in src
    assert ".release_emergency(" not in src
    assert "one_instance_on_windows" in src


def test_desktop_exception_reports_are_recoverable_without_console(tmp_path, monkeypatch):
    monkeypatch.setattr(desktop_entry, "diagnostics_dir", lambda: tmp_path)
    try:
        raise RuntimeError("Example startup failure")
    except RuntimeError as exc:
        path = desktop_entry.save_crash_report(exc)
    assert path is not None and path.exists()
    content = path.read_text(encoding="utf-8")
    assert "Example startup failure" in content
    assert "CABBAGE Control Studio" in content


def test_icon_builder_produces_real_windows_ico_when_pillow_available(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    from build_icon import build_icon

    icon = build_icon(tmp_path / "CabbageStudio.ico")
    assert icon.exists()
    with Image.open(icon) as image:
        assert image.format == "ICO"
        assert image.size == (256, 256)
        sizes = image.ico.sizes()
        assert (16, 16) in sizes and (48, 48) in sizes and (256, 256) in sizes


def test_live_hardware_ui_requires_explicit_ble_and_has_editor_picker():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "'REAL BLE  /  HARDWARE'" in src
    assert "text='SIMULATOR'" not in src
    assert "'SELECT UNREAL EDITOR 5.4'" in src
    assert "def select_unreal_editor(self):" in src
    assert "UnrealEditorNotFound" in src
    assert "self.emergency_stop(quiet=True)" in src
