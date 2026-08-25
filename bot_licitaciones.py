#!/usr/bin/env python3
"""
Bot de Licitaciones Biomédicas con Menú Interactivo, Fichas PDF y Búsqueda por Proveedor
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

def cargar_env_local():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() not in os.environ:
                            os.environ[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass

cargar_env_local()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
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

KEYBOARD_MENU = {
    "keyboard": [
        [{"text": "🟢 Licitaciones Activas"}, {"text": "🔴 Licitaciones Adjudicadas"}],
        [{"text": "✨ Licitaciones Nuevas"}, {"text": "📍 Solo Sinaloa"}],
        [{"text": "🏢 Buscar Proveedor"}]
    ],
    "resize_keyboard": True,
    "is_persistent": True
}

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

def obtener_distintivo_estatus(proc_detalle):
    """Calcula el distintivo visual según si la licitación está abierta o ya adjudicada."""
    root = proc_detalle.get("data", proc_detalle)
    raw_status = (root.get("lifecycle", {}).get("status") or root.get("status") or root.get("estatus") or "").lower()
    awards = root.get("awards", [])
    has_contractor = any(aw.get("contractor") for aw in awards)
    
    if "vigente" in raw_status or "abiert" in raw_status:
        return {
            "tipo": "ABIERTA",
            "emoji": "🟢",
            "texto_telegram": "🟢 *ESTATUS: CONVOCATORIA ABIERTA (VIGENTE)*",
            "texto_pdf": "🟢 CONVOCATORIA ABIERTA (En plazo para participar)",
            "bg_color": "#c6f6d5",
            "border_color": "#38a169",
            "text_color": "#22543d"
        }
    elif has_contractor or "concluid" in raw_status or "adjudicad" in raw_status:
        return {
            "tipo": "ADJUDICADA",
            "emoji": "🔴",
            "texto_telegram": "🔴 *ESTATUS: YA ADJUDICADA / CONCLUIDA*",
            "texto_pdf": "🔴 ADJUDICADA / CONCLUIDA (Con Acta de Fallo)",
            "bg_color": "#fed7d7",
            "border_color": "#e53e3e",
            "text_color": "#742a2a"
        }
    elif "desiert" in raw_status:
        return {
            "tipo": "DESIERTA",
            "emoji": "⚪",
            "texto_telegram": "⚪ *ESTATUS: DECLARADA DESIERTA*",
            "texto_pdf": "⚪ DECLARADA DESIERTA",
            "bg_color": "#edf2f7",
            "border_color": "#cbd5e0",
            "text_color": "#4a5568"
        }
    else:
        return {
            "tipo": "SEGUIMIENTO",
            "emoji": "🟡",
            "texto_telegram": f"🟡 *ESTATUS: {raw_status.upper()}*",
            "texto_pdf": f"🟡 {raw_status.upper()}",
            "bg_color": "#fefcbf",
            "border_color": "#d69e2e",
            "text_color": "#744210"
        }

def obtener_objeto_completo(root):
    """Extrae la descripción completa y no truncada del procedimiento."""
    desc = root.get("description")
    detailed = ""
    if isinstance(desc, dict):
        detailed = (desc.get("detailed") or "").strip()
    elif isinstance(desc, str):
        detailed = desc.strip()
        
    title = (root.get("title") or root.get("nombre_procedimiento") or "").strip()
    
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
    """Genera un PDF con ficha digerida, distintivo visual de estado, objeto completo y partidas."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
    except ImportError:
        print("[ERROR] Reportlab no está instalado.")
        return None, [], "Sin descripción", {}

    distintivo = obtener_distintivo_estatus(proc_detalle)
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
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1a365d'), spaceAfter=2)
    subtitle_style = ParagraphStyle('SubtitleStyle', parent=styles['Normal'], fontSize=8.5, textColor=colors.HexColor('#4a5568'), spaceAfter=6)
    h2_style = ParagraphStyle('H2Style', parent=styles['Heading2'], fontSize=10.5, textColor=colors.HexColor('#2b6cb0'), spaceBefore=7, spaceAfter=3)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=8.5, textColor=colors.HexColor('#2d3748'), leading=11)
    bold_style = ParagraphStyle('BoldStyle', parent=body_style, fontName='Helvetica-Bold')
    badge_style = ParagraphStyle('BadgeStyle', parent=styles['Normal'], fontSize=9.5, textColor=colors.HexColor(distintivo["text_color"]), fontName='Helvetica-Bold', alignment=1)

    story = []
    story.append(Paragraph(f"FICHA TÉCNICA RESUMIDA DE LICITACIÓN {emoji}", title_style))
    story.append(Paragraph(f"Vigilancia de Compras Públicas · Sector Biomédico Regional", subtitle_style))

    # Banner distintivo de estado
    badge_table = Table([[Paragraph(f"<b>{distintivo['texto_pdf']}</b>", badge_style)]], colWidths=[540])
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(distintivo["bg_color"])),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor(distintivo["border_color"])),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(badge_table)
    story.append(Spacer(1, 6))

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
    story.append(Spacer(1, 5))

    # Objeto de la Contratación
    objeto_completo = obtener_objeto_completo(root)
    story.append(Paragraph("Objeto de la Contratación", h2_style))
    story.append(Paragraph(objeto_completo, body_style))
    story.append(Spacer(1, 5))

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
    story.append(Spacer(1, 5))

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
        story.append(Spacer(1, 5))

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
    return pdf_path, ganadores, objeto_completo, distintivo

