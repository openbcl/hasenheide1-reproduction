"""Stage the dashboard for publishing: copy dashboard/ to an output folder and add a
version query (?v=...) to every module, stylesheet, script and data path, so a
browser never mixes cached files of an earlier release with new ones (GitHub Pages
serves with a 10-minute cache). The repository's files stay unchanged; the GitHub Pages
workflow publishes the staged copy.

    python scripts/stage_dashboard.py --out _site --version 1a2b3c4 [--ref <commit>] [--preview <branch>]

--ref points the repository links at the commit the site was built from; --preview adds a
note to every page that the site is a preview built from that branch, not a release, and
asks search engines not to index it.

Fails if a rewrite rule no longer matches (the code changed) or if a relative module
import is left without the version afterwards.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "dashboard"
MARKER = ".staged-dashboard"                       # written into a staged folder; required to replace it

# (file glob, pattern, replacement, minimum number of matches over those files)
RULES = [
    ("index.html", r'(href|src)="((?:style\.css|app/[\w/]+\.js))"', r'\1="\2?v={v}"', 3),
    ("app/**/*.js", r'(from\s+")(\.{1,2}/[^"?]+\.js)(")', r"\1\2?v={v}\3", 10),
    ("app/main.js", r'(module:\s*")(\./views/[^"?]+\.js)(")', r"\1\2?v={v}\3", 7),
    ("app/main.js", r"fetch\(`data/\$\{name\}`\)", r"fetch(`data/${{name}}?v={v}`)", 1),
]


def cff_version() -> str:
    m = re.search(r"^version:\s*(\S+)\s*$", (ROOT.parent / "CITATION.cff").read_text(encoding="utf-8"), re.M)
    if not m:
        sys.exit("CITATION.cff has no version")
    return m.group(1)


def stage(out: Path, version: str, ref: str | None = None, preview: str | None = None) -> dict[str, int]:
    if not re.fullmatch(r"[0-9A-Za-z._-]{1,40}", version):
        sys.exit(f"invalid version {version!r}")
    if ref is not None and not re.fullmatch(r"[0-9a-f]{40}", ref):
        sys.exit(f"invalid ref {ref!r} (a full commit hash)")
    if preview is not None and not re.fullmatch(r"[0-9A-Za-z._/-]{1,100}", preview):
        sys.exit(f"invalid branch name {preview!r}")
    rules = list(RULES)
    if ref:   # repository links point at the commit the site was built from, not at a moving branch
        rules.append(("app/util.js", r'export const REPO_REF = "main";', f'export const REPO_REF = "{ref}";', 1))
    if preview:   # a site published from a branch says so on every page
        note = (f'<p class="preview-note" role="note">Preview, not a release: built from branch <code>{preview}</code>, '
                f"commit <code>{version}</code>. It shows the reproduction package's next, unreleased version; "
                f"the archived release is {cff_version()}.</p>")
        rules.append(("index.html", r"</header>\n", "</header>\n" + note.replace("\\", r"\\") + "\n", 1))
        rules.append(("index.html", r'(<meta name="referrer"[^>]*>\n)', r'\1<meta name="robots" content="noindex">\n', 1))
    # the output folder is replaced: only a new folder or one this script staged (marked by
    # MARKER), never the repository, the source, the working directory or one of their ancestors
    out, src, repo, cwd = out.resolve(), ROOT.resolve(), ROOT.parent.resolve(), Path.cwd().resolve()
    unsafe = out in (src, repo, cwd) or out in repo.parents or out in cwd.parents or src in out.parents or (out / ".git").exists()
    foreign = out.is_dir() and any(out.iterdir()) and not (out / MARKER).is_file()
    if unsafe or foreign:
        sys.exit(f"refusing to replace {out}: choose a new folder or one staged before")
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT, out, ignore=shutil.ignore_patterns("_*", "*.md"))   # no test pages, no notes
    (out / MARKER).write_text("staged by scripts/stage_dashboard.py; replaced by the next run\n", encoding="utf-8")
    counts = {}
    for glob, pat, rep, minimum in rules:
        n = 0
        for f in sorted(out.glob(glob)):
            text = f.read_text(encoding="utf-8")
            new, k = re.subn(pat, rep.format(v=version), text)
            if k:
                f.write_text(new, encoding="utf-8", newline="\n")
                n += k
        if n < minimum:
            sys.exit(f"rule {pat!r} on {glob} matched {n} times, expected at least {minimum}: update stage_dashboard.py")
        counts[f"{glob}: {pat}"] = n
    left = [f"{f.relative_to(out)}: {m}" for f in out.glob("app/**/*.js")
            for m in re.findall(r'from\s+"(\.{1,2}/[^"]+)"', f.read_text(encoding="utf-8")) if "?v=" not in m]
    if left:
        sys.exit("unversioned module imports: " + ", ".join(left))
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True, help="output folder (replaced)")
    ap.add_argument("--version", required=True, help="release identifier, e.g. the short commit hash")
    ap.add_argument("--ref", help="full commit hash for the repository links (default: they point at main)")
    ap.add_argument("--preview", metavar="BRANCH", help="mark every page as a preview built from this branch")
    args = ap.parse_args()
    counts = stage(args.out, args.version, args.ref, args.preview)
    print(f"staged dashboard/ -> {args.out} (version {args.version}); rewrites: " +
          ", ".join(str(n) for n in counts.values()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
