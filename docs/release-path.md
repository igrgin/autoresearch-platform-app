# PROTOTYPE — credible signing and update path

This is the release boundary proved or deliberately left credential-gated by the prototype.

## Proved by the spike on packaged macOS

- Commander freezes locally, is renamed with the Rust host target triple, and is bundled by Tauri inside the native application package.
- The packaged application launches Commander, completes its version handshake, correlates a ping response, preserves ordered telemetry, detects a simulated crash, restarts, exits gracefully, force-kills, and cleans up on application exit.
- Tauri produces a macOS app, updater archive, and updater payload signature.
- The desktop shell, protocol version, and Commander executable share one application version and one package, so they update atomically.
- The renderer has only core Tauri IPC. It cannot invoke the shell plugin or choose an executable or command line.

## Defined but not yet proved on Windows and Linux

`docs/prototype-tauri-sidecar.workflow.yml` contains the host-native matrix. The repository's current automation credentials cannot create files under `.github/workflows`, so those jobs have not run. A maintainer must activate the recipe before this ticket can claim three-platform reliability.

## Production release credentials

Updater trust and platform identity trust are separate:

1. Generate one long-lived Tauri updater key offline. Back up the private key and password; embed its public key in `tauri.conf.json`; store the private key and password as protected release secrets. Every OS/architecture release job must use the same updater key.
2. macOS release jobs import a Developer ID Application certificate, sign the application and bundled Commander, then notarize and staple the app/DMG with App Store Connect issuer/key credentials.
3. Windows release jobs sign the application, bundled Commander, and NSIS/MSI with a trusted code-signing identity and timestamp service. The specific certificate provider is an operational choice, not an architecture choice.
4. Linux publishes AppImage plus a package format such as Debian. Tauri's updater signature authenticates the update payload; optional repository/GPG signing is distribution-channel policy.
5. A release action publishes packages, `.sig` files, and `latest.json` to one HTTPS endpoint such as GitHub Releases. Release jobs never publish the disposable prototype keys used by this branch's CI.

The prototype cannot prove Apple notarization or Windows reputation without real organization credentials. That is a credential/provisioning gate, not an unresolved application architecture question.
