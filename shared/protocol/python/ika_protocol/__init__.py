"""Bekçi kartı protokolünün Python tarafı.

    messages  mesaj tanımları. messages.yaml'dan ÜRETİLİR, elle düzenlenmez.
    frame     çerçeve katmanı (COBS, CRC, HMAC). Elle yazılan referans uygulama.

Bu dosya bilerek hiçbir şeyi içe aktarmaz: tools/gen_protocol.py, test
vektörlerini üretirken messages modülünü bellekten yükler.
"""
