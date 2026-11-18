"""Regression tests for v1.8 -> Unreal Spatial Lab launcher.

No hardware, Unreal installation or GUI display needed.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from spatial_lab_launcher import (
    SpatialLabLaunchError, validate_target, save_target, stored_target,
    launch, discover_target,
)

def test_valid_unreal_source_and_refuses_unrelated_file():
    with TemporaryDirectory() as tmp:
        project = Path(tmp)/"BuggySensorViz.uproject"
        project.write_text("{}", encoding="utf-8")
        assert validate_target(project) == project.resolve()
        other = Path(tmp)/"normal_app.exe"
        other.write_text("stub", encoding="utf-8")
        try:
            validate_target(other)
            assert False, "unrelated .exe must be rejected"
        except SpatialLabLaunchError:
            pass
        try:
            validate_target(Path(tmp)/"not-real.bat")
            assert False, "untrusted batch file must be rejected"
        except SpatialLabLaunchError:
            pass

def test_local_preference_roundtrip_never_stores_motor_state():
    with TemporaryDirectory() as tmp:
        project = Path(tmp)/"BuggySensorViz.uproject"
        project.write_text("{}", encoding="utf-8")
        pref = Path(tmp)/"private"/"spatial_lab.json"
        with patch("spatial_lab_launcher.settings_path", return_value=pref):
            save_target(project)
            assert stored_target() == project.resolve()
            data = json.loads(pref.read_text(encoding="utf-8"))
            assert set(data) == {"schema","path"}
            assert not any(word in pref.read_text().lower() for word in ("armed", "motor", "ble"))
            pref.write_text('{"schema": 1, "path": "missing.exe"}', encoding="utf-8")
            assert stored_target() is None

def test_executable_uses_argument_list_no_shell_and_nonblocking():
    with TemporaryDirectory() as tmp:
        exe = Path(tmp)/"BuggySensorViz-Win64-Shipping.exe"
        exe.write_bytes(b"test")
        call = Mock(return_value=SimpleNamespace(pid=1234))
        result = launch(exe, platform="win32", popen=call)
        assert result.pid == 1234
        argv = call.call_args.args[0]
        assert argv == [str(exe.resolve())]
        assert call.call_args.kwargs["shell"] is False
        assert os.path.samefile(call.call_args.kwargs["cwd"], exe.parent)

def test_unreal_project_opens_explicit_editor_not_shell():
    with TemporaryDirectory() as tmp:
        project = Path(tmp)/"BuggySensorViz.uproject"
        editor = Path(tmp)/"UnrealEditor.exe"
        project.write_text("{}", encoding="utf-8")
        editor.write_bytes(b"stub")
        call = Mock(return_value=SimpleNamespace(pid=3))
        launch(project, platform="win32", popen=call, editor=editor)
        assert call.call_args.args[0] == [str(editor.resolve()), str(project.resolve())]
        assert call.call_args.kwargs["shell"] is False

def test_project_requires_installed_unreal_editor():
    with TemporaryDirectory() as tmp:
        project = Path(tmp)/"BuggySensorViz.uproject"
        project.write_text("{}", encoding="utf-8")
        with patch("spatial_lab_launcher.unreal_editor_path", return_value=None):
            try:
                launch(project, platform="win32", popen=Mock())
                assert False, "missing Unreal should be explicit"
            except SpatialLabLaunchError as exc:
                assert "Unreal Engine 5.4" in str(exc)

def test_never_launch_on_unsupported_platform():
    with TemporaryDirectory() as tmp:
        project = Path(tmp)/"BuggySensorViz.uproject"
        project.write_text("{}", encoding="utf-8")
        call = Mock()
        try:
            launch(project, platform="linux", popen=call)
            assert False, "non-Windows process launch must fail"
        except SpatialLabLaunchError:
            call.assert_not_called()

def test_studio_refuses_live_ble_and_requests_safety_brake():
    from app import BuggyApp
    instance = BuggyApp.__new__(BuggyApp)
    instance.online = True
    instance.demo = False
    instance.emergency_stop = Mock()
    instance.log = Mock()
    instance.flight = SimpleNamespace(record=Mock())
    with patch("app.messagebox.showwarning") as warning, \
         patch("app.discover_target") as discover, \
         patch("app.launch_spatial_lab") as spawn:
        assert instance.open_spatial_lab() is False
        instance.emergency_stop.assert_called_once_with(quiet=True)
        warning.assert_called_once()
        discover.assert_not_called()
        spawn.assert_not_called()

def test_studio_offline_starts_visualizer_only():
    from app import BuggyApp
    with TemporaryDirectory() as tmp:
        project = Path(tmp)/"BuggySensorViz.uproject"
        project.write_text("{}", encoding="utf-8")
        instance = BuggyApp.__new__(BuggyApp)
        instance.online = False
        instance.demo = True
        instance.emergency_stop = Mock()
        instance.log = Mock()
        instance.flight = SimpleNamespace(record=Mock())
        with patch("app.discover_target", return_value=project), \
             patch("app.launch_spatial_lab") as spawn:
            assert instance.open_spatial_lab() is True
            instance.emergency_stop.assert_called_once_with(quiet=True)
            spawn.assert_called_once_with(project)
            instance.flight.record.assert_called_once()
