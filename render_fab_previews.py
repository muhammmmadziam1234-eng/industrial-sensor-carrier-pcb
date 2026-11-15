"""Make README previews from the files that leave the project, not from the generator's model.

media/gerber-top.svg and media/gerber-bottom.svg are drawn by gerbonara from fab/gerbers and fab/drill, so they show
what a fabricator would see. media/schematic-N.png are the pages of reports/meridian-schematic.pdf (needs pymupdf:
pip install -r requirements-previews.txt).
"""
import warnings
from pathlib import Path

from gerbonara import LayerStack

ROOT = Path(__file__).parent
MEDIA = ROOT / "media"


def gerber_views():
    warnings.simplefilter("ignore")
    stack = LayerStack.open(ROOT / "fab")
    for side in ("top", "bottom"):
        target = MEDIA / f"gerber-{side}.svg"
        target.write_text(str(stack.to_pretty_svg(side=side)), encoding="utf-8")
        print(f"wrote {target.relative_to(ROOT)}")


def schematic_pages():
    import pymupdf

    with pymupdf.open(ROOT / "reports" / "meridian-schematic.pdf") as pdf:
        for number, page in enumerate(pdf, start=1):
            target = MEDIA / f"schematic-{number}.png"
            page.get_pixmap(dpi=130).save(target)
            print(f"wrote {target.relative_to(ROOT)}")


if __name__ == "__main__":
    MEDIA.mkdir(exist_ok=True)
    gerber_views()
    try:
        schematic_pages()
    except ModuleNotFoundError:
        print("pymupdf is not installed: schematic pages skipped (pip install -r requirements-previews.txt)")
