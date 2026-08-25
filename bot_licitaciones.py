#!/usr/bin/env python3
"""
Bot de Alertas de Licitaciones Biomédicas con Ficha Técnica PDF y Objeto Completo
Región: Sinaloa, Sonora, Durango, Nayarit y Jalisco.
Fuente: API Abierta de LicitIA (https://api.licitia.com.mx/api/open/v1)
"""

import os
import sys
import time
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

# Configuración por variables de entorno con fallback
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8325404080:AAEkN_Hrhr55pPEdM5ZDJi6I-AL_SmYjk8w")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1344870675")
CACHE_FILE = os.path.join(os.path.dirname(__file__), "notified_ids.json")
PDF_DIR = os.path.join(os.path.dirname(__file__), "fichas_pdf")

os.makedirs(PDF_DIR, exist_ok=True)

# Mapa de estados monitoreados
ESTADOS_CONFIG = {
    "Sinaloa": {
        "emoji": "📍",
        "keywords": [
            "sinaloa", "culiacan", "culiacán", "mazatlan", "mazatlán", "los mochis",
            "ahome", "guasave", "navolato", "saludsinaloa", "925006", "056ayo920",
            "051gyn002", "050gyr061"
        ],
        "unidades": [
            ("servicios-de-salud-de-sinaloa-925006998", "Servicios de Salud de Sinaloa (SSA)"),
            ("coordinacion-estatal-imss-bienestar-sinaloa-056ayo920", "IMSS-Bienestar Sinaloa"),
            ("departamento-de-adquisiciones-en-sinaloa-051gyn002", "ISSSTE Sinaloa"),
            ("delegacion-estatal-en-sinaloa-departamento-de-construccion-y-planeacion-inmobilaria-050gyr061", "IMSS Delegación Sinaloa")
        ]
    },
    "Sonora": {
        "emoji": "🌵",
        "keywords": [
            "sonora", "hermosillo", "ciudad obregón", "ciudad obregon", "cd. obregón",
            "cd obregon", "nogales", "navojoa", "guaymas", "cajeme", "ssaludsonora",
            "056ayo933", "050gyr068"
        ],
        "unidades": [
            ("coordinacion-estatal-de-imss-bienestar-en-sonora-056ayo933", "IMSS-Bienestar Sonora")
        ]
    },
    "Durango": {
        "emoji": "🦂",
        "keywords": [
            "durango", "gomez palacio", "gómez palacio", "lerdo", "069q55", "050gyr054"
        ],
        "unidades": [
            ("departamento-de-construccion-de-la-delegacion-durango-050gyr054", "IMSS Delegación Durango")
        ]
    },
    "Nayarit": {
        "emoji": "🌊",
        "keywords": [
            "nayarit", "tepic", "bahia de banderas", "bahía de banderas", "santiago ixcuintla",
            "056ayo923", "ssn"
        ],
        "unidades": [
            ("coordinacion-estatal-del-imss-bienestar-de-nayarit-056ayo923", "IMSS-Bienestar Nayarit")
        ]
    },
    "Jalisco": {
        "emoji": "⭐",
        "keywords": [
            "jalisco", "guadalajara", "zapopan", "tlaquepaque", "tonala", "tonalá",
            "puerto vallarta", "ciudad guzman", "ciudad guzmán", "073019", "051gyn065",
            "914010"
        ],
        "unidades": [
            ("direccion-de-recursos-materiales-de-opd-servicios-de-salud-jalisco-914010985", "Servicios de Salud Jalisco"),
            ("delegacion-estatal-jalisco-departamento-de-recursos-materiales-y-obras-051gyn065", "ISSSTE Delegación Jalisco")
        ]
    }
}

