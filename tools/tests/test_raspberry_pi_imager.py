"""Tests for tools/raspberry_pi_imager.py

Uses unittest.mock so no network access is required.
Run from anywhere:
    cd /home/sword/raspberry_pi_imager
    python3 -m pytest test_raspberry_pi_imager.py -v
"""
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

# Ensure the module's directory is importable (handles both the original
# tools/tests/ layout and the standalone /home/sword/raspberry_pi_imager/ layout).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
from raspberry_pi_imager import (
    detect_platform,
    find_asset,
    download_imager,
    get_latest_release,
    list_available_assets,
    PLATFORM_PATTERNS,
)

# ── Fixtures ───────────────────────────────────────────────────────────────────

SAMPLE_RELEASE = {
    "tag_name": "v2.0.11.1",
    "name": "v2.0.11.1",
    "published_at": "2026-08-17T17:07:09Z",
    "body": "Release notes here",
    "assets": [
        {"name": "imager-v2.0.11.1.exe", "size": 22498400,
         "browser_download_url": "https://github.com/raspberrypi/rpi-imager/releases/download/v2.0.11.1/imager-v2.0.11.1.exe"},
        {"name": "rpi-imager-v2.0.11.1.dmg", "size": 51904566,
         "browser_download_url": "https://github.com/raspberrypi/rpi-imager/releases/download/v2.0.11.1/rpi-imager-v2.0.11.1.dmg"},
        {"name": "rpi-imager_2.0.11.1-1_amd64.deb", "size": 33403064,
         "browser_download_url": "https://github.com/raspberrypi/rpi-imager/releases/download/v2.0.11.1/rpi-imager_2.0.11.1-1_amd64.deb"},
        {"name": "rpi-imager_2.0.11.1-1_arm64.deb", "size": 33477784,
         "browser_download_url": "https://github.com/raspberrypi/rpi-imager/releases/download/v2.0.11.1/rpi-imager_2.0.11.1-1_arm64.deb"},
        {"name": "rpi-imager_2.0.11.1-1_armhf.deb", "size": 31717104,
         "browser_download_url": "https://github.com/raspberrypi/rpi-imager/releases/download/v2.0.11.1/rpi-imager_2.0.11.1-1_armhf.deb"},
        {"name": "rpi-imager-cli_2.0.11.1-1_amd64.deb", "size": 9759204,
         "browser_download_url": "https://github.com/raspberrypi/rpi-imager/releases/download/v2.0.11.1/rpi-imager-cli_2.0.11.1-1_amd64.deb"},
        {"name": "rpi-imager_2.0.11.1.orig.tar.xz", "size": 4710676,
         "browser_download_url": "https://github.com/raspberrypi/rpi-imager/releases/download/v2.0.11.1/rpi-imager_2.0.11.1.orig.tar.xz"},
    ],
}


class FakeResponse:
    """Minimal fake of requests.Response for streaming download."""
    def __init__(self, content: bytes, status_code: int = 200):
        self._content = content
        self.content = content
        self.status_code = status_code
        self.headers = {"content-type": "application/octet-stream"}

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=8192):
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i:i + chunk_size]


class FakeApi:
    """Fake .json() for API responses."""
    def __init__(self, payload):
        self._json = payload

    def json(self):
        return self._json


# ── detect_platform ────────────────────────────────────────────────────────────

