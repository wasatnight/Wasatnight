# Setup notes

This folder is ready to become the public profile repository `wasatnight/wasatnight`.

## Publish

1. Create a public GitHub repository named exactly `wasatnight` under the `wasatnight` account.
2. Upload the contents of this folder without adding another nested directory.
3. Keep the default branch named `main`.
4. Open the Actions tab once and run **Update contribution graphic** manually to verify permissions and output.

## Links still to verify

The README intentionally does not guess public URLs. Add the verified portfolio and LinkedIn URLs to the `./connect` line in `README.md` after they are available.

## Local validation

```powershell
python scripts/generate_contributions.py --username wasatnight --output assets/contributions.svg
```

The generator uses Python's standard library only. It fetches GitHub's public contribution page and writes a self-hosted SVG; no token, package installation, or third-party statistics service is required.
