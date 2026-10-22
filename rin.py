"""Run RIN without installing dependencies: python rin.py investigate CASE."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from rin.cli import main


if __name__ == "__main__":
    main()