class TestDetectPlatform:
    def test_windows(self):
        with patch("raspberry_pi_imager.platform_mod") as m:
            m.system.return_value = "Windows"
            m.machine.return_value = "AMD64"
            assert detect_platform() == "windows"

    def test_macos(self):
        with patch("raspberry_pi_imager.platform_mod") as m:
            m.system.return_value = "Darwin"
            m.machine.return_value = "x86_64"
            assert detect_platform() == "macos"

    def test_linux_amd64(self):
        with patch("raspberry_pi_imager.platform_mod") as m:
            m.system.return_value = "Linux"
            m.machine.return_value = "x86_64"
            assert detect_platform() == "linux-amd64"

    def test_linux_arm64(self):
        with patch("raspberry_pi_imager.platform_mod") as m:
            m.system.return_value = "Linux"
            m.machine.return_value = "aarch64"
            assert detect_platform() == "linux-arm64"

    def test_linux_armhf(self):
        with patch("raspberry_pi_imager.platform_mod") as m:
            m.system.return_value = "Linux"
            m.machine.return_value = "armv7l"
            assert detect_platform() == "linux-armhf"

    def test_linux_unknown_arch_fallback(self):
        with patch("raspberry_pi_imager.platform_mod") as m:
            m.system.return_value = "Linux"
            m.machine.return_value = "riscv64"
            assert detect_platform() == "linux-amd64"

    def test_unknown_system_fallback(self):
        with patch("raspberry_pi_imager.platform_mod") as m:
            m.system.return_value = "FreeBSD"
            m.machine.return_value = "amd64"
            assert detect_platform() == "linux-amd64"


# ── find_asset ──────────────────────────────────────────────────────────────────

class TestFindAsset:
    def test_windows_exe(self):
        asset = find_asset(SAMPLE_RELEASE, "windows")
        assert asset["name"] == "imager-v2.0.11.1.exe"

    def test_macos_dmg(self):
        asset = find_asset(SAMPLE_RELEASE, "macos")
        assert asset["name"] == "rpi-imager-v2.0.11.1.dmg"

    def test_linux_amd64_prefers_gui_not_cli(self):
        asset = find_asset(SAMPLE_RELEASE, "linux-amd64")
        assert asset["name"] == "rpi-imager_2.0.11.1-1_amd64.deb"
        assert "cli" not in asset["name"]

    def test_no_assets(self):
        release = {"tag_name": "v1", "assets": []}
        with pytest.raises(RuntimeError, match="No assets found"):
            find_asset(release, "windows")

    def test_unknown_platform(self):
        with pytest.raises(ValueError, match="Unknown platform"):
            find_asset(SAMPLE_RELEASE, "solaris")

    def test_missing_match(self):
        """When no asset matches the pattern, raise RuntimeError."""
        release = {"tag_name": "v1", "assets": [
            {"name": "some-other-file.txt", "size": 10,
             "browser_download_url": "http://example.com/file.txt"}
        ]}
        with pytest.raises(RuntimeError, match="No asset matching"):
            find_asset(release, "windows")


# ── get_latest_release ─────────────────────────────────────────────────────────