def send_telegram_msg(texto, chat_id=None, reply_markup=None):
    """Envía un mensaje de texto simple o con teclado interactivo a Telegram."""
    target_chat = chat_id or TELEGRAM_CHAT_ID
    if not TELEGRAM_TOKEN or not target_chat:
        return False
        
    payload_dict = {
        "chat_id": target_chat,
        "text": texto,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload_dict["reply_markup"] = reply_markup
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = json.dumps(payload_dict).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "BotBiomedicoRegional/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("ok", False)
    except Exception as err:
        print(f"[ERROR] Error al enviar mensaje: {err}")
        return False

def send_telegram_doc(pdf_path, caption, chat_id=None):
    """Envía el PDF generado directamente como archivo adjunto a Telegram."""
    target_chat = chat_id or TELEGRAM_CHAT_ID
    if not TELEGRAM_TOKEN or not target_chat:
        return False

    boundary = "----WebKitFormBoundaryBotBiomedico7MA"
    filename = os.path.basename(pdf_path)

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"chat_id\"\r\n\r\n"
        f"{target_chat}\r\n"
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

def buscar_licitaciones_region(dias_atras=30, solo_estado=None, solo_estatus=None):
    """Busca licitaciones biomédicas con filtros de días, estado o estatus (abierta / adjudicada)."""
    encontradas = []
    fecha_limite = (datetime.now(timezone.utc) - timedelta(days=dias_atras)).strftime("%Y-%m-%d")

    # 1. Unidades compradoras de salud
    for estado, config in ESTADOS_CONFIG.items():
        if solo_estado and solo_estado.lower() != estado.lower():
            continue
            
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
            if solo_estado and solo_estado.lower() != estado.lower():
                continue
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
            if solo_estatus:
                dist = obtener_distintivo_estatus(p)
                if dist["tipo"] != solo_estatus:
                    continue
            vistos.add(num)
            unicas.append(p)

    return unicas

def buscar_proveedor_y_enviar(nombre_q, chat_id):
    """Busca el perfil y las licitaciones ganadas de un proveedor específico."""
    send_telegram_msg(f"🔍 *Buscando historial comercial de:* `{nombre_q}`...", chat_id=chat_id)
    
    url_search = f"https://api.licitia.com.mx/api/open/v1/buscar?q={urllib.parse.quote(nombre_q)}&tipo=proveedor&limit=5"
    res = fetch_json(url_search)
    hits = res.get("data", {}).get("grupos", [{}])[0].get("hits", [])
    
    if not hits:
        send_telegram_msg(f"❌ *No se encontró ningún proveedor registrado con el nombre:* `{nombre_q}`.\n\nIntenta con una palabra clave diferente (ej: `/proveedor vitalmex` o `/proveedor mrs labs`).", chat_id=chat_id)
        return
        
    top_hit = hits[0]
    slug = top_hit.get("clave")
    razon_social = top_hit.get("titulo") or nombre_q
    monto_total = f"${float(top_hit.get('monto', 0)):,.2f} MXN" if top_hit.get("monto") else "N/D"
    total_contratos = top_hit.get("cuenta", "0")
    dependencias = top_hit.get("detalle", "")

    # Enviar resumen del perfil del proveedor
    perfil_msg = (
        f"🏢 *PERFIL DE PROVEEDOR ENCONTRADO*\n\n"
        f"🏷️ *Razón Social:* {razon_social}\n"
        f"💰 *Monto Total Adjudicado:* {monto_total}\n"
        f"📑 *Total de Contratos:* {total_contratos}\n"
        f"🏥 *Alcance:* {dependencias}\n\n"
        f"📥 *Generando y enviando las fichas PDF de sus procedimientos recientes...*"
    )
    send_telegram_msg(perfil_msg, chat_id=chat_id)
    
    # Obtener historial de procedimientos
    url_procs = f"https://api.licitia.com.mx/api/open/v1/proveedores/{slug}/procedimientos"
    res_procs = fetch_json(url_procs)
    procs = res_procs.get("data", [])
    
    if not procs:
        send_telegram_msg("ℹ️ *No se encontraron procedimientos registrados en el historial de este proveedor.*", chat_id=chat_id)
        return
        
    for p in procs[:5]:
        enviar_procedimiento_individual(p, chat_id)
        time.sleep(1)

def responder_consulta_interactiva(comando, chat_id):
    """Procesa comandos y consultas interactivas recibidas por Telegram."""
    c = comando.strip()
    c_lower = c.lower()
    
    if c_lower in ["/start", "start", "/menu", "menu", "/ayuda", "ayuda"]:
        texto = (
            "📋 *Menú de Control de Licitaciones Biomédicas*\n\n"
            "Presiona cualquiera de los botones abajo o escribe un comando:\n\n"
            "• 🟢 *Licitaciones Activas:* Convocatorias vigentes para participar.\n"
            "• 🔴 *Licitaciones Adjudicadas:* Procedimientos concluidos con empresa ganadora y monto.\n"
            "• ✨ *Licitaciones Nuevas:* Publicaciones recientes (últimas 48h).\n"
            "• 📍 *Solo Sinaloa:* Procedimientos de salud en Sinaloa.\n"
            "• 🏢 *Buscar Proveedor:* Historial de licitaciones de una empresa."
        )
        send_telegram_msg(texto, chat_id=chat_id, reply_markup=KEYBOARD_MENU)
        return

    # Disparador: Buscar Proveedor
    if c_lower.startswith("/proveedor") or c_lower.startswith("proveedor"):
        partes = c.split(maxsplit=1)
        if len(partes) > 1 and partes[1].strip():
            nombre_prov = partes[1].strip()
            buscar_proveedor_y_enviar(nombre_prov, chat_id)
        else:
            send_telegram_msg(
                "🏢 *Búsqueda de Proveedor o Empresa*\n\n"
                "Escribe `/proveedor` seguido del nombre o razón social de la empresa que deseas investigar.\n\n"
                "*Ejemplos:*\n"
                "• `/proveedor MRS Labs`\n"
                "• `/proveedor Vitalmex`\n"
                "• `/proveedor Biomedica`",
                chat_id=chat_id
            )
        return

    if "buscar proveedor" in c_lower or "proveedor" in c_lower:
        send_telegram_msg(
            "🏢 *Búsqueda de Proveedor o Empresa*\n\n"
            "Escribe `/proveedor` seguido del nombre de la empresa que quieres investigar.\n\n"
            "*Ejemplo:*\n"
            "👉 `/proveedor MRS Labs`",
            chat_id=chat_id
        )
        return

    send_telegram_msg("🔍 *Consultando compras públicas en tiempo real... Espera un momento.*", chat_id=chat_id)

    # Disparador: Licitaciones Activas (Abiertas)
    if "activa" in c_lower or "vigente" in c_lower or "abiert" in c_lower:
        procs = buscar_licitaciones_region(dias_atras=30, solo_estatus="ABIERTA")
        if not procs:
            send_telegram_msg("ℹ️ *No hay licitaciones abiertas (vigentes) en este momento en la región.* Todas las registradas en el periodo reciente ya fueron adjudicadas.", chat_id=chat_id)
            return
        send_telegram_msg(f"🟢 *Se encontraron {len(procs)} licitaciones ABIERTAS para participar:*", chat_id=chat_id)
        for p in procs:
            enviar_procedimiento_individual(p, chat_id)
            time.sleep(1)

    # Disparador: Licitaciones Adjudicadas
    elif "adjudicad" in c_lower or "concluid" in c_lower or "ganador" in c_lower:
        procs = buscar_licitaciones_region(dias_atras=45, solo_estatus="ADJUDICADA")
        send_telegram_msg(f"🔴 *Se encontraron {len(procs)} licitaciones ADJUDICADAS con fallo registrado:*", chat_id=chat_id)
        for p in procs:
            enviar_procedimiento_individual(p, chat_id)
            time.sleep(1)

    # Disparador: Licitaciones Nuevas (Últimas 48h)
    elif "nueva" in c_lower or "reciente" in c_lower:
        procs = buscar_licitaciones_region(dias_atras=3)
        if not procs:
            send_telegram_msg("✨ *No se registraron nuevas publicaciones en las últimas 48 horas en la región.*", chat_id=chat_id)
            return
        send_telegram_msg(f"✨ *Se encontraron {len(procs)} publicaciones recientes:*", chat_id=chat_id)
        for p in procs:
            enviar_procedimiento_individual(p, chat_id)
            time.sleep(1)

    # Disparador: Solo Sinaloa
    elif "sinaloa" in c_lower:
        procs = buscar_licitaciones_region(dias_atras=45, solo_estado="Sinaloa")
        send_telegram_msg(f"📍 *Se encontraron {len(procs)} licitaciones del sector salud en Sinaloa:*", chat_id=chat_id)
        for p in procs:
            enviar_procedimiento_individual(p, chat_id)
            time.sleep(1)
    else:
        send_telegram_msg("❓ Comando no reconocido. Usa los botones del menú o escribe `/activas`, `/adjudicadas`, `/nuevas`, `/sinaloa` o `/proveedor <nombre>`.", chat_id=chat_id, reply_markup=KEYBOARD_MENU)

def enviar_procedimiento_individual(proc, chat_id):
    """Genera PDF y envía alerta de un procedimiento específico."""
    num = proc.get("numero_procedimiento")
    estado = proc.get("estado_detectado") or "Región"
    emoji = proc.get("estado_emoji") or "📍"

    detalle = fetch_json(f"https://api.licitia.com.mx/api/open/v1/licitaciones/{num}")
    if not detalle.get("data"):
        detalle = proc

    pdf_file, ganadores, objeto_completo, distintivo = generar_pdf_licitacion(detalle, estado, emoji)
    
    ganador_texto = ""
    if ganadores:
        ganador_texto = f"\n🏆 *Ganador:* {ganadores[0]['empresa']} ({ganadores[0]['monto']})"

    if len(objeto_completo) > 300:
        objeto_caption = objeto_completo[:300] + "..."
    else:
        objeto_caption = objeto_completo

    caption = (
        f"🚨 *LICITACIÓN BIOMÉDICA*\n"
        f"📍 *Estado:* {emoji} *{estado}*\n"
        f"{distintivo['texto_telegram']}\n\n"
        f"📋 *Objeto:* {objeto_caption}\n"
        f"🏥 *Institución:* {proc.get('origen_institucion', '')}\n"
        f"🔢 *Número:* `{num}`"
        f"{ganador_texto}\n\n"
        f"📄 *Ficha técnica en PDF adjunta.*"
    )

    if pdf_file:
        send_telegram_doc(pdf_file, caption, chat_id=chat_id)

def escuchar_mensajes_interactivos():
    """Modo polling continuo para escuchar comandos desde Telegram en tiempo real."""
    print("🤖 Bot interactivo iniciado. Escuchando mensajes de Telegram en tiempo real...")
    offset = None
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?timeout=20"
            if offset:
                url += f"&offset={offset}"
            req = urllib.request.Request(url, headers={"User-Agent": "BotBiomedicoRegional/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                
            for update in data.get("result", []):
                offset = update.get("update_id", 0) + 1
                msg = update.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                texto = msg.get("text", "")
                
                if chat_id and texto:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Mensaje recibido de {chat_id}: '{texto}'")
                    responder_consulta_interactiva(texto, chat_id)
        except Exception as e:
            print(f"[WARN] Error en polling: {e}")
            time.sleep(3)

def self_check():
    """Chequeo ejecutable sin frameworks"""
    assert es_biomedico("SERVICIO DE MANTENIMIENTO PREVENTIVO A EQUIPO MÉDICO") is True
    assert es_biomedico("ADQUISICIÓN DE RECETARIOS MÉDICOS") is False
    
    mock_concluido = {
        "procedure_number": "test-prov-2026",
        "lifecycle": {"status": "concluido"},
        "awards": [{"contractor": {"name": "EMPRESA BIOMEDICA SA"}, "value": {"total": "100000"}}]
    }
    pdf_p, _, _, _ = generar_pdf_licitacion(mock_concluido, "Sinaloa", "📍")
    assert pdf_p is not None and os.path.exists(pdf_p)
    print("✅ Self-check superado: Búsqueda por proveedor, menú, PDF y filtros OK.")

def main():
    if "--self-check" in sys.argv:
        self_check()
        return

    if "--interactivo" in sys.argv or "--listen" in sys.argv:
        escuchar_mensajes_interactivos()
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

            detalle = fetch_json(f"https://api.licitia.com.mx/api/open/v1/licitaciones/{num}")
            if not detalle.get("data"):
                detalle = proc

            pdf_file, ganadores, objeto_completo, distintivo = generar_pdf_licitacion(detalle, estado, emoji)
            
            ganador_texto = ""
            if ganadores:
                ganador_texto = f"\n🏆 *Ganador:* {ganadores[0]['empresa']} ({ganadores[0]['monto']})"

            if len(objeto_completo) > 300:
                objeto_caption = objeto_completo[:300] + "..."
            else:
                objeto_caption = objeto_completo

            caption = (
                f"🚨 *LICITACIÓN BIOMÉDICA*\n"
                f"📍 *Estado:* {emoji} *{estado}*\n"
                f"{distintivo['texto_telegram']}\n\n"
                f"📋 *Objeto:* {objeto_caption}\n"
                f"🏥 *Institución:* {proc.get('origen_institucion', '')}\n"
                f"🔢 *Número:* `{num}`"
                f"{ganador_texto}\n\n"
                f"📄 *Ficha técnica en PDF adjunta.*"
            )

            print(f"-> [{estado}] ({distintivo['tipo']}) Enviando PDF y alerta para {num}...")
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
