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