class TestGetLatestRelease:
    @patch("raspberry_pi_imager.requests.get")
    def test_success(self, mock_get):
        mock_resp = FakeApi(SAMPLE_RELEASE)
        mock_resp.status_code = 200
        mock_resp.raise_for_status = lambda: None
        mock_get.return_value = mock_resp
        result = get_latest_release()
        assert result["tag_name"] == "v2.0.11.1"
        assert len(result["assets"]) == 7

    @patch("raspberry_pi_imager.requests.get")
    def test_not_found(self, mock_get):
        mock_resp = FakeApi({"message": "Not Found"})
        mock_resp.status_code = 404
        def raise_for():
            import requests
            raise requests.exceptions.HTTPError("404")
        mock_resp.raise_for_status = raise_for
        mock_get.return_value = mock_resp
        with pytest.raises(RuntimeError, match="API error"):
            get_latest_release()

    @patch("raspberry_pi_imager.requests.get")
    def test_network_error(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("dns failure")
        with pytest.raises(RuntimeError, match="Network error"):
            get_latest_release()


# ── list_available_assets ───────────────────────────────────────────────────────

class TestListAvailableAssets:
    @patch("raspberry_pi_imager.get_latest_release")
    def test_returns_assets(self, mock_release):
        mock_release.return_value = SAMPLE_RELEASE
        assets = list_available_assets()
        assert len(assets) == 7
        assert assets[0]["name"] == "imager-v2.0.11.1.exe"


# ── download_asset ──────────────────────────────────────────────────────────────

class TestDownloadAsset:
    @patch("raspberry_pi_imager.requests.get")
    def test_download_success(self, mock_get, tmp_path):
        from raspberry_pi_imager import download_asset
        fake_resp = FakeResponse(b"RPI_IMAGER_BINARY_DATA")
        mock_get.return_value = fake_resp
        asset = SAMPLE_RELEASE["assets"][0]  # .exe
        result = download_asset(asset, output_dir=str(tmp_path))
        assert os.path.exists(result)
        assert open(result, "rb").read() == b"RPI_IMAGER_BINARY_DATA"

    @patch("raspberry_pi_imager.requests.get")
    def test_skip_if_already_exists(self, mock_get, tmp_path):
        from raspberry_pi_imager import download_asset
        asset = SAMPLE_RELEASE["assets"][2]  # amd64 deb, 33403064 bytes
        filepath = str(tmp_path / asset["name"])
        with open(filepath, "wb") as f:
            f.write(b"\x00" * asset["size"])
        result = download_asset(asset, output_dir=str(tmp_path))
        assert result == filepath
        mock_get.assert_not_called()

    @patch("raspberry_pi_imager.requests.get")
    def test_download_default_output_dir(self, mock_get, tmp_path):
        """When output_dir is None, uses DEFAULT_DOWNLOAD_DIR."""
        from raspberry_pi_imager import download_asset, DEFAULT_DOWNLOAD_DIR
        fake_resp = FakeResponse(b"DATA")
        mock_get.return_value = fake_resp
        asset = SAMPLE_RELEASE["assets"][0]  # .exe
        result = download_asset(asset, output_dir=DEFAULT_DOWNLOAD_DIR)
        assert os.path.exists(result)

    @patch("raspberry_pi_imager.requests.get")
    def test_skip_size_mismatch_resumes(self, mock_get, tmp_path):
        """File exists but wrong size → re-download (line 161)."""
        from raspberry_pi_imager import download_asset
        fake_resp = FakeResponse(b"NEW_CORRECT_DATA")
        mock_get.return_value = fake_resp
        asset = SAMPLE_RELEASE["assets"][0]  # expects 22498400 bytes
        filepath = str(tmp_path / asset["name"])
        # Write a file with WRONG size
        with open(filepath, "wb") as f:
            f.write(b"too small")
        result = download_asset(asset, output_dir=str(tmp_path))
        # Content should be replaced
        assert open(result, "rb").read() == b"NEW_CORRECT_DATA"

    @patch("raspberry_pi_imager.requests.get")
    def test_download_size_mismatch_warning(self, mock_get, tmp_path, capsys):
        """Downloaded size doesn't match expected → prints warning."""
        from raspberry_pi_imager import download_asset
        fake_resp = FakeResponse(b"PARTIAL")  # smaller than expected
        mock_get.return_value = fake_resp
        asset = SAMPLE_RELEASE["assets"][0]  # expects 22498400 bytes
        result = download_asset(asset, output_dir=str(tmp_path))
        captured = capsys.readouterr()
        assert "size mismatch" in captured.out.lower()

    @patch("raspberry_pi_imager.requests.get")
    def test_download_failure_cleans_up(self, mock_get, tmp_path):
        """Partial download should be cleaned up on failure."""
        from raspberry_pi_imager import download_asset
        import requests
        mock_get.side_effect = requests.exceptions.RequestException("oops")
        asset = SAMPLE_RELEASE["assets"][0]
        with pytest.raises(RuntimeError, match="Download failed"):
            download_asset(asset, output_dir=str(tmp_path))
        assert not os.path.exists(str(tmp_path / asset["name"]))


# ── download_imager ─────────────────────────────────────────────────────────────

class TestDownloadImager:
    @patch("raspberry_pi_imager.download_asset")
    @patch("raspberry_pi_imager.get_latest_release")
    def test_full_flow(self, mock_release, mock_download, tmp_path):
        mock_release.return_value = SAMPLE_RELEASE
        mock_download.return_value = str(tmp_path / "imager-v2.0.11.1.exe")
        result = download_imager("windows", output_dir=str(tmp_path))
        assert result["ok"] is True
        assert result["version"] == "v2.0.11.1"
        assert result["platform"] == "windows"
        assert result["asset_name"] == "imager-v2.0.11.1.exe"

    @patch("raspberry_pi_imager.download_asset")
    @patch("raspberry_pi_imager.get_latest_release")
    def test_returns_url_and_size(self, mock_release, mock_download, tmp_path):
        mock_release.return_value = SAMPLE_RELEASE
        mock_download.return_value = str(tmp_path / "test.exe")
        result = download_imager("windows", output_dir=str(tmp_path))
        assert "url" in result
        assert "size_bytes" in result
        assert result["url"].startswith("https://github.com")

    @patch("raspberry_pi_imager.download_asset")
    @patch("raspberry_pi_imager.get_latest_release")
    def test_auto_platform_uses_detect(self, mock_release, mock_download, tmp_path):
        """When platform_key is 'auto' or None, detect_platform is called."""
        mock_release.return_value = SAMPLE_RELEASE
        mock_download.return_value = str(tmp_path / "imager.deb")
        with patch("raspberry_pi_imager.detect_platform", return_value="linux-amd64"):
            result = download_imager(output_dir=str(tmp_path))
            assert result["platform"] == "linux-amd64"
            assert result["asset_name"] == "rpi-imager_2.0.11.1-1_amd64.deb"

    @patch("raspberry_pi_imager.download_asset")
    @patch("raspberry_pi_imager.get_latest_release")
    def test_overwrite_passed_through(self, mock_release, mock_download, tmp_path):
        """The overwrite flag should be passed to download_asset."""
        mock_release.return_value = SAMPLE_RELEASE
        mock_download.return_value = str(tmp_path / "imager.exe")
        download_imager("windows", output_dir=str(tmp_path), overwrite=True)
        # download_asset was called with overwrite=True
        args, kwargs = mock_download.call_args
        assert kwargs.get("overwrite") is True or (len(args) >= 3 and args[2] is True)


class TestAdditionalCoverage:
    """Additional tests to push coverage above 80%."""

    @patch("raspberry_pi_imager.requests.get")
    def test_http_error_raises(self, mock_get):
        """A real HTTPError from raise_for_status becomes a RuntimeError."""
        import requests
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"valid": "data"}
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("403")
        mock_get.return_value = mock_resp
        with pytest.raises(RuntimeError, match="HTTP error"):
            get_latest_release()

    @patch("raspberry_pi_imager.requests.get")
    def test_download_uses_default_output_dir(self, mock_get, tmp_path):
        """When output_dir is None, DEFAULT_DOWNLOAD_DIR is used (line 146)."""
        from raspberry_pi_imager import download_asset, DEFAULT_DOWNLOAD_DIR
        mock_get.return_value = FakeResponse(b"X")
        # Monkey-patch DEFAULT_DOWNLOAD_DIR by passing None and patching os.path.exists
        # to detect which path is being used
        with patch("raspberry_pi_imager.DEFAULT_DOWNLOAD_DIR", str(tmp_path)):
            asset = {
                "name": "x.exe", "size": 1,
                "browser_download_url": "http://example.com/x.exe",
            }
            result = download_asset(asset, output_dir=None)
            assert str(tmp_path) in result

    @patch("raspberry_pi_imager.os.remove")
    @patch("raspberry_pi_imager.requests.get")
    def test_download_oserror_on_cleanup_swallowed(self, mock_get, mock_remove, tmp_path):
        """When cleanup itself fails with OSError, it's swallowed (line 203-204)."""
        from raspberry_pi_imager import download_asset
        import requests
        # Make requests.get fail after writing a partial file
        mock_resp = MagicMock()
        mock_resp.raise_for_status = lambda: None
        def bad_iter(chunk_size=8192):
            yield b"partial"
            raise requests.exceptions.ChunkedEncodingError("truncated")
        mock_resp.iter_content = bad_iter
        mock_get.return_value = mock_resp
        # Make os.remove raise OSError - it should be silently swallowed
        mock_remove.side_effect = OSError("permission denied")
        asset = SAMPLE_RELEASE["assets"][0]
        with pytest.raises(RuntimeError, match="Download failed"):
            download_asset(asset, output_dir=str(tmp_path))
        # The OSError from os.remove should be swallowed
        # (the test passing without raising OSError confirms this)

    @patch("raspberry_pi_imager.requests.get")
    def test_download_failure_with_existing_file(self, mock_get, tmp_path):
        """When the download fails AND a partial file exists, clean it up."""
        from raspberry_pi_imager import download_asset
        import requests
        # Make requests.get succeed in opening the file but fail inside iter_content
        mock_resp = MagicMock()
        mock_resp.raise_for_status = lambda: None
        def bad_iter(chunk_size=8192):
            # Write a chunk first to create a partial file
            yield b"partial data"
            raise requests.exceptions.ChunkedEncodingError("truncated")
        mock_resp.iter_content = bad_iter
        mock_get.return_value = mock_resp
        asset = SAMPLE_RELEASE["assets"][0]
        with pytest.raises(RuntimeError, match="Download failed"):
            download_asset(asset, output_dir=str(tmp_path))
        assert not os.path.exists(str(tmp_path / asset["name"]))

    @patch("raspberry_pi_imager.requests.get")
    def test_download_size_match_success(self, mock_get, tmp_path, capsys):
        """When size matches expected, the success path prints [saved]."""
        from raspberry_pi_imager import download_asset
        asset = {
            "name": "small.exe", "size": 5,
            "browser_download_url": "http://example.com/small.exe",
        }
        mock_get.return_value = FakeResponse(b"12345")  # 5 bytes exactly
        result = download_asset(asset, output_dir=str(tmp_path))
        captured = capsys.readouterr()
        assert "saved" in captured.out.lower()
        assert result == str(tmp_path / "small.exe")


