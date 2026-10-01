# Belge kunyesi: her chunk'in basina eklenen "bu chunk hangi belgeden" bilgisi (Deney 1).
#
# Neden: chunk'lar PDF sayfalarindan geliyor ve sayfa metni sirket adini, yili, belge turunu
# cogu zaman icermiyor. Sorular ise "Coca-Cola FY2022 ..." gibi bunlari soyluyor. Kunye bu
# bilgiyi chunk metnine tasir.
#
# Kunye SADECE belge meta verisinden (belgeler.jsonl: sirket, tur, donem) ve belge adindan
# (ceyrek, tarih) uretilir; soru bilgisi kullanilmaz. Format tek ve sonuclara bakmadan sabitlendi.
#
# Ornekler:
#   "3M. 10-K annual report, fiscal year 2018."
#   "3M. 10-Q quarterly report, 2023 Q2."
#   "Amcor. 8-K current report, dated 2022-04-26."
#   "Best Buy. Earnings release, 2024 Q2."
import json
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
BELGELER = KOK / "data" / "ham" / "financebench" / "belgeler.jsonl"

TUR = {
    "10k": "10-K annual report",
    "10q": "10-Q quarterly report",
    "8k": "8-K current report",
    "Earnings": "Earnings release",
    "10k_annualreport": "Annual report",
}


def kunye_sozlugu() -> dict:
    # doc_name -> kunye metni
    sonuc = {}
    with open(BELGELER, encoding="utf-8") as f:
        for satir in f:
            if not satir.strip():
                continue
            b = json.loads(satir)
            ad = b["doc_name"]
            ceyrek = re.search(r"_(\d{4})Q(\d)_", ad)
            tarih = re.search(r"dated-(\d{4}-\d{2}-\d{2})", ad)
            if ceyrek:
                donem = f"{ceyrek.group(1)} Q{ceyrek.group(2)}"
            elif tarih:
                donem = f"dated {tarih.group(1)}"
            elif b["doc_type"] == "10k":
                donem = f"fiscal year {b['doc_period']}"
            else:
                donem = str(b["doc_period"])
            sonuc[ad] = f"{b['company']}. {TUR[b['doc_type']]}, {donem}."
    return sonuc


if __name__ == "__main__":
    k = kunye_sozlugu()
    print(len(k), "belge")
    for ad in ("3M_2018_10K", "3M_2023Q2_10Q", "AMCOR_2022_8K_dated-2022-04-26", "BESTBUY_2024Q2_EARNINGS", "AMD_2022_annualreport"):
        print(f"  {ad:34s} -> {k.get(ad)}")
