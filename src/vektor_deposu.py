# Vektor deposu soyutlamasi: ayni arayuzle iki arka uc (Karar 13).
#
#   TamAramaDeposu : mevcut yontem; tum vektorlerle tam (kaba kuvvet, flat) kosinus arama, GPU/torch.
#   ChromaDeposu   : Chroma vektor veritabani (HNSW, kalici); yaklasik arama + metadata filtresi.
#
# Arayuz (ikisi icin ayni):
#   ara(q, k, doc=None) -> [chunk_id, ...]   q: tek sorgu vektoru (L2 normalize, float32)
#                                            doc verilirse sadece o belgenin chunk'lari (tek belge uzayi)
#
# NEDEN SOYUTLAMA: final RAG hatti hangi arka ucun kullanildigini bilmesin; Deney 6 dogrulamasi
# gecerse Chroma, gecmezse tam arama kullanilir (ya da ileride baska bir DB, ornegin Qdrant).
#
# TUZAK (dogrulandi): Chroma koleksiyonunda varsayilan bir gomme fonksiyonu vardir (kucuk ONNX modeli).
# Sorgu METINLE yapilirsa Chroma kendi modeliyle gomer ve bizim e5 vektorlerimizle uyumsuz sonuc verir.
# Bu sinif embedding_function=None ile olusturulur ve yalnizca HAZIR VEKTORLE arar.
import json
import time
from pathlib import Path

import numpy as np

KOK = Path(__file__).resolve().parent.parent
CHROMA_YOLU = KOK / "data" / "islenmis" / "chroma"
PARTI = 5000  # Chroma'nin en buyuk toplu ekleme siniri 5461 (get_max_batch_size)


class TamAramaDeposu:
    def __init__(self, emb_yolu, chunks_yolu, cihaz="cuda"):
        import torch
        self.torch = torch
        self.cihaz = cihaz
        self.E = torch.from_numpy(np.load(emb_yolu)).to(cihaz)  # (N, d) fp16
        self.idler, self.belgeler = [], []
        with open(chunks_yolu, encoding="utf-8") as f:
            for satir in f:
                c = json.loads(satir)
                self.idler.append(c["chunk_id"])
                self.belgeler.append(c["doc"])
        self.belge_no = {b: i for i, b in enumerate(sorted(set(self.belgeler)))}
        self.belge_idx = torch.tensor([self.belge_no[b] for b in self.belgeler], device=cihaz)

    def ara(self, q, k, doc=None):
        torch = self.torch
        s = (torch.from_numpy(q).to(self.cihaz).half() @ self.E.T).float()
        if doc is not None:
            maske = self.belge_idx == self.belge_no[doc]
            k = min(k, int(maske.sum()))  # belgede k'dan az chunk varsa onlarin hepsi
            s = torch.where(maske, s, torch.tensor(-1e9, device=self.cihaz))
        return [self.idler[j] for j in torch.topk(s, k).indices.tolist()]


class ChromaDeposu:
    def __init__(self, yol=CHROMA_YOLU, ad="chunks_e5_c200"):
        import chromadb
        self.istemci = chromadb.PersistentClient(path=str(yol))
        self.ad = ad
        self.koleksiyon = None

    def ac(self):
        # mevcut koleksiyonu acar; yoksa None
        try:
            self.koleksiyon = self.istemci.get_collection(self.ad, embedding_function=None)
        except Exception:
            self.koleksiyon = None
        return self.koleksiyon

    def kur(self, emb_yolu, chunks_yolu, ef_construction=100, max_neighbors=16, ef_search=100):
        # Idempotent: koleksiyon varsa ve eleman sayisi dogruysa tekrar kurmaz.
        # Doner: kurulum suresi (sn) ya da None (zaten vardi).
        E = np.load(emb_yolu)
        mevcut = self.ac()
        if mevcut is not None and mevcut.count() == len(E):
            return None
        if mevcut is not None:
            self.istemci.delete_collection(self.ad)
        t0 = time.time()
        self.koleksiyon = self.istemci.create_collection(
            self.ad, embedding_function=None,
            configuration={"hnsw": {"space": "cosine", "ef_construction": ef_construction,
                                    "max_neighbors": max_neighbors, "ef_search": ef_search}})
        idler, belge, sayfa, metin = [], [], [], []
        with open(chunks_yolu, encoding="utf-8") as f:
            for satir in f:
                c = json.loads(satir)
                idler.append(c["chunk_id"])
                belge.append(c["doc"])
                sayfa.append(c["sayfa_idx"])
                metin.append(c["metin"])
        assert len(idler) == len(E), "chunk sayisi ile gomu sayisi uyusmuyor"
        for bas in range(0, len(idler), PARTI):
            son = bas + PARTI
            self.koleksiyon.add(
                ids=idler[bas:son], embeddings=E[bas:son].astype(np.float32),
                metadatas=[{"doc": b, "sayfa_idx": p} for b, p in zip(belge[bas:son], sayfa[bas:son])],
                documents=metin[bas:son])
        return time.time() - t0

    def ef_search_ayarla(self, ef):
        # indeksi yeniden kurmadan sorgu zamani parametresini degistirir (dogrulandi)
        self.koleksiyon.modify(configuration={"hnsw": {"ef_search": ef}})

    def ara(self, q, k, doc=None):
        if doc is None:
            r = self.koleksiyon.query(query_embeddings=[q], n_results=k, include=["distances"])
        else:
            r = self.koleksiyon.query(query_embeddings=[q], n_results=k, where={"doc": doc}, include=["distances"])
        return r["ids"][0]