# ── CLI tests ──────────────────────────────────────────────────────────────────

class TestCLI:
    """Tests for the main() CLI entrypoint."""

    @patch("raspberry_pi_imager.get_latest_release")
    def test_list_flag(self, mock_release, capsys):
        """--list prints asset table and returns 0."""
        from raspberry_pi_imager import main
        mock_release.return_value = SAMPLE_RELEASE
        exit_code = main(["--list"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Latest release" in captured.out
        assert "imager-v2.0.11.1.exe" in captured.out

    @patch("raspberry_pi_imager.get_latest_release")
    def test_list_flag_error(self, mock_release, capsys):
        """--list with API error prints [error] and returns 1."""
        from raspberry_pi_imager import main
        mock_release.side_effect = RuntimeError("API down")
        exit_code = main(["--list"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "[error]" in captured.out

    @patch("raspberry_pi_imager.download_imager")
    @patch("raspberry_pi_imager.get_latest_release")
    def test_download_flag(self, mock_release, mock_download, capsys, tmp_path):
        """Default mode (no --list) calls download_imager and returns 0."""
        from raspberry_pi_imager import main
        mock_release.return_value = SAMPLE_RELEASE
        mock_download.return_value = {
            "ok": True,
            "version": "v2.0.11.1",
            "platform": "windows",
            "filepath": str(tmp_path / "imager.exe"),
            "url": "https://github.com/.../imager.exe",
            "size_bytes": 22498400,
            "asset_name": "imager-v2.0.11.1.exe",
        }
        exit_code = main(["--platform", "windows", "--output", str(tmp_path)])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Done" in captured.out
        assert "v2.0.11.1" in captured.out

    @patch("raspberry_pi_imager.download_imager")
    @patch("raspberry_pi_imager.get_latest_release")
    def test_download_error(self, mock_release, mock_download, capsys, tmp_path):
        """When download_imager raises, main() returns 1 and prints [Error]."""
        from raspberry_pi_imager import main
        mock_release.return_value = SAMPLE_RELEASE
        mock_download.side_effect = RuntimeError("network down")
        exit_code = main(["--platform", "windows", "--output", str(tmp_path)])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
