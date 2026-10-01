# hibrit.py'deki RRF birlestirmesinin dogrulugunu sinar (elle hesaplanmis ornek).
#
# Kullanim: python tests/test_hibrit.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import hibrit  # noqa: E402


def main():
    # iki liste: A ilk 'x', B ilk 'y'. x: 1/61 + 1/62, y: 1/62 + 1/61 -> esit; sonra z (tek listede 3.) ve w.
    a = {"q": ["x", "y", "z"]}
    b = {"q": ["y", "x", "w"]}
    sonuc = hibrit.rrf([a, b], ["q"])["q"]
    assert set(sonuc[:2]) == {"x", "y"}, sonuc            # iki ortak aday en ustte
    assert sonuc[:2] == ["x", "y"], sonuc                  # esitlikte chunk_id'ye gore deterministik
    assert sonuc[2:] == ["w", "z"], sonuc                  # 3. siradakiler esit, id sirasi
    # tek liste: sira korunur
    assert hibrit.rrf([{"q": ["c", "a", "b"]}], ["q"])["q"] == ["c", "a", "b"]
    # bir listede olmayan aday, iki listede de olan her adayin altinda kalir
    s = hibrit.rrf([{"q": ["u", "v"]}, {"q": ["v", "t"]}], ["q"])["q"]
    assert s[0] == "v" or s[0] == "u", s
    assert s[-1] == "t" or s[-1] == "u", s
    print("TUM TESTLER GECTI")


if __name__ == "__main__":
    main()
