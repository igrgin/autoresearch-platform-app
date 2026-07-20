# PROTOTYPE — credible signing and update path

This is the release boundary proved or deliberately left credential-gated by the prototype.

## Proved by the spike

- Each target freezes Commander locally, renames it with the Rust host target triple, and lets Tauri bundle it inside the native application package.
- macOS, Windows, and Linux run the same headless handshake/request/stream/shutdown harness against their own frozen executable before packaging.
- Tauri produces host-native packages and updater payload signatures on all three CI hosts.
- The desktop shell, protocol version, and Commander executable share one application version and one package, so they update atomically.
- The renderer has only core Tauri IPC. It cannot invoke the shell plugin or choose an executable or command line.

## Production release credentials

Updater trust and platform identity trust are separate:

1. Generate one long-lived Tauri updater key offline. Back up the private key and password; embed its public key in `tauri.conf.json`; store the private key and password as protected release secrets. Every OS/architecture release job must use the same updater key.
2. macOS release jobs import a Developer ID Application certificate, sign the application and bundled Commander, then notarize and staple the app/DMG with App Store Connect issuer/key credentials.
3. Windows release jobs sign the application, bundled Commander, and NSIS/MSI with a trusted code-signing identity and timestamp service. The specific certificate provider is an operational choice, not an architecture choice.
4. Linux publishes AppImage plus a package format such as Debian. Tauri's updater signature authenticates the update payload; optional repository/GPG signing is distribution-channel policy.
5. A release action publishes packages, `.sig` files, and `latest.json` to one HTTPS endpoint such as GitHub Releases. Release jobs never publish the disposable prototype keys used by this branch's CI.

The prototype cannot prove Apple notarization or Windows reputation without real organization credentials. That is a credential/provisioning gate, not an unresolved application architecture question.