# Palabras clave biomédicas estrictas
KEYWORDS_BIOMEDICA = [
    "medico", "médico", "biomed", "bioméd", "hospital", "clinico", "clínico",
    "quirurg", "quirúrg", "curacion", "curación", "laboratorio", "reactivo",
    "mantenimiento", "conservación", "calibración", "equipo", "instrumental",
    "imagenolog", "ultrason", "rayos x", "tomograf", "mastograf", "resonancia",
    "dialisis", "diálisis", "hemodi", "anestesia", "anestesiolog", "infeccion",
    "esteriliz", "protesis", "prótesis", "endoprótesis", "osteosíntesis",
    "marcapasos", "oxígeno", "banco de sangre", "terapia", "monitoreo", "cardiol"
]

EXCLUSIONES_NO_BIOMEDICAS = [
    "recetario", "transbordador", "puente", "pavimentaci", "camino", "agua potable",
    "alcantarillado", "computo", "vehiculo", "gas lp", "alarma", "papeleria", "limpieza"
]

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "BotBiomedicoRegional/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as err:
        print(f"[WARN] Error al consultar {url}: {err}")
        return {}

def es_biomedico(texto):
    texto_l = (texto or "").lower()
    if any(ex in texto_l for ex in EXCLUSIONES_NO_BIOMEDICAS):
        return False
    return any(kw in texto_l for kw in KEYWORDS_BIOMEDICA)

def detectar_estado(texto):
    texto_l = (texto or "").lower()
    for estado, config in ESTADOS_CONFIG.items():
        if any(kw in texto_l for kw in config["keywords"]):
            return estado, config["emoji"]
    return None, None

def obtener_objeto_completo(root):
    """Extrae la descripción completa y no truncada del procedimiento."""
    desc = root.get("description")
    detailed = ""
    if isinstance(desc, dict):
        detailed = (desc.get("detailed") or "").strip()
    elif isinstance(desc, str):
        detailed = desc.strip()
        
    title = (root.get("title") or root.get("nombre_procedimiento") or "").strip()
    
    # Si description.detailed es más completo y no es solo justificación legal
    if detailed and len(detailed) >= len(title) and not detailed.startswith("Peligro o alteración"):
        return detailed
    return title or detailed or "Sin descripción registrada"

def extraer_ganadores(data_detalle):
    """Extrae empresas ganadoras y montos adjudicados si existen."""
    root = data_detalle.get("data", data_detalle)
    awards = root.get("awards", [])
    ganadores = []

    for aw in awards:
        contractor = aw.get("contractor") or {}
        val = aw.get("value") or {}
        nom = contractor.get("name") or contractor.get("normalized_name")
        if nom:
            monto_str = "No especificado"
            try:
                if val.get("total"):
                    monto_str = f"${float(val.get('total')):,.2f} {val.get('currency', 'MXN')}"
            except Exception:
                monto_str = f"{val.get('total', '')} {val.get('currency', 'MXN')}"

            ganadores.append({
                "empresa": nom,
                "monto": monto_str,
                "rfc_type": contractor.get("rfc_type"),
                "periodo": aw.get("contract_period") or {}
            })
    return ganadores

