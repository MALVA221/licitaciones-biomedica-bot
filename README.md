# 🏥 Bot de Licitaciones Biomédicas (Región Noroeste y Occidente)

Bot automatizado que vigila las compras públicas de **Sinaloa, Sonora, Durango, Nayarit y Jalisco** a través de la API abierta de [LicitIA](https://licitia.com.mx) (alimentada de CompraNet / ComprasMX) y envía alertas diarias a Telegram con **Fichas Técnicas en PDF digeridas**.

---

## 📍 Estados Monitoreados
* 📍 **Sinaloa** (Culiacán, Mazatlán, Los Mochis, IMSS, ISSSTE, SSA Sinaloa)
* 🌵 **Sonora** (Hermosillo, Ciudad Obregón, Nogales, IMSS-Bienestar Sonora, SSA Sonora)
* 🦂 **Durango** (Durango, Gómez Palacio, Lerdo, IMSS Durango, SSA Durango)
* 🌊 **Nayarit** (Tepic, Bahía de Banderas, IMSS-Bienestar Nayarit, SSN)
* ⭐ **Jalisco** (Guadalajara, Zapopan, Puerto Vallarta, SSJalisco, ISSSTE Jalisco)

---

## 🎯 Especialidades Biomédicas Cubiertas
* Mantenimiento preventivo y correctivo de equipo médico e instrumental.
* Suministro y adquisición de equipo médico y mobiliario clínico.
* Imagenología, ultrasonido, rayos X, tomografía, mastografía, resonancia.
* Instrumental, consumibles, reactivos, material de curación y laboratorio.
* Servicios médicos integrales (hemodiálisis, anestesia, cirugía de mínima invasión, osteosíntesis).

---

## 🚀 Características
* **Fichas Técnicas en PDF automáticas:** Cada alerta adjunta un PDF con el resumen ejecutivo, claves CUCOP, anexos de la convocatoria y la **empresa ganadora / monto adjudicado** (en procedimientos concluidos).
* **Caché anti-duplicados:** Registra los IDs notificados en `notified_ids.json` para evitar spam.
* **100% Serverless y Gratis:** Corre diario en GitHub Actions sin necesidad de mantener un servidor prendido.

---

## ⚙️ Configuración y Ejecución Local
```bash
# Validar funcionamiento
python3 bot_licitaciones.py --self-check

# Ejecutar escaneo
python3 bot_licitaciones.py
```
