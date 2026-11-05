"""Checks the Xcode project customisation against a fake converter output
shaped like Apple's template."""

import plistlib

from surroundflix import xcode

VIEW_CONTROLLER = """import Cocoa
import SafariServices
import WebKit

let extensionBundleIdentifier = "io.example.Surroundflix.Extension"

class ViewController: NSViewController, WKNavigationDelegate, WKScriptMessageHandler {

    @IBOutlet var webView: WKWebView!

    override func viewDidLoad() {
        super.viewDidLoad()
        self.webView.navigationDelegate = self
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        SFSafariExtensionManager.getStateOfSafariExtension(withIdentifier: extensionBundleIdentifier) { (state, error) in
        }
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
    }

}
"""


def make_project(tmp_path):
    app = tmp_path / "Surroundflix" / "Surroundflix"
    (app / "Resources" / "Base.lproj").mkdir(parents=True)
    (app / "Resources" / "Base.lproj" / "Main.html").write_text("<html>apple</html>")
    (app / "Resources" / "Style.css").write_text("/* apple */")
    (app / "Resources" / "Script.js").write_text("// apple")
    (app / "Resources" / "Icon.png").write_bytes(b"png")
    (app / "ViewController.swift").write_text(VIEW_CONTROLLER)
    (app / "Base.lproj").mkdir()
    (app / "Base.lproj" / "Main.storyboard").write_text(STORYBOARD)
    with (app / "Surroundflix.entitlements").open("wb") as fh:
        plistlib.dump({"com.apple.security.app-sandbox": True}, fh)

    ext = tmp_path / "Surroundflix" / "Surroundflix Extension"
    ext.mkdir(parents=True)
    with (ext / "Surroundflix Extension.entitlements").open("wb") as fh:
        plistlib.dump({"com.apple.security.app-sandbox": True}, fh)
    return tmp_path, app, ext


def test_customize_project(tmp_path):
    root, app, ext = make_project(tmp_path)
    notes = xcode.customize_project(root)
    assert not [n for n in notes if n.startswith("warning")], notes

    html = (app / "Resources" / "Base.lproj" / "Main.html").read_text()
    assert (
        'href="../Style.css"' in html
        and 'src="../Script.js"' in html
        and 'src="../Icon.png"' in html
    )
    script = (app / "Resources" / "Script.js").read_text()
    assert "pickLang" in script and "window.show" in script and "__SURROUNDFLIX" not in script

    swift = (app / "ViewController.swift").read_text()
    assert swift.count(xcode.LANG_MARKER) == 1 and swift.count(xcode.LINK_MARKER) == 1
    assert swift.rstrip().endswith("}")
    assert swift.index(xcode.LANG_MARKER) > swift.index("didFinish navigation")

    with (app / "Surroundflix.entitlements").open("rb") as fh:
        assert plistlib.load(fh)["com.apple.security.network.client"] is True
    with (ext / "Surroundflix Extension.entitlements").open("rb") as fh:
        assert "com.apple.security.network.client" not in plistlib.load(fh)


def test_customize_is_idempotent(tmp_path):
    root, app, _ = make_project(tmp_path)
    xcode.customize_project(root)
    first = (app / "ViewController.swift").read_text()
    notes = xcode.customize_project(root)
    assert (app / "ViewController.swift").read_text() == first
    assert not any("patched" in n or "network" in n for n in notes)


def test_missing_files_only_warn(tmp_path):
    notes = xcode.customize_project(tmp_path)
    assert all(n.startswith("warning") for n in notes)


XCPROJ = """{
  "targets": [
    {
      "name": "Surroundflix",
      "build-settings": {
        "ENABLE_APP_SANDBOX": "YES",
        "ENABLE_OUTGOING_NETWORK_CONNECTIONS": "YES",
        "PRODUCT_BUNDLE_IDENTIFIER": "io.github.anzouk.Surroundflix",
      },
    }, {
      "name": "Surroundflix Extension",
      "build-settings": {
        "PRODUCT_BUNDLE_IDENTIFIER": "io.github.anzouk.surroundflix.Extension",
      },
    },
  ],
}
"""


def test_new_project_format_gets_matching_bundle_ids(tmp_path):
    root, app, _ = make_project(tmp_path)
    (app / "Surroundflix.entitlements").unlink()
    proj = root / "Surroundflix" / "Surroundflix.xcodeproj"
    proj.mkdir()
    (proj / "project.xcproj").write_text(XCPROJ)
    swift = app / "ViewController.swift"
    swift.write_text(
        swift.read_text().replace(
            "io.example.Surroundflix.Extension", "io.github.anzouk.surroundflix.Extension"
        )
    )

    notes = xcode.customize_project(root)
    text = (proj / "project.xcproj").read_text()
    assert '"PRODUCT_BUNDLE_IDENTIFIER": "io.github.anzouk.Surroundflix.Extension"' in text
    assert '"io.github.anzouk.Surroundflix.Extension"' in swift.read_text()
    assert "network access already enabled in the build settings" in notes
    assert not [n for n in notes if n.startswith("warning")], notes
    # Running it again changes nothing.
    assert not [n for n in xcode.customize_project(root) if "bundle identifier" in n]


def test_old_project_format_gets_matching_bundle_ids(tmp_path):
    root, app, _ = make_project(tmp_path)
    proj = root / "Surroundflix" / "Surroundflix.xcodeproj"
    proj.mkdir()
    (proj / "project.pbxproj").write_text(
        "PRODUCT_BUNDLE_IDENTIFIER = io.github.anzouk.Surroundflix;\n"
        "PRODUCT_BUNDLE_IDENTIFIER = io.github.anzouk.surroundflix.Extension;\n"
    )
    xcode.customize_project(root)
    assert "io.github.anzouk.Surroundflix.Extension;" in (proj / "project.pbxproj").read_text()


STORYBOARD = """<window key="window" title="Surroundflix" id="IQv-IB-iLA">
    <windowStyleMask key="styleMask" titled="YES" closable="YES"/>
    <rect key="contentRect" x="196" y="240" width="425" height="325"/>
    <rect key="screenRect" x="0.0" y="0.0" width="1680" height="1027"/>
</window>
<viewController id="XfG-lQ-9wD" customClass="ViewController">
    <view key="view"><rect key="frame" x="0.0" y="0.0" width="425" height="325"/>
        <wkWebView><rect key="frame" x="0.0" y="0.0" width="425" height="325"/></wkWebView>
    </view>
</viewController>"""


def test_storyboard_window_becomes_resizable():
    out = xcode.patch_storyboard_source(STORYBOARD)
    assert 'titled="YES" closable="YES" miniaturizable="YES" resizable="YES"' in out
    w, h = xcode.WINDOW_SIZE
    assert out.count(f'width="{w}" height="{h}"') == 3
    assert 'width="1680" height="1027"' in out  # the screen rect is left alone
    assert xcode.patch_storyboard_source(out) == out


def test_app_stays_open_after_opening_safari_settings():
    src = """SFSafariApplication.showPreferencesForExtension(withIdentifier: id) { error in
        DispatchQueue.main.async {
            NSApplication.shared.terminate(nil)
        }
    }
}
"""
    out = xcode.patch_view_controller_source(src)
    assert "terminate" not in out
    assert xcode.KEEP_OPEN_MARKER in out
    assert xcode.patch_view_controller_source(out) == out


def test_customize_patches_the_storyboard(tmp_path):
    root, _, _ = make_project(tmp_path)
    notes = xcode.customize_project(root)
    assert any(n.startswith("window made resizable") for n in notes)