def generar_pdf_licitacion(proc_detalle, estado, emoji):
    """Genera un PDF con ficha digerida, objeto completo, partidas, anexos y empresa ganadora."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
    except ImportError:
        print("[ERROR] Reportlab no está instalado.")
        return None, [], "Sin descripción"

    root = proc_detalle.get("data", proc_detalle)
    num = root.get("procedure_number") or root.get("numero_procedimiento") or "licitacion"
    safe_num = "".join(c for c in num if c.isalnum() or c in "-_")
    pdf_path = os.path.join(PDF_DIR, f"Ficha_{safe_num}.pdf")

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1a365d'), spaceAfter=4)
    subtitle_style = ParagraphStyle('SubtitleStyle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#4a5568'), spaceAfter=8)
    h2_style = ParagraphStyle('H2Style', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#2b6cb0'), spaceBefore=8, spaceAfter=4)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=8.5, textColor=colors.HexColor('#2d3748'), leading=11)
    bold_style = ParagraphStyle('BoldStyle', parent=body_style, fontName='Helvetica-Bold')

    story = []
    story.append(Paragraph(f"FICHA TÉCNICA RESUMIDA DE LICITACIÓN {emoji}", title_style))
    story.append(Paragraph(f"Vigilancia de Compras Públicas · Sector Biomédico Regional", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2b6cb0'), spaceAfter=8))

    # Datos Generales
    f_pub = (root.get("schedule", {}).get("published_at") or root.get("fecha_publicacion") or "N/D")[:10]
    tipo = root.get("classification", {}).get("procedure_type") or root.get("tipo_procedimiento") or "No especificado"
    estatus = (root.get("lifecycle", {}).get("status") or root.get("estatus") or root.get("status") or "VIGENTE").upper()
    dep = root.get("buyer", {}).get("name") or root.get("dependencia") or root.get("origen_institucion") or "Sector Salud"

    datos_grales = [
        [Paragraph("<b>Estado:</b>", bold_style), Paragraph(f"{estado}", body_style), Paragraph("<b>Número:</b>", bold_style), Paragraph(f"<b>{num}</b>", bold_style)],
        [Paragraph("<b>Institución:</b>", bold_style), Paragraph(f"{dep}", body_style), Paragraph("<b>Tipo:</b>", bold_style), Paragraph(f"{tipo}", body_style)],
        [Paragraph("<b>Fecha Pub:</b>", bold_style), Paragraph(f"{f_pub}", body_style), Paragraph("<b>Estatus:</b>", bold_style), Paragraph(f"{estatus}", body_style)],
    ]
    t_gral = Table(datos_grales, colWidths=[65, 200, 65, 210])
    t_gral.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7fafc')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_gral)
    story.append(Spacer(1, 6))

    # Objeto de la Contratación (Completo, sin truncar)
    objeto_completo = obtener_objeto_completo(root)
    story.append(Paragraph("Objeto de la Contratación", h2_style))
    story.append(Paragraph(objeto_completo, body_style))
    story.append(Spacer(1, 6))

    # Empresa Ganadora si existe
    ganadores = extraer_ganadores(proc_detalle)
    story.append(Paragraph("Resultado del Fallo y Empresa Ganadora", h2_style))
    if ganadores:
        gan_rows = [[Paragraph("<b>Empresa / Proveedor Adjudicado</b>", bold_style), Paragraph("<b>Monto Total Adjudicado</b>", bold_style)]]
        for g in ganadores:
            gan_rows.append([
                Paragraph(f"🏆 <b>{g['empresa']}</b>", body_style),
                Paragraph(f"<b>{g['monto']}</b>", body_style)
            ])
        t_gan = Table(gan_rows, colWidths=[380, 160])
        t_gan.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#feebc8')),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fffaf0')),
            ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#dd6b20')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#fbd38d')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_gan)
    else:
        story.append(Paragraph("⏳ <i>Licitación en etapa de convocatoria / evaluación abierta. Aún no se emite el acta de fallo ni hay empresa adjudicada.</i>", body_style))
    story.append(Spacer(1, 6))

    # Partidas CUCOP
    items_cucop = []
    for aw in root.get("awards", []):
        for it in aw.get("line_items", []):
            items_cucop.append(it)
    for lot in root.get("lots", []):
        for it in lot.get("line_items", []):
            items_cucop.append(it)

    if items_cucop:
        story.append(Paragraph("Partidas y Claves CUCOP Identificadas", h2_style))
        partidas_rows = [[
            Paragraph("<b>CUCOP</b>", bold_style),
            Paragraph("<b>Descripción del Bien / Servicio</b>", bold_style),
            Paragraph("<b>Cantidad / Unidad</b>", bold_style)
        ]]
        for it in items_cucop[:6]:
            code = it.get("cucop_code") or "N/D"
            desc = it.get("description") or "Sin descripción"
            qty = f"{it.get('requested_quantity', '')} {it.get('unit', '')}".strip() or "Servicio"
            partidas_rows.append([
                Paragraph(f"<code>{code}</code>", body_style),
                Paragraph(desc, body_style),
                Paragraph(qty, body_style)
            ])
        t_part = Table(partidas_rows, colWidths=[80, 360, 100])
        t_part.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#edf2f7')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(t_part)
        story.append(Spacer(1, 6))

    # Anexos
    docs = root.get("documents", [])
    if docs:
        story.append(Paragraph("Anexos y Documentos Registrados", h2_style))
        doc_rows = [[Paragraph("<b>Documento / Anexo</b>", bold_style), Paragraph("<b>Archivo Original</b>", bold_style), Paragraph("<b>Tamaño</b>", bold_style)]]
        for d in docs[:6]:
            d_nom = d.get("description") or "Anexo"
            d_file = d.get("filename") or "archivo"
            sz_kb = f"{int(d.get('size_bytes', 0)) // 1024} KB" if d.get('size_bytes') else "N/D"
            doc_rows.append([Paragraph(d_nom, body_style), Paragraph(d_file, body_style), Paragraph(sz_kb, body_style)])
        t_docs = Table(doc_rows, colWidths=[200, 240, 100])
        t_docs.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#edf2f7')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(t_docs)

    doc.build(story)
    return pdf_path, ganadores, objeto_completo

def send_telegram_doc(pdf_path, caption):
    """Envía el PDF generado directamente como archivo adjunto a Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    boundary = "----WebKitFormBoundaryBotBiomedico7MA"
    filename = os.path.basename(pdf_path)

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"chat_id\"\r\n\r\n"
        f"{TELEGRAM_CHAT_ID}\r\n"
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"caption\"\r\n\r\n"
        f"{caption}\r\n"
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"parse_mode\"\r\n\r\n"
        f"Markdown\r\n"
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"document\"; filename=\"{filename}\"\r\n"
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + pdf_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": "BotBiomedicoRegional/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("ok", False)
    except Exception as err:
        print(f"[ERROR] Fallo al enviar PDF por Telegram: {err}")
        return False

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_cache(notified_set):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(notified_set)), f, indent=2)
    except Exception as err:
        print(f"[WARN] No se pudo guardar caché: {err}")

