"""Build and validate fresh artifacts before an explicitly requested upload."""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", choices=["pypi", "testpypi"],
                        help="Upload to this repository after checking. Omit for a local check.")
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="pyserialtransfer-dist-") as directory:
        subprocess.run([sys.executable, "-m", "build", "--outdir", directory, str(ROOT)],
                       check=True)
        wheels = list(Path(directory).glob("*.whl"))
        sources = list(Path(directory).glob("*.tar.gz"))
        if len(wheels) != 1 or len(sources) != 1:
            raise RuntimeError("Expected exactly one wheel and one source distribution")
        artifacts = [str(wheels[0]), str(sources[0])]
        twine = [sys.executable, "-m", "twine"]
        subprocess.run(twine + ["check", "--strict"] + artifacts, check=True)
        if args.repository:
            subprocess.run(twine + ["upload", "--repository", args.repository] + artifacts,
                           check=True)


if __name__ == "__main__":
    main()

