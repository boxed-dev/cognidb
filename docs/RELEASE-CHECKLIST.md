# CogniDB 3.0.1 release checklist

Prep can be completed without credentials. **Publishing to PyPI and creating the GitHub Release require a human with tokens.**

Do **not** claim PyPI 3.0.1 is live until `pip index versions cognidb` (or the PyPI project page) shows `3.0.0`.

## 0. Preflight (local, no secrets)

```bash
cd /path/to/cognidb
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]" build twine

# Version consistency
python -c "import cognidb; assert cognidb.__version__ == '3.0.1'"
grep -E 'version|__version__' pyproject.toml cognidb/__init__.py cognidb/client.py setup.py

pytest -q
python examples/sqlite_offline_demo.py

rm -rf dist/ build/ *.egg-info
python -m build
twine check dist/*
```

Expected artifacts:

- `dist/cognidb-3.0.1-py3-none-any.whl`
- `dist/cognidb-3.0.1.tar.gz`

## 1. Git tag + GitHub Release (human)

```bash
git status   # clean working tree on the release commit
git tag -a v3.0.1 -m "CogniDB 3.0.1"
git push origin HEAD
git push origin v3.0.1
```

Create the GitHub Release (UI or CLI):

```bash
gh release create v3.0.1 \
  dist/cognidb-3.0.1-py3-none-any.whl \
  dist/cognidb-3.0.1.tar.gz \
  --title "v3.0.1" \
  --notes-file CHANGELOG.md
```

Or paste the `## 3.0.1` section from `CHANGELOG.md` into the GitHub Release body.

## 2. PyPI upload (human + token)

Create an API token at https://pypi.org/manage/account/token/ (scope: project `cognidb` or entire account).

```bash
# Preferred: Trusted Publishing (OIDC) from GitHub Actions — configure on PyPI first.
# Manual upload:
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-AgEIcHlwaS5vcmc...   # full token string; never commit

twine upload dist/cognidb-3.0.1*
```

Test PyPI first (optional):

```bash
twine upload --repository testpypi dist/cognidb-3.0.1*
pip install -i https://test.pypi.org/simple/ cognidb==3.0.1
```

## 3. Post-publish smoke (clean venv)

```bash
python -m venv /tmp/cognidb-smoke && source /tmp/cognidb-smoke/bin/activate
pip install cognidb==3.0.1
python -c "import cognidb; assert cognidb.__version__ == '3.0.1'"
# Copy or clone examples/sqlite_offline_demo.py and run it
```

## 4. Honest status after this checklist

| Step | Status owner |
|---|---|
| Package builds; README/CHANGELOG accurate; community files | Maintainer prep (this doc) |
| Tag `v3.0.1` + GitHub Release | Human with `git`/`gh` access |
| `twine upload` to PyPI | Human with `__token__` |
| Update README “PyPI published” wording | After upload succeeds |

No PyPI or GitHub credentials are stored in this repository.