def buscar_licitaciones_region(dias_atras=30):
    encontradas = []
    fecha_limite = (datetime.now(timezone.utc) - timedelta(days=dias_atras)).strftime("%Y-%m-%d")

    # 1. Unidades compradoras de salud
    for estado, config in ESTADOS_CONFIG.items():
        for slug_unidad, label_inst in config["unidades"]:
            url = f"https://api.licitia.com.mx/api/open/v1/unidades/{slug_unidad}/procedimientos"
            res = fetch_json(url)
            for proc in res.get("data", []):
                f_pub = (proc.get("fecha_publicacion") or "")[:10]
                status = (proc.get("status") or "").lower()
                nombre = proc.get("nombre_procedimiento") or ""

                if (f_pub >= fecha_limite or status == "vigente") and es_biomedico(nombre):
                    proc["estado_detectado"] = estado
                    proc["estado_emoji"] = config["emoji"]
                    proc["origen_institucion"] = label_inst
                    encontradas.append(proc)

    # 2. Procedimientos vigentes transversales
    url_vigentes = "https://api.licitia.com.mx/api/open/v1/licitaciones?section=vigente&limit=100"
    res_vigentes = fetch_json(url_vigentes)
    for proc in res_vigentes.get("data", []):
        nombre = proc.get("nombre_procedimiento") or ""
        dep = proc.get("dependencia") or ""
        siglas = proc.get("siglas") or ""
        num = proc.get("numero_procedimiento") or ""
        texto_completo = f"{num} {nombre} {dep} {siglas}"

        estado, emoji = detectar_estado(texto_completo)
        if estado and es_biomedico(nombre):
            proc["estado_detectado"] = estado
            proc["estado_emoji"] = emoji
            proc["origen_institucion"] = dep
            encontradas.append(proc)

    # Deduplicar por número de procedimiento
    vistos = set()
    unicas = []
    for p in encontradas:
        num = p.get("numero_procedimiento")
        if num and num not in vistos:
            vistos.add(num)
            unicas.append(p)

    return unicas

