# Contracts for the final cross-platform CI runtime.

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_core_jobs_do_not_load_qt():
    workflow = read(".github/workflows/ci.yml")
    core = workflow[workflow.index("  core-tests:") : workflow.index("  gui-tests:")]
    assert '-e ".[core]"' in core
    assert '-e ".[dev]"' not in core
    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD" in core


def test_linux_gui_runtime_is_complete_pinned_and_diagnosed():
    workflow = read(".github/workflows/ci.yml")
    release = read(".github/workflows/release.yml")
    all_os = read("scripts/test_all_os.sh")
    combined = workflow + release + all_os

    for package in (
        "libegl1",
        "libxcb-cursor0",
        "libxcb-icccm4",
        "libxcb-image0",
        "libxcb-keysyms1",
        "libxcb-render-util0",
        "libxcb-util1",
        "libxcb-xkb1",
        "libxkbcommon-x11-0",
    ):
        assert package in combined

    assert "ubuntu-24.04" in workflow
    assert "ubuntu-latest" not in workflow
    assert "requirements/qt-ci.txt" in combined
    assert "python scripts/check_qt_linux_runtime.py" in combined
    assert "xvfb-run" in combined
    assert "coactions/setup-xvfb" not in combined

    requirements = read("requirements/qt-ci.txt")
    assert "PySide6==6.11.1" in requirements

    checker = read("scripts/check_qt_linux_runtime.py")
    assert "libxcb-icccm.so.4" in checker
    assert "libxcb-image.so.0" in checker
    assert "libxcb-keysyms.so.1" in checker
    assert "libxcb-render-util.so.0" in checker
    assert '["ldd", str(path)]' in checker
    assert '"not found" in line' in checker


def test_workflows_use_node24_action_versions():
    combined = read(".github/workflows/ci.yml") + read(".github/workflows/release.yml")
    for token in (
        "actions/checkout@v6",
        "actions/setup-python@v6",
        "actions/upload-artifact@v6",
        "actions/download-artifact@v7",
        "softprops/action-gh-release@v3",
    ):
        assert token in combined

    for token in (
        "actions/checkout@v4",
        "actions/setup-python@v5",
        "actions/upload-artifact@v4",
        "coactions/setup-xvfb",
    ):
        assert token not in combined


def test_all_os_tests_are_partitioned_and_timeout_bounded():
    workflow = read(".github/workflows/ci.yml")
    all_os = read("scripts/test_all_os.sh")
    runner = read("scripts/run_ci_test_partitions.py")
    worker = read("scripts/run_single_qt_test.py")

    assert "run_ci_test_partitions.py" in workflow
    assert "run_ci_test_partitions.py" in all_os
    assert "Cross-platform non-GUI tests" in all_os
    assert "Isolated Linux GUI and WebEngine tests" in all_os
    assert "Native macOS geometry persistence smoke" in all_os
    assert "Full tests on Windows and macOS" not in all_os
    assert "Full tests on Linux" not in all_os

    assert "process.wait(timeout=timeout)" in runner
    assert "os.killpg" in runner
    assert "taskkill" in runner
    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD" in runner
    assert "GUI TEST PARTITION: PASS" in runner
    assert "run_single_qt_test.py" in runner

    assert "pytest.main" in worker
    assert "pytest_runtest_logreport" in worker
    assert 'report.when != "call"' in worker
    assert "report.passed or report.skipped" in worker
    assert "plugins=[CallPhaseExit()]" in worker
    assert "sys.stdout.flush()" in worker
    assert "sys.stderr.flush()" in worker
    assert "os._exit(exit_code)" in worker

    launcher = read("scripts/test_all_os.sh")
    smoke = read("scripts/smoke_packaged.py")
    app_candidate = 'dist / "pawdf.app" / "Contents" / "MacOS" / "pawdf"'
    bare_candidate = 'dist / "pawdf" / "pawdf"'

    assert 'platform.system() == "Darwin"' in launcher
    assert launcher.index(app_candidate) < launcher.index(bare_candidate)

    assert 'sys.platform == "darwin"' in smoke
    assert smoke.index(app_candidate) < smoke.index(bare_candidate)

    spec = read("packaging/pyinstaller/pawdf.spec")
    hook = read("packaging/pyinstaller/hooks/hook-PySide6.QtWebEngineCore.py")
    builder = read("scripts/build_pyinstaller.py")

    assert 'str(repo_root / "packaging" / "pyinstaller" / "hooks")' in spec
    for token in (
        "_select_binary_framework_version",
        '(child / "QtWebEngineCore").is_file()',
        "_collect_macos_webengine_files",
        "collect_system_data_files",
        "QtWebEngineProcess.app/Contents/MacOS/QtWebEngineProcess",
        "add_qt6_dependencies",
        "PySide6.QtPrintSupport",
    ):
        assert token in hook

    assert "versions[-1]" not in hook
    assert "_repair_macos_webengine_process" not in builder
    assert "shutil.copytree" not in builder
    assert '"--deep"' not in builder


def test_geometry_fixture_fits_hosted_native_screens():
    shell_test = read("tests/gui/test_shell.py")
    assert "target_size = (900, 620)" in shell_test
    assert "first.resize(1101, 733)" not in shell_test


def test_windows_smoke_uses_subprocess_capture():
    workflow = read(".github/workflows/ci.yml")
    smoke = read("scripts/smoke_packaged.py")
    assert "python scripts/smoke_packaged.py --dist dist" in workflow
    assert "pawdf.exe --version" not in workflow

    # `capture()` runs --version/--diagnostics-json synchronously, where a
    # Windows GUI-subsystem executable can receive an invalid inherited
    # stdout handle from PowerShell; capture_output=True gives it explicit,
    # Python-managed pipes instead. Scoped to that function specifically:
    # gui_liveness() legitimately needs raw Popen(stdout=PIPE, ...) because
    # it has to stream a long-running process's output while polling
    # liveness, a case subprocess.run's capture_output shortcut cannot serve.
    capture_fn = smoke[smoke.index("def capture(") : smoke.index("def gui_liveness(")]
    assert "capture_output=True" in capture_fn
    assert "stdout=subprocess.PIPE" not in capture_fn
    assert "stderr=subprocess.PIPE" not in capture_fn


def test_global_pytest_configuration_does_not_force_qt():
    workflow = read(".github/workflows/ci.yml")
    assert "qt_api =" not in read("pyproject.toml")
    assert "PAWDF_CI_REPRODUCIBILITY_V1" in workflow
    assert "PAWDF_CI_FINAL_2026_08" in workflow
    assert "PAWDF_CI_XCB_RUNTIME_V2" in workflow
