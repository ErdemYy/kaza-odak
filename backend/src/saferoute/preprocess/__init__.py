"""Faz 2: veri ön işleme, öznitelik mühendisliği ve öznitelik seçimi.

Katmanlar (ham veri asla değiştirilmez):
  raw       data/raw/<dataset>/<snapshot>/            indirildiği gibi, salt-okunur
  interim   data/interim/<dataset>/<snapshot>/         türleri doğrulanmış, standartlaştırılmış
  processed data/processed/<dataset>/<snapshot>/       bayraklı, zenginleştirilmiş, tüm satırlar
  features  data/processed/<dataset>/<snapshot>/features/  algoritmalara özel matrisler
"""