def self_check():
    """Chequeo ejecutable sin frameworks"""
    assert es_biomedico("SERVICIO DE MANTENIMIENTO PREVENTIVO A EQUIPO MÉDICO") is True
    assert es_biomedico("ADQUISICIÓN DE RECETARIOS MÉDICOS") is False
    assert es_biomedico("SERVICIO MÉDICO INTEGRAL DE ANESTESIA") is True
    
    mock_concluido = {
        "procedure_number": "test-ganador-2026",
        "title": "ADQUISICIÓN DE EQUIPO MÉDICO QUIRÚRGICO Y DE DIAGNÓSTICO",
        "description": {"detailed": "ADQUISICIÓN DE EQUIPO MÉDICO QUIRÚRGICO Y DE DIAGNÓSTICO PARA EL HOSPITAL GENERAL DE CULIACÁN SINALOA."},
        "lifecycle": {"status": "concluido"},
        "awards": [{
            "contractor": {"name": "EMPRESA BIOMEDICA SA DE CV"},
            "value": {"total": "500000", "currency": "MXN"}
        }]
    }
    assert "HOSPITAL GENERAL DE CULIACÁN" in obtener_objeto_completo(mock_concluido)
    
    pdf_p, _, _ = generar_pdf_licitacion(mock_concluido, "Sinaloa", "📍")
    assert pdf_p is not None and os.path.exists(pdf_p)
    print("✅ Self-check superado: Objeto completo sin truncar, PDF y filtros OK.")

def main():
    if "--self-check" in sys.argv:
        self_check()
        return

    force_mode = "--force" in sys.argv
    send_all = "--send-all" in sys.argv

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Escaneando Sinaloa y vecinos (Sonora, Durango, Nayarit, Jalisco)...")
    cache = load_cache()

    procedimientos = buscar_licitaciones_region(dias_atras=30 if (force_mode or send_all) else 7)
    print(f"Total de licitaciones biomédicas filtradas en la región: {len(procedimientos)}")

    notificados_hoy = 0
    for proc in procedimientos:
        num = proc.get("numero_procedimiento")
        if not num:
            continue

        if num not in cache or force_mode or send_all:
            estado = proc.get("estado_detectado") or "Región"
            emoji = proc.get("estado_emoji") or "📍"

            # Obtener detalle enriquecido de la licitación
            detalle = fetch_json(f"https://api.licitia.com.mx/api/open/v1/licitaciones/{num}")
            if not detalle.get("data"):
                detalle = proc

            pdf_file, ganadores, objeto_completo = generar_pdf_licitacion(detalle, estado, emoji)
            
            ganador_texto = ""
            if ganadores:
                ganador_texto = f"\n🏆 *Ganador:* {ganadores[0]['empresa']} ({ganadores[0]['monto']})"

            # Limitar caption si es muy largo para Telegram (máx 1024 caracteres)
            if len(objeto_completo) > 300:
                objeto_caption = objeto_completo[:300] + "..."
            else:
                objeto_caption = objeto_completo

            caption = (
                f"🚨 *LICITACIÓN BIOMÉDICA*\n"
                f"📍 *Estado:* {emoji} *{estado}*\n"
                f"📋 *Objeto:* {objeto_caption}\n"
                f"🏥 *Institución:* {proc.get('origen_institucion', '')}\n"
                f"🔢 *Número:* `{num}`"
                f"{ganador_texto}\n\n"
                f"📄 *Ficha técnica en PDF adjunta.*"
            )

            print(f"-> [{estado}] Enviando PDF y alerta para {num}...")
            if pdf_file:
                ok = send_telegram_doc(pdf_file, caption)
                if ok:
                    cache.add(num)
                    notificados_hoy += 1
                time.sleep(1)

    save_cache(cache)
    print(f"Finalizado. Total de fichas PDF enviadas: {notificados_hoy}")

if __name__ == "__main__":
    main()
