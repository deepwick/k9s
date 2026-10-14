import shutil
from pathlib import Path

import pytest
import yaml

from deepwick_spec.ansi import runs
from deepwick_spec.check_port import check_port
from deepwick_spec.color import contrast_ratio
from deepwick_spec.palette import load_palette
from deepwick_spec.tui import capture, tmux_available

REPO = Path(__file__).resolve().parents[1]
PALETTE = load_palette()
C = PALETTE.colors


def isolated_env(tmp_path, **extra):
    dirs = {"HOME": tmp_path / "home"}
    for kind in ("CONFIG", "DATA", "STATE", "CACHE"):
        dirs[f"XDG_{kind}_HOME"] = tmp_path / kind.lower()
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    env = {key: str(path) for key, path in dirs.items()}
    env.update(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
    env.update({key: str(value) for key, value in extra.items()})
    return env


SKIN = REPO / "deepwick.yaml"
SECTIONS = {"body", "prompt", "info", "help", "dialog", "frame", "views"}
EXPECTED = {
    ("body", "fgColor"): "foreground", ("body", "bgColor"): "background", ("body", "logoColor"): "blue",
    ("frame", "border", "fgColor"): "overlay", ("frame", "border", "focusColor"): "blue",
    ("frame", "crumbs", "fgColor"): "background", ("frame", "crumbs", "bgColor"): "blue",
    ("frame", "crumbs", "activeColor"): "lightBlue",
    ("frame", "menu", "keyColor"): "blue", ("frame", "menu", "numKeyColor"): "magenta",
    ("frame", "status", "newColor"): "foreground", ("frame", "status", "modifyColor"): "blue",
    ("frame", "status", "addColor"): "green", ("frame", "status", "pendingColor"): "yellow",
    ("frame", "status", "errorColor"): "red", ("frame", "status", "killColor"): "red",
    ("frame", "status", "completedColor"): "muted",
    ("frame", "title", "fgColor"): "foreground", ("frame", "title", "highlightColor"): "blue",
    ("views", "table", "cursorBgColor"): "selection", ("views", "table", "header", "fgColor"): "foreground",
    ("views", "yaml", "keyColor"): "lightBlue", ("views", "yaml", "valueColor"): "orange",
}


def skin():
    assert SKIN.is_file(), "deepwick.yaml missing"
    return yaml.safe_load(SKIN.read_text(encoding="utf-8"))["k9s"]


def test_only_known_sections():
    assert set(skin()) == SECTIONS


def test_role_colors():
    s = skin()
    for path, color in EXPECTED.items():
        node = s
        for key in path:
            node = node[key]
        assert node == C[color], path


def test_cursor_text_readable_on_every_row_color():
    # k9s draws the cursor row as cursorFgColor on the row's status color, not on cursorBgColor.
    s = skin()
    cursor_fg = s["views"]["table"]["cursorFgColor"]
    for key, color in s["frame"]["status"].items():
        assert contrast_ratio(cursor_fg, color) >= 4.5, key


@pytest.mark.skipif(not (tmux_available() and shutil.which("k9s")), reason="requires tmux and k9s")
def test_k9s_renders_skin_without_cluster(tmp_path):
    env = isolated_env(tmp_path)
    config = tmp_path / "k9s"
    (config / "skins").mkdir(parents=True)
    shutil.copy(SKIN, config / "skins" / "deepwick.yaml")
    (config / "config.yaml").write_text("k9s:\n  skipLatestRevCheck: true\n  ui:\n    skin: deepwick\n")
    kubeconfig = tmp_path / "kubeconfig"
    kubeconfig.write_text("apiVersion: v1\nkind: Config\nclusters: []\ncontexts: []\nusers: []\n")
    env.update(K9S_CONFIG_DIR=str(config), K9S_LOGS_DIR=str(tmp_path / "logs"), KUBECONFIG=str(kubeconfig))
    # Inside tmux, k9s rounds skin colors to the 256-color palette; outside it (as in a real terminal) it uses 24-bit.
    text = capture("env -u TMUX TERM=xterm-256color k9s", env, size=(120, 30), wait_for="contexts", timeout=25)
    styles = [s for _, s in runs(text)]
    assert any(s["bg"] == C["background"].lower() for s in styles)
    assert any(s["fg"] == C["blue"].lower() for s in styles)
    assert any(s["bg"] == C["lightBlue"].lower() for s in styles)


def test_port_conventions():
    assert check_port(REPO, PALETTE.allowed_hex()) == []
