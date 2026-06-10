import streamlit as st
import requests
from datetime import datetime, date, timedelta
import hashlib
import pandas as pd
import io
import calendar

# -------- CONFIG --------
SUPABASE_URL = "https://hivvykyslqodrrfmteer.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhpdnZ5a3lzbHFvZHJyZm10ZWVyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg3MTA0NzQsImV4cCI6MjA5NDI4NjQ3NH0.1dBUFD9myAK9057E0g6RVFKellm6RT_6E15RHz63ryc"
HEADERS = {
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "apikey": SUPABASE_KEY,
    "Content-Type": "application/json"
}

NOMBRE_CLINICA = "Clínica Odontológica Demo"
COLOR = "#1B9AAA"
SLUG = "odontodemo"

USUARIOS = {
    "admin": {"password": hashlib.sha256("admin123".encode()).hexdigest(), "rol": "admin", "sede": "Todas"},
    "recepcion": {"password": hashlib.sha256("recep123".encode()).hexdigest(), "rol": "recepcion", "sede": "Principal"},
}

# Prefijos de tablas
T_PACIENTES = f"{SLUG}_pacientes"
T_CITAS = f"{SLUG}_citas"
T_HISTORIAS = f"{SLUG}_historias"
T_TRATAMIENTOS = f"{SLUG}_tratamientos"
T_PAGOS = f"{SLUG}_pagos"
T_ALERTAS = f"{SLUG}_alertas"
T_PROCEDIMIENTOS = f"{SLUG}_procedimientos"
T_ODONTOLOGOS = f"{SLUG}_odontologos"

# -------- SUPABASE HELPERS --------
def sb_get(tabla, params=""):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{tabla}?{params}", headers=HEADERS)
    return r.json() if r.status_code == 200 else []

def sb_post(tabla, datos):
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{tabla}", headers={**HEADERS, "Prefer": "return=representation"}, json=datos)
    return r.status_code == 201

def sb_patch(tabla, id_val, datos):
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/{tabla}?id=eq.{id_val}", headers={**HEADERS, "Prefer": "return=minimal"}, json=datos)
    return r.status_code == 204

# -------- FESTIVOS COLOMBIA --------
def calcular_pascua(anio):
    a = anio % 19
    b = anio // 100
    c = anio % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(anio, mes, dia)

def siguiente_lunes(d):
    if d.weekday() == 0:
        return d
    return d + timedelta(days=(7 - d.weekday()))

def festivos_colombia(anio):
    pascua = calcular_pascua(anio)
    fijos = {
        date(anio, 1, 1): "Año Nuevo",
        date(anio, 5, 1): "Día del Trabajo",
        date(anio, 7, 20): "Independencia",
        date(anio, 8, 7): "Batalla de Boyacá",
        date(anio, 12, 8): "Inmaculada Concepción",
        date(anio, 12, 25): "Navidad",
    }
    emiliani = {
        siguiente_lunes(date(anio, 1, 6)): "Reyes Magos",
        siguiente_lunes(date(anio, 3, 19)): "San José",
        siguiente_lunes(date(anio, 6, 29)): "San Pedro y San Pablo",
        siguiente_lunes(date(anio, 8, 15)): "Asunción",
        siguiente_lunes(date(anio, 10, 12)): "Día de la Raza",
        siguiente_lunes(date(anio, 11, 1)): "Todos los Santos",
        siguiente_lunes(date(anio, 11, 11)): "Independencia Cartagena",
    }
    religiosos = {
        pascua - timedelta(days=3): "Jueves Santo",
        pascua - timedelta(days=2): "Viernes Santo",
        siguiente_lunes(pascua + timedelta(days=39)): "Ascensión",
        siguiente_lunes(pascua + timedelta(days=60)): "Corpus Christi",
        siguiente_lunes(pascua + timedelta(days=68)): "Sagrado Corazón",
    }
    todos = {}
    todos.update(fijos)
    todos.update(emiliani)
    todos.update(religiosos)
    return todos

# -------- HORARIOS --------
HORAS_LABORALES = [
    "08:00","08:30","09:00","09:30","10:00","10:30","11:00","11:30",
    "12:00","12:30","13:00","13:30","14:00","14:30","15:00","15:30",
    "16:00","16:30","17:00","17:30"
]

def calcular_hora_fin(hora_inicio, duracion_min):
    h, m = map(int, hora_inicio.split(":"))
    total_min = h * 60 + m + duracion_min
    return f"{total_min // 60:02d}:{total_min % 60:02d}"

def hay_conflicto(citas_dia, hora_inicio, duracion_min, excluir_id=None):
    h1, m1 = map(int, hora_inicio.split(":"))
    inicio_new = h1 * 60 + m1
    fin_new = inicio_new + duracion_min
    for c in citas_dia:
        if excluir_id and c.get("id") == excluir_id:
            continue
        if c.get("estado") in ["Cancelada", "No asistió"]:
            continue
        ch, cm = map(int, c.get("hora_inicio", "00:00").split(":"))
        c_inicio = ch * 60 + cm
        c_fin = c_inicio + (c.get("duracion_min") or 30)
        if inicio_new < c_fin and fin_new > c_inicio:
            return True
    return False

def formato_cop(valor):
    if not valor:
        return "$0"
    return f"${val:,.0f}".replace(",", ".") if (val := float(valor)) else "$0"

# -------- DOCUMENTOS --------
def subir_documento(archivo):
    try:
        url = f"{SUPABASE_URL}/storage/v1/object/documentos/{SLUG}/{archivo.name}"
        h = {"Authorization": f"Bearer {SUPABASE_KEY}", "apikey": SUPABASE_KEY, "Content-Type": archivo.type}
        r = requests.post(url, headers=h, data=archivo.getvalue())
        return r.status_code in [200, 201]
    except:
        return False

def listar_documentos():
    try:
        url = f"{SUPABASE_URL}/storage/v1/object/list/documentos"
        r = requests.post(url, headers={**HEADERS}, json={"prefix": SLUG + "/", "limit": 100})
        return r.json() if r.status_code == 200 else []
    except:
        return []

# -------- PAGE CONFIG --------
st.set_page_config(page_title=NOMBRE_CLINICA, page_icon="🦷", layout="wide")

st.markdown(f"""
<style>
.stApp {{ background-color: #0a0a0a; }}
.stButton > button {{
    background: linear-gradient(135deg, #0a1a1a, #112222) !important;
    color: {COLOR} !important; border: 1px solid {COLOR}66 !important;
    border-radius: 4px !important; font-size: 12px !important;
}}
.stTextInput > div > div > input, .stNumberInput > div > div > input,
.stDateInput > div > div > input, .stSelectbox > div > div > div,
.stTextArea > div > div > textarea {{
    background-color: #111 !important; color: #e0e0e0 !important;
    border: 1px solid {COLOR}44 !important;
}}
.mc {{ background:linear-gradient(135deg,#111,#1a1a1a); border:1px solid {COLOR}33; border-radius:8px; padding:20px 24px; text-align:center; }}
.mn {{ font-family:serif; font-size:42px; font-weight:700; color:{COLOR}; line-height:1; }}
.ml {{ font-size:11px; color:#888; letter-spacing:2px; margin-top:6px; }}
.dv {{ border:none; height:1px; background:linear-gradient(90deg,transparent,{COLOR}44,transparent); margin:20px 0; }}
.cal-day {{ display:inline-block; width:85px; height:70px; margin:2px; border-radius:6px; text-align:center; padding:6px 4px; font-size:12px; vertical-align:top; cursor:default; }}
.cal-hoy {{ border:2px solid {COLOR} !important; }}
.cal-normal {{ background:#111; border:1px solid #222; color:#ccc; }}
.cal-citas {{ background:#0a2a1a; border:1px solid #44ff8844; color:#44ff88; }}
.cal-vacio {{ background:#1a1a0a; border:1px solid #C9A84C44; color:#C9A84C; }}
.cal-festivo {{ background:#2a0a0a; border:1px solid #ff444444; color:#ff6666; }}
.cal-domingo {{ background:#1a1a1a; border:1px solid #33333366; color:#555; }}
.cal-fuera {{ background:transparent; border:1px solid transparent; color:#333; }}
.slot-ocupado {{ background:#0a2a2a; border:1px solid {COLOR}44; border-left:3px solid {COLOR}; border-radius:4px; padding:8px 12px; margin:3px 0; }}
.slot-libre {{ background:#111; border:1px solid #222; border-left:3px solid #44ff88; border-radius:4px; padding:8px 12px; margin:3px 0; color:#44ff88; font-size:12px; }}
.pop-alerta {{ background:#2a1a0a; border:1px solid #ff884466; border-radius:8px; padding:14px 18px; margin:8px 0; }}
</style>
""", unsafe_allow_html=True)

# -------- LOGIN --------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown(f"""
    <div style='text-align:center; padding:60px 0 30px 0;'>
        <div style='font-family:serif; font-size:11px; color:{COLOR}; letter-spacing:4px;'>{NOMBRE_CLINICA.upper()}</div>
        <div style='font-family:serif; font-size:28px; font-weight:700; color:#fff; margin:8px 0;'>Sistema de Gestión Odontológica</div>
        <div style='font-size:11px; color:#555; letter-spacing:2px;'>Powered by A.R.I.Z.A.</div>
    </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        usr = st.text_input("Usuario", key="login_usr")
        pwd = st.text_input("Contraseña", type="password", key="login_pwd")
        if st.button("Ingresar", use_container_width=True):
            pwd_hash = hashlib.sha256(pwd.encode()).hexdigest()
            if usr in USUARIOS and USUARIOS[usr]["password"] == pwd_hash:
                st.session_state.autenticado = True
                st.session_state.usuario = usr
                st.session_state.rol = USUARIOS[usr]["rol"]
                st.session_state.sede = USUARIOS[usr]["sede"]
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# -------- HEADER --------
st.markdown(f"""
<div style='text-align:center; padding:20px 0 10px 0; border-bottom:1px solid {COLOR}33; margin-bottom:20px;'>
    <div style='font-family:serif; font-size:11px; color:{COLOR}; letter-spacing:4px;'>{NOMBRE_CLINICA.upper()}</div>
    <div style='font-family:serif; font-size:24px; font-weight:700; color:#fff;'>Sistema de Gestión</div>
    <div style='font-size:10px; color:#555; margin-top:4px;'>Usuario: {st.session_state.usuario} | Rol: {st.session_state.rol}</div>
</div>
""", unsafe_allow_html=True)

# -------- MENÚ --------
if "menu" not in st.session_state:
    st.session_state.menu = "Agenda"

modulos = ["Agenda", "Pacientes", "Historias", "Tratamientos", "Pagos", "Alertas", "Documentos"]
cols = st.columns(len(modulos))
for i, mod in enumerate(modulos):
    with cols[i]:
        if st.button(f"◈ {mod.upper()}", use_container_width=True, key=f"m_{mod}"):
            st.session_state.menu = mod
            st.rerun()

menu = st.session_state.menu
st.markdown("<hr class='dv'>", unsafe_allow_html=True)

# Datos comunes
pacientes_list = sb_get(T_PACIENTES, "order=nombre.asc&estado=eq.Activo")
odontologos_list = sb_get(T_ODONTOLOGOS, "order=nombre.asc&activo=eq.true")
procedimientos_list = sb_get(T_PROCEDIMIENTOS, "order=nombre.asc&activo=eq.true")


# ================================================================
# AGENDA DE CITAS
# ================================================================
if menu == "Agenda":
    st.markdown(f"<div style='font-family:serif; font-size:20px; color:{COLOR};'>Agenda de Citas</div>", unsafe_allow_html=True)

    # Selector de mes y odontólogo
    ca1, ca2, ca3 = st.columns([1, 1, 1])
    with ca1:
        hoy = date.today()
        if "cal_mes" not in st.session_state:
            st.session_state.cal_mes = hoy.month
        if "cal_anio" not in st.session_state:
            st.session_state.cal_anio = hoy.year
        meses_es = ["","Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        mes_sel = st.selectbox("Mes", range(1, 13), index=st.session_state.cal_mes - 1, format_func=lambda x: meses_es[x], key="sel_mes")
        st.session_state.cal_mes = mes_sel
    with ca2:
        anio_sel = st.selectbox("Año", [hoy.year - 1, hoy.year, hoy.year + 1], index=1, key="sel_anio")
        st.session_state.cal_anio = anio_sel
    with ca3:
        filtro_odon = st.selectbox("Odontólogo", ["Todos"] + [o.get("nombre") for o in odontologos_list], key="filtro_odon")

    # Obtener citas del mes
    primer_dia = date(anio_sel, mes_sel, 1)
    if mes_sel == 12:
        ultimo_dia = date(anio_sel + 1, 1, 1) - timedelta(days=1)
    else:
        ultimo_dia = date(anio_sel, mes_sel + 1, 1) - timedelta(days=1)

    params_citas = f"fecha=gte.{primer_dia}&fecha=lte.{ultimo_dia}&order=fecha.asc,hora_inicio.asc"
    if filtro_odon != "Todos":
        params_citas += f"&odontologo=eq.{filtro_odon}"
    citas_mes = sb_get(T_CITAS, params_citas)

    # Agrupar citas por día
    citas_por_dia = {}
    for c in citas_mes:
        dia = c.get("fecha")
        if dia not in citas_por_dia:
            citas_por_dia[dia] = []
        citas_por_dia[dia].append(c)

    festivos = festivos_colombia(anio_sel)

    # ---- CALENDARIO MENSUAL ----
    st.markdown(f"<div style='text-align:center; font-family:serif; font-size:16px; color:{COLOR}; margin:10px 0;'>{meses_es[mes_sel]} {anio_sel}</div>", unsafe_allow_html=True)

    dias_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    header_html = "".join([f"<div class='cal-day' style='background:transparent; border:none; color:#888; font-weight:600; height:30px;'>{d}</div>" for d in dias_semana])
    st.markdown(f"<div style='text-align:center;'>{header_html}</div>", unsafe_allow_html=True)

    cal = calendar.monthcalendar(anio_sel, mes_sel)
    cal_html = ""
    for semana in cal:
        for dia_num in semana:
            if dia_num == 0:
                cal_html += "<div class='cal-day cal-fuera'></div>"
                continue

            fecha_dia = date(anio_sel, mes_sel, dia_num)
            fecha_str = str(fecha_dia)
            es_hoy = fecha_dia == hoy
            es_domingo = fecha_dia.weekday() == 6
            es_festivo = fecha_dia in festivos
            citas_dia = citas_por_dia.get(fecha_str, [])
            citas_activas = [c for c in citas_dia if c.get("estado") not in ["Cancelada", "No asistió"]]
            num_citas = len(citas_activas)

            clase = "cal-normal"
            if es_domingo:
                clase = "cal-domingo"
            elif es_festivo:
                clase = "cal-festivo"
            elif num_citas > 0:
                clase = "cal-citas"
            else:
                clase = "cal-vacio"

            if es_hoy:
                clase += " cal-hoy"

            info_festivo = festivos.get(fecha_dia, "")
            tooltip = f"title='{info_festivo}'" if info_festivo else ""
            citas_texto = f"<div style='font-size:10px;'>{num_citas} citas</div>" if num_citas > 0 else ""
            festivo_texto = f"<div style='font-size:8px;'>{info_festivo[:12]}</div>" if info_festivo else ""

            cal_html += f"<div class='cal-day {clase}' {tooltip}><strong>{dia_num}</strong>{citas_texto}{festivo_texto}</div>"

    st.markdown(f"<div style='text-align:center;'>{cal_html}</div>", unsafe_allow_html=True)

    # Leyenda
    st.markdown(f"""
    <div style='display:flex; gap:16px; justify-content:center; margin:12px 0; font-size:11px;'>
        <span><span style='display:inline-block; width:12px; height:12px; background:#0a2a1a; border:1px solid #44ff8844; border-radius:2px; vertical-align:middle;'></span> Con citas</span>
        <span><span style='display:inline-block; width:12px; height:12px; background:#1a1a0a; border:1px solid #C9A84C44; border-radius:2px; vertical-align:middle;'></span> Disponible</span>
        <span><span style='display:inline-block; width:12px; height:12px; background:#2a0a0a; border:1px solid #ff444444; border-radius:2px; vertical-align:middle;'></span> Festivo</span>
        <span><span style='display:inline-block; width:12px; height:12px; background:#1a1a1a; border:1px solid #33333366; border-radius:2px; vertical-align:middle;'></span> Domingo</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr class='dv'>", unsafe_allow_html=True)

    # ---- VISTA DEL DÍA ----
    dia_sel = st.date_input("Ver agenda del día:", value=hoy, key="dia_agenda")
    fecha_sel_str = str(dia_sel)
    festivo_hoy = festivos.get(dia_sel, "")

    if dia_sel.weekday() == 6:
        st.markdown("<div style='text-align:center; color:#555; padding:20px;'>Domingo — No hay atención</div>", unsafe_allow_html=True)
    elif festivo_hoy:
        st.markdown(f"<div style='text-align:center; color:#ff6666; padding:20px;'>Festivo: {festivo_hoy}</div>", unsafe_allow_html=True)
    else:
        params_dia = f"fecha=eq.{fecha_sel_str}&order=hora_inicio.asc"
        if filtro_odon != "Todos":
            params_dia += f"&odontologo=eq.{filtro_odon}"
        citas_dia_sel = sb_get(T_CITAS, params_dia)
        citas_activas_dia = [c for c in citas_dia_sel if c.get("estado") not in ["Cancelada", "No asistió"]]

        ocupadas = {}
        for c in citas_activas_dia:
            h_ini = c.get("hora_inicio", "")
            dur = c.get("duracion_min", 30)
            hi, mi = map(int, h_ini.split(":"))
            inicio_min = hi * 60 + mi
            for m in range(0, dur, 30):
                slot = f"{(inicio_min + m) // 60:02d}:{(inicio_min + m) % 60:02d}"
                ocupadas[slot] = c

        st.markdown(f"<div style='font-family:serif; font-size:14px; color:{COLOR}; margin:10px 0;'>Horario — {dia_sel.strftime('%A %d de %B %Y').title()}</div>", unsafe_allow_html=True)

        for hora in HORAS_LABORALES:
            if hora in ocupadas:
                c = ocupadas[hora]
                h_ini = c.get("hora_inicio", "")
                if hora == h_ini:
                    dur = c.get("duracion_min", 30)
                    h_fin = calcular_hora_fin(h_ini, dur)
                    estado_c = c.get("estado", "Agendada")
                    color_est = {"Agendada": COLOR, "Confirmada": "#44ff88", "En atención": "#ffaa44", "Completada": "#888"}.get(estado_c, "#888")
                    st.markdown(f"""
                    <div class='slot-ocupado'>
                        <div style='display:flex; justify-content:space-between; align-items:center;'>
                            <div>
                                <span style='color:{COLOR}; font-size:13px; font-weight:600;'>{h_ini} - {h_fin}</span>
                                <span style='color:#888; font-size:11px; margin-left:8px;'>({dur} min)</span>
                            </div>
                            <span style='color:{color_est}; font-size:10px; letter-spacing:1px;'>{estado_c.upper()}</span>
                        </div>
                        <div style='color:#e0e0e0; font-size:13px; margin-top:4px;'><strong>{c.get('paciente_nombre', '—')}</strong> — {c.get('procedimiento', '—')}</div>
                        <div style='color:#666; font-size:11px;'>Dr(a). {c.get('odontologo', '—')} {(' | ' + c.get('sede', '')) if c.get('sede') else ''}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='slot-libre'>{hora} — Disponible</div>", unsafe_allow_html=True)

    st.markdown("<hr class='dv'>", unsafe_allow_html=True)

    # ---- AGENDAR CITA ----
    with st.expander("➕ Agendar nueva cita"):
        if pacientes_list and procedimientos_list:
            ag1, ag2 = st.columns(2)
            with ag1:
                pac_opciones = {f"{p.get('nombre')} (CC: {p.get('cedula', 'N/A')})": p for p in pacientes_list}
                pac_sel = st.selectbox("Paciente", list(pac_opciones.keys()), key="ag_pac")
                paciente = pac_opciones[pac_sel]

                proc_opciones = {f"{p.get('nombre')} ({p.get('duracion_min')} min — {formato_cop(p.get('costo'))})": p for p in procedimientos_list}
                proc_sel = st.selectbox("Procedimiento", list(proc_opciones.keys()), key="ag_proc")
                procedimiento = proc_opciones[proc_sel]

                odon_sel = st.selectbox("Odontólogo", [o.get("nombre") for o in odontologos_list] if odontologos_list else ["Sin odontólogos"], key="ag_odon")

            with ag2:
                ag_fecha = st.date_input("Fecha", value=hoy, key="ag_fecha")
                ag_hora = st.selectbox("Hora de inicio", HORAS_LABORALES, key="ag_hora")
                duracion = procedimiento.get("duracion_min", 30)
                st.markdown(f"**Duración:** {duracion} minutos")
                st.markdown(f"**Hora fin:** {calcular_hora_fin(ag_hora, duracion)}")

            ag_notas = st.text_area("Notas", key="ag_notas", placeholder="Observaciones de la cita...")

            if st.button("✓ Agendar cita", key="btn_agendar"):
                ag_fecha_str = str(ag_fecha)
                citas_ese_dia = sb_get(T_CITAS, f"fecha=eq.{ag_fecha_str}&odontologo=eq.{odon_sel}")

                if ag_fecha.weekday() == 6:
                    st.error("No se pueden agendar citas en domingo")
                elif ag_fecha in festivos:
                    st.error(f"Día festivo: {festivos[ag_fecha]}")
                elif hay_conflicto(citas_ese_dia, ag_hora, duracion):
                    st.error("Ese horario se cruza con otra cita. Elige otra hora.")
                else:
                    sb_post(T_CITAS, {
                        "paciente_id": paciente.get("id"),
                        "paciente_nombre": paciente.get("nombre"),
                        "odontologo": odon_sel,
                        "procedimiento": procedimiento.get("nombre"),
                        "duracion_min": duracion,
                        "fecha": ag_fecha_str,
                        "hora_inicio": ag_hora,
                        "hora_fin": calcular_hora_fin(ag_hora, duracion),
                        "estado": "Agendada",
                        "notas": ag_notas
                    })
                    st.success(f"✓ Cita agendada: {paciente.get('nombre')} — {ag_fecha_str} {ag_hora}")
                    st.rerun()
        else:
            st.warning("Registra pacientes y procedimientos primero")

    # ---- GESTIONAR CITAS DEL DÍA ----
    if dia_sel.weekday() != 6 and not festivo_hoy:
        citas_gestion = sb_get(T_CITAS, f"fecha=eq.{fecha_sel_str}&order=hora_inicio.asc")
        if citas_gestion:
            st.markdown(f"<div style='font-family:serif; font-size:14px; color:{COLOR}; margin:10px 0;'>Gestionar citas del {dia_sel.strftime('%d/%m/%Y')}</div>", unsafe_allow_html=True)

            for cita in citas_gestion:
                estado = cita.get("estado", "Agendada")
                if estado in ["Cancelada", "No asistió"]:
                    continue
                with st.expander(f"{cita.get('hora_inicio')} — {cita.get('paciente_nombre')} — {cita.get('procedimiento')}"):
                    bc1, bc2, bc3, bc4 = st.columns(4)
                    with bc1:
                        if st.button("Confirmar", key=f"conf_{cita.get('id')}"):
                            sb_patch(T_CITAS, cita.get("id"), {"estado": "Confirmada"})
                            st.rerun()
                    with bc2:
                        if st.button("Completada", key=f"comp_{cita.get('id')}"):
                            sb_patch(T_CITAS, cita.get("id"), {"estado": "Completada"})
                            st.rerun()
                    with bc3:
                        if st.button("No asistió", key=f"noasis_{cita.get('id')}"):
                            sb_patch(T_CITAS, cita.get("id"), {"estado": "No asistió"})
                            sb_post(T_ALERTAS, {
                                "tipo": "Seguimiento",
                                "titulo": f"Paciente no asistió: {cita.get('paciente_nombre')}",
                                "descripcion": f"No asistió a cita de {cita.get('procedimiento')} el {fecha_sel_str}",
                                "paciente_id": cita.get("paciente_id"),
                                "paciente_nombre": cita.get("paciente_nombre"),
                                "fecha_vencimiento": str(hoy + timedelta(days=1)),
                                "prioridad": "Alta",
                                "estado": "Pendiente"
                            })
                            st.rerun()
                    with bc4:
                        if st.button("Cancelar", key=f"canc_{cita.get('id')}"):
                            sb_patch(T_CITAS, cita.get("id"), {"estado": "Cancelada"})
                            st.rerun()

                    # Reagendar
                    st.markdown("**Reagendar:**")
                    rg1, rg2 = st.columns(2)
                    with rg1:
                        nueva_fecha = st.date_input("Nueva fecha", key=f"rf_{cita.get('id')}")
                    with rg2:
                        nueva_hora = st.selectbox("Nueva hora", HORAS_LABORALES, key=f"rh_{cita.get('id')}")
                    if st.button("Reagendar", key=f"reag_{cita.get('id')}"):
                        citas_nuevo_dia = sb_get(T_CITAS, f"fecha=eq.{nueva_fecha}&odontologo=eq.{cita.get('odontologo')}")
                        dur = cita.get("duracion_min", 30)
                        if hay_conflicto(citas_nuevo_dia, nueva_hora, dur, cita.get("id")):
                            st.error("Ese horario se cruza con otra cita")
                        else:
                            sb_patch(T_CITAS, cita.get("id"), {
                                "fecha": str(nueva_fecha),
                                "hora_inicio": nueva_hora,
                                "hora_fin": calcular_hora_fin(nueva_hora, dur),
                                "notas": (cita.get("notas") or "") + f" | Reagendada desde {fecha_sel_str} {cita.get('hora_inicio')}"
                            })
                            st.success("✓ Cita reagendada")
                            st.rerun()


# ================================================================
# PACIENTES
# ================================================================
elif menu == "Pacientes":
    pacientes = sb_get(T_PACIENTES, "order=created_at.desc")
    st.markdown(f"<div style='font-family:serif; font-size:20px; color:{COLOR};'>Pacientes</div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"<div class='mc'><div class='mn'>{len(pacientes)}</div><div class='ml'>TOTAL</div></div>", unsafe_allow_html=True)
    with col2:
        activos = len([p for p in pacientes if p.get("estado") == "Activo"])
        st.markdown(f"<div class='mc'><div class='mn' style='color:#44ff88;'>{activos}</div><div class='ml'>ACTIVOS</div></div>", unsafe_allow_html=True)

    st.markdown("<hr class='dv'>", unsafe_allow_html=True)

    with st.expander("➕ Nuevo paciente"):
        np1, np2 = st.columns(2)
        with np1:
            p_nombre = st.text_input("Nombre completo", key="p_nom")
            p_cedula = st.text_input("Cédula", key="p_ced")
            p_telefono = st.text_input("Teléfono", key="p_tel")
            p_email = st.text_input("Email", key="p_email")
            p_direccion = st.text_input("Dirección", key="p_dir")
        with np2:
            p_nacimiento = st.date_input("Fecha nacimiento", value=date(1990, 1, 1), key="p_nac")
            p_eps = st.text_input("EPS", key="p_eps")
            p_antecedentes = st.text_area("Antecedentes médicos", key="p_ant")
            p_alergias = st.text_input("Alergias", key="p_ale")
            p_medicamentos = st.text_input("Medicamentos", key="p_med")

        if st.button("✓ Registrar paciente", key="btn_pac"):
            if p_nombre:
                sb_post(T_PACIENTES, {
                    "nombre": p_nombre, "cedula": p_cedula, "telefono": p_telefono,
                    "email": p_email, "direccion": p_direccion,
                    "fecha_nacimiento": str(p_nacimiento), "eps": p_eps,
                    "antecedentes": p_antecedentes, "alergias": p_alergias,
                    "medicamentos": p_medicamentos, "estado": "Activo"
                })
                st.success("✓ Paciente registrado")
                st.rerun()

    st.markdown("<hr class='dv'>", unsafe_allow_html=True)

    buscar = st.text_input("Buscar paciente:", key="buscar_pac", placeholder="Nombre o cédula...")

    for pac in pacientes:
        if buscar and buscar.lower() not in (pac.get("nombre", "") + pac.get("cedula", "")).lower():
            continue
        with st.expander(f"{pac.get('nombre')} — CC: {pac.get('cedula', 'N/A')}"):
            pp1, pp2 = st.columns(2)
            with pp1:
                st.markdown(f"**Teléfono:** {pac.get('telefono', '—')}")
                st.markdown(f"**Email:** {pac.get('email', '—')}")
                st.markdown(f"**EPS:** {pac.get('eps', '—')}")
                st.markdown(f"**Nacimiento:** {pac.get('fecha_nacimiento', '—')}")
            with pp2:
                st.markdown(f"**Dirección:** {pac.get('direccion', '—')}")
                st.markdown(f"**Antecedentes:** {pac.get('antecedentes', '—')}")
                st.markdown(f"**Alergias:** {pac.get('alergias', '—')}")
                st.markdown(f"**Medicamentos:** {pac.get('medicamentos', '—')}")

            num = (pac.get("telefono") or "").replace(" ", "").replace("-", "")
            if num:
                st.markdown(f"<a href='https://wa.me/57{num}' target='_blank' style='color:{COLOR};'>📱 WhatsApp</a>", unsafe_allow_html=True)

    if pacientes and st.button("📊 Exportar pacientes", key="exp_pac"):
        df = pd.DataFrame(pacientes)
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        st.download_button("Descargar", buf.getvalue(), f"pacientes_{date.today()}.xlsx")


# ================================================================
# HISTORIA CLÍNICA
# ================================================================
elif menu == "Historias":
    st.markdown(f"<div style='font-family:serif; font-size:20px; color:{COLOR};'>Historia Clínica</div>", unsafe_allow_html=True)

    if pacientes_list:
        pac_opciones = {f"{p.get('nombre')} (CC: {p.get('cedula', 'N/A')})": p for p in pacientes_list}
        pac_sel = st.selectbox("Seleccionar paciente:", list(pac_opciones.keys()), key="hc_pac")
        paciente = pac_opciones[pac_sel]

        historias = sb_get(T_HISTORIAS, f"paciente_id=eq.{paciente.get('id')}&order=fecha.desc")

        st.markdown("<hr class='dv'>", unsafe_allow_html=True)

        with st.expander("➕ Nueva consulta"):
            hc1, hc2 = st.columns(2)
            with hc1:
                hc_motivo = st.text_area("Motivo de consulta", key="hc_mot")
                hc_diagnostico = st.text_area("Diagnóstico", key="hc_diag")
                hc_dientes = st.text_input("Dientes tratados", key="hc_dientes", placeholder="Ej: 11, 21, 36")
            with hc2:
                hc_tratamiento = st.text_area("Tratamiento realizado", key="hc_trat")
                hc_odontologo = st.selectbox("Odontólogo", [o.get("nombre") for o in odontologos_list] if odontologos_list else ["—"], key="hc_odon")
                hc_obs = st.text_area("Observaciones", key="hc_obs")

            if st.button("✓ Registrar consulta", key="btn_hc"):
                sb_post(T_HISTORIAS, {
                    "paciente_id": paciente.get("id"),
                    "paciente_nombre": paciente.get("nombre"),
                    "motivo_consulta": hc_motivo,
                    "diagnostico": hc_diagnostico,
                    "tratamiento_realizado": hc_tratamiento,
                    "dientes_tratados": hc_dientes,
                    "odontologo": hc_odontologo,
                    "observaciones": hc_obs
                })
                st.success("✓ Consulta registrada en historia clínica")
                st.rerun()

        st.markdown(f"<div style='font-family:serif; font-size:14px; color:{COLOR}; margin:12px 0;'>Historial ({len(historias)} consultas)</div>", unsafe_allow_html=True)

        for h in historias:
            st.markdown(f"""
            <div style='background:#111; border:1px solid {COLOR}22; border-left:3px solid {COLOR}; border-radius:4px; padding:12px 16px; margin:6px 0;'>
                <div style='display:flex; justify-content:space-between;'>
                    <span style='color:{COLOR}; font-size:13px; font-weight:600;'>{h.get('fecha', '—')}</span>
                    <span style='color:#888; font-size:11px;'>Dr(a). {h.get('odontologo', '—')}</span>
                </div>
                <div style='color:#e0e0e0; font-size:12px; margin-top:6px;'><strong>Motivo:</strong> {h.get('motivo_consulta', '—')}</div>
                <div style='color:#ccc; font-size:12px;'><strong>Diagnóstico:</strong> {h.get('diagnostico', '—')}</div>
                <div style='color:#ccc; font-size:12px;'><strong>Tratamiento:</strong> {h.get('tratamiento_realizado', '—')}</div>
                <div style='color:#888; font-size:11px;'>Dientes: {h.get('dientes_tratados', '—')} | Obs: {h.get('observaciones', '—')}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("Registra pacientes primero")


# ================================================================
# PLANES DE TRATAMIENTO
# ================================================================
elif menu == "Tratamientos":
    st.markdown(f"<div style='font-family:serif; font-size:20px; color:{COLOR};'>Planes de Tratamiento</div>", unsafe_allow_html=True)

    tratamientos = sb_get(T_TRATAMIENTOS, "order=created_at.desc")
    en_curso = [t for t in tratamientos if t.get("estado") == "En curso"]
    pendiente_cobro = sum((t.get("costo_total", 0) or 0) - (t.get("abonado", 0) or 0) for t in en_curso)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"<div class='mc'><div class='mn'>{len(en_curso)}</div><div class='ml'>EN CURSO</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='mc'><div class='mn'>{len(tratamientos)}</div><div class='ml'>TOTAL</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='mc'><div class='mn' style='font-size:28px;'>{formato_cop(pendiente_cobro)}</div><div class='ml'>PENDIENTE COBRO</div></div>", unsafe_allow_html=True)

    st.markdown("<hr class='dv'>", unsafe_allow_html=True)

    with st.expander("➕ Nuevo plan de tratamiento"):
        if pacientes_list:
            tp_pac = st.selectbox("Paciente", [f"{p.get('nombre')}" for p in pacientes_list], key="tp_pac")
            pac_data = next((p for p in pacientes_list if p.get("nombre") == tp_pac), {})
            tp1, tp2 = st.columns(2)
            with tp1:
                tp_tipo = st.text_input("Tipo de tratamiento", key="tp_tipo", placeholder="Ortodoncia, Implante, Diseño de sonrisa...")
                tp_desc = st.text_area("Descripción", key="tp_desc")
                tp_sesiones = st.number_input("Sesiones totales", min_value=1, value=1, key="tp_ses")
            with tp2:
                tp_costo = st.number_input("Costo total (COP)", min_value=0, step=50000, key="tp_costo")
                tp_odon = st.selectbox("Odontólogo", [o.get("nombre") for o in odontologos_list] if odontologos_list else ["—"], key="tp_odon")
                tp_prox = st.date_input("Próxima sesión", key="tp_prox")

            if st.button("✓ Crear plan", key="btn_tp"):
                sb_post(T_TRATAMIENTOS, {
                    "paciente_id": pac_data.get("id"),
                    "paciente_nombre": tp_pac,
                    "tipo": tp_tipo, "descripcion": tp_desc,
                    "sesiones_total": tp_sesiones, "sesiones_completadas": 0,
                    "costo_total": tp_costo, "abonado": 0,
                    "odontologo": tp_odon,
                    "fecha_proxima_sesion": str(tp_prox),
                    "estado": "En curso"
                })
                st.success("✓ Plan de tratamiento creado")
                st.rerun()

    st.markdown("<hr class='dv'>", unsafe_allow_html=True)

    filtro_tp = st.selectbox("Filtrar:", ["En curso", "Todos", "Completados"], key="f_tp")

    for t in tratamientos:
        if filtro_tp == "En curso" and t.get("estado") != "En curso":
            continue
        if filtro_tp == "Completados" and t.get("estado") != "Completado":
            continue

        sesiones = t.get("sesiones_completadas", 0)
        total_ses = t.get("sesiones_total", 1)
        pct = int((sesiones / total_ses * 100)) if total_ses > 0 else 0
        saldo = (t.get("costo_total", 0) or 0) - (t.get("abonado", 0) or 0)

        with st.expander(f"{t.get('paciente_nombre')} — {t.get('tipo')} — {sesiones}/{total_ses} sesiones ({pct}%)"):
            st.markdown(f"**Descripción:** {t.get('descripcion', '—')}")
            st.markdown(f"**Costo total:** {formato_cop(t.get('costo_total'))} | **Abonado:** {formato_cop(t.get('abonado'))} | **Saldo:** {formato_cop(saldo)}")
            st.markdown(f"**Próxima sesión:** {t.get('fecha_proxima_sesion', '—')}")
            st.progress(pct / 100)

            if t.get("estado") == "En curso":
                tc1, tc2 = st.columns(2)
                with tc1:
                    if st.button("+ Registrar sesión", key=f"ses_{t.get('id')}"):
                        nuevas = sesiones + 1
                        datos_update = {"sesiones_completadas": nuevas}
                        if nuevas >= total_ses:
                            datos_update["estado"] = "Completado"
                        sb_patch(T_TRATAMIENTOS, t.get("id"), datos_update)
                        st.rerun()
                with tc2:
                    prox = st.date_input("Próxima sesión", key=f"prox_{t.get('id')}")
                    if st.button("Actualizar próxima", key=f"upx_{t.get('id')}"):
                        sb_patch(T_TRATAMIENTOS, t.get("id"), {"fecha_proxima_sesion": str(prox)})
                        st.rerun()


# ================================================================
# FACTURACIÓN / PAGOS
# ================================================================
elif menu == "Pagos":
    pagos = sb_get(T_PAGOS, "order=created_at.desc")
    st.markdown(f"<div style='font-family:serif; font-size:20px; color:{COLOR};'>Facturación y Pagos</div>", unsafe_allow_html=True)

    total_ingresos = sum(p.get("monto", 0) or 0 for p in pagos)
    hoy_str = date.today().strftime("%Y-%m")
    pagos_mes = [p for p in pagos if (p.get("fecha_pago") or "")[:7] == hoy_str]
    ingresos_mes = sum(p.get("monto", 0) or 0 for p in pagos_mes)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"<div class='mc'><div class='mn' style='font-size:28px;color:#44ff88;'>{formato_cop(ingresos_mes)}</div><div class='ml'>ESTE MES</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='mc'><div class='mn' style='font-size:28px;'>{formato_cop(total_ingresos)}</div><div class='ml'>TOTAL</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='mc'><div class='mn'>{len(pagos)}</div><div class='ml'>TRANSACCIONES</div></div>", unsafe_allow_html=True)

    st.markdown("<hr class='dv'>", unsafe_allow_html=True)

    with st.expander("➕ Registrar pago"):
        if pacientes_list:
            pg_pac = st.selectbox("Paciente", [p.get("nombre") for p in pacientes_list], key="pg_pac")
            pac_data = next((p for p in pacientes_list if p.get("nombre") == pg_pac), {})
            pg1, pg2 = st.columns(2)
            with pg1:
                pg_concepto = st.text_input("Concepto", key="pg_con", placeholder="Abono ortodoncia, Limpieza, Control...")
                pg_monto = st.number_input("Monto (COP)", min_value=0, step=10000, key="pg_monto")
            with pg2:
                pg_metodo = st.selectbox("Método de pago", ["Efectivo", "Transferencia", "Tarjeta", "Nequi", "Daviplata"], key="pg_met")
                pg_fecha = st.date_input("Fecha", value=date.today(), key="pg_fecha")

            if st.button("✓ Registrar pago", key="btn_pg"):
                if pg_monto > 0 and pg_concepto:
                    sb_post(T_PAGOS, {
                        "paciente_id": pac_data.get("id"),
                        "paciente_nombre": pg_pac,
                        "concepto": pg_concepto,
                        "monto": pg_monto,
                        "metodo_pago": pg_metodo,
                        "fecha_pago": str(pg_fecha)
                    })
                    st.success("✓ Pago registrado")
                    st.rerun()

    st.markdown("<hr class='dv'>", unsafe_allow_html=True)

    for pago in pagos[:30]:
        met_color = {"Efectivo": "#44ff88", "Transferencia": "#4488ff", "Tarjeta": "#C9A84C", "Nequi": "#aa44ff", "Daviplata": "#ff4444"}.get(pago.get("metodo_pago"), "#888")
        st.markdown(f"""
        <div style='background:#0d0d0d; border:1px solid {COLOR}15; border-radius:4px; padding:10px 16px; margin:4px 0; display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <span style='color:#e0e0e0; font-size:13px;'><strong>{pago.get('concepto', '—')}</strong></span><br>
                <span style='color:#666; font-size:11px;'>{pago.get('paciente_nombre', '—')} · {pago.get('fecha_pago', '—')}</span>
            </div>
            <div style='text-align:right;'>
                <span style='color:#44ff88; font-size:16px; font-weight:700;'>{formato_cop(pago.get('monto'))}</span><br>
                <span style='color:{met_color}; font-size:10px;'>{pago.get('metodo_pago', '—')}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ================================================================
# ALERTAS CON SEGUIMIENTO
# ================================================================
elif menu == "Alertas":
    alertas = sb_get(T_ALERTAS, "order=fecha_vencimiento.asc")
    pendientes = [a for a in alertas if a.get("estado") == "Pendiente"]
    hoy = date.today()
    vencidas = [a for a in pendientes if a.get("fecha_vencimiento") and a.get("fecha_vencimiento") < str(hoy)]

    st.markdown(f"<div style='font-family:serif; font-size:20px; color:{COLOR};'>Alertas y Seguimiento</div>", unsafe_allow_html=True)

    # Pop-up de alertas urgentes
    if vencidas:
        for v in vencidas[:3]:
            st.markdown(f"""
            <div class='pop-alerta'>
                <div style='display:flex; justify-content:space-between;'>
                    <span style='color:#ff8844; font-size:13px; font-weight:600;'>⚠️ {v.get('titulo')}</span>
                    <span style='color:#ff6644; font-size:11px;'>VENCIDA: {v.get('fecha_vencimiento')}</span>
                </div>
                <div style='color:#ccc; font-size:12px; margin-top:4px;'>{v.get('descripcion', '—')}</div>
                <div style='color:#888; font-size:11px; margin-top:2px;'>Paciente: {v.get('paciente_nombre', '—')}</div>
            </div>
            """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"<div class='mc'><div class='mn' style='color:#ff4444;'>{len(vencidas)}</div><div class='ml'>VENCIDAS</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='mc'><div class='mn' style='color:#ffaa44;'>{len(pendientes)}</div><div class='ml'>PENDIENTES</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='mc'><div class='mn'>{len(alertas)}</div><div class='ml'>TOTAL</div></div>", unsafe_allow_html=True)

    st.markdown("<hr class='dv'>", unsafe_allow_html=True)

    with st.expander("➕ Nueva alerta"):
        al_titulo = st.text_input("Título", key="al_tit")
        al_desc = st.text_area("Descripción", key="al_desc")
        al1, al2 = st.columns(2)
        with al1:
            al_tipo = st.selectbox("Tipo", ["Seguimiento", "Pago pendiente", "Tratamiento incompleto", "Control", "General"], key="al_tipo")
            al_fecha = st.date_input("Fecha vencimiento", key="al_fecha")
        with al2:
            al_prioridad = st.selectbox("Prioridad", ["Normal", "Alta", "Urgente"], key="al_pri")
            al_paciente = st.selectbox("Paciente (opcional)", ["Ninguno"] + [p.get("nombre") for p in pacientes_list], key="al_pac")

        if st.button("✓ Crear alerta", key="btn_al"):
            if al_titulo:
                pac_id = None
                pac_nombre = ""
                if al_paciente != "Ninguno":
                    pac = next((p for p in pacientes_list if p.get("nombre") == al_paciente), {})
                    pac_id = pac.get("id")
                    pac_nombre = al_paciente

                sb_post(T_ALERTAS, {
                    "tipo": al_tipo, "titulo": al_titulo, "descripcion": al_desc,
                    "paciente_id": pac_id, "paciente_nombre": pac_nombre,
                    "fecha_vencimiento": str(al_fecha), "prioridad": al_prioridad,
                    "estado": "Pendiente"
                })
                st.success("✓ Alerta creada")
                st.rerun()

    st.markdown("<hr class='dv'>", unsafe_allow_html=True)

    for alerta in pendientes:
        fecha = alerta.get("fecha_vencimiento", "")
        es_vencida = fecha and fecha < str(hoy)
        icono = "🔴" if es_vencida else "🟡"
        color_a = "#ff4444" if es_vencida else "#ffaa44"

        with st.expander(f"{icono} {alerta.get('titulo')} — {fecha} — {alerta.get('tipo', '')}"):
            st.markdown(f"**Descripción:** {alerta.get('descripcion', '—')}")
            st.markdown(f"**Paciente:** {alerta.get('paciente_nombre', '—')}")
            st.markdown(f"**Prioridad:** {alerta.get('prioridad', 'Normal')}")
            st.markdown(f"<span style='color:{color_a}'>**Vence:** {fecha}</span>", unsafe_allow_html=True)

            # Acciones de seguimiento
            st.markdown(f"<div style='font-size:12px; color:{COLOR}; margin:8px 0 4px;'>Registrar acción:</div>", unsafe_allow_html=True)
            accion = st.selectbox("¿Qué se hizo?", [
                "Se llamó al paciente",
                "Se envió mensaje WhatsApp",
                "Se reprogramó cita",
                "No contestó, reintentar",
                "Paciente confirmó",
                "Paciente canceló definitivamente",
                "Resuelto"
            ], key=f"acc_{alerta.get('id')}")

            if st.button("✓ Registrar acción", key=f"rac_{alerta.get('id')}"):
                estado_nuevo = "Completada" if accion in ["Paciente confirmó", "Paciente canceló definitivamente", "Resuelto", "Se reprogramó cita"] else "Pendiente"
                sb_patch(T_ALERTAS, alerta.get("id"), {
                    "accion_realizada": accion,
                    "fecha_accion": datetime.now().isoformat(),
                    "responsable_accion": st.session_state.usuario,
                    "estado": estado_nuevo
                })
                st.success(f"✓ Acción registrada: {accion}")
                st.rerun()


# ================================================================
# DOCUMENTOS
# ================================================================
elif menu == "Documentos":
    st.markdown(f"<div style='font-family:serif; font-size:20px; color:{COLOR};'>Documentos</div>", unsafe_allow_html=True)

    archivo = st.file_uploader("Subir documento", type=["pdf", "png", "jpg", "jpeg", "doc", "docx", "xlsx"])
    if archivo and st.button("📤 Subir", key="btn_up"):
        if subir_documento(archivo):
            st.success("✓ Documento subido")
        else:
            st.error("Error al subir")

    st.markdown("<hr class='dv'>", unsafe_allow_html=True)

    docs = listar_documentos()
    if docs:
        for doc in docs:
            nombre_doc = doc.get("name", "")
            if nombre_doc:
                url_doc = f"{SUPABASE_URL}/storage/v1/object/public/documentos/{SLUG}/{nombre_doc}"
                st.markdown(f"""
                <div style='background:#111; border:1px solid {COLOR}22; padding:10px 16px; border-radius:4px; margin:4px 0; display:flex; justify-content:space-between;'>
                    <span style='color:#e0e0e0; font-size:13px;'>📄 {nombre_doc}</span>
                    <a href='{url_doc}' target='_blank' style='color:{COLOR}; font-size:11px;'>Descargar</a>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.markdown("<div style='text-align:center; color:#555; padding:30px;'>No hay documentos</div>", unsafe_allow_html=True)


# -------- CONFIGURACIÓN (solo admin) --------
if st.session_state.rol == "admin":
    st.markdown("<hr class='dv'>", unsafe_allow_html=True)
    with st.expander("⚙️ Configuración — Odontólogos y Procedimientos"):
        st.markdown(f"<div style='font-size:12px; color:{COLOR};'>Registrar odontólogo:</div>", unsafe_allow_html=True)
        co1, co2, co3 = st.columns(3)
        with co1:
            od_nombre = st.text_input("Nombre", key="od_nom")
        with co2:
            od_esp = st.text_input("Especialidad", key="od_esp")
        with co3:
            if st.button("Agregar", key="btn_od"):
                if od_nombre:
                    sb_post(T_ODONTOLOGOS, {"nombre": od_nombre, "especialidad": od_esp, "activo": True})
                    st.success(f"✓ {od_nombre} agregado")
                    st.rerun()

        if odontologos_list:
            st.markdown("**Odontólogos registrados:**")
            for o in odontologos_list:
                st.markdown(f"- {o.get('nombre')} — {o.get('especialidad', '—')}")

        st.markdown("<hr class='dv'>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:12px; color:{COLOR};'>Procedimientos registrados:</div>", unsafe_allow_html=True)
        if procedimientos_list:
            for pr in procedimientos_list:
                st.markdown(f"- {pr.get('nombre')} — {pr.get('duracion_min')} min — {formato_cop(pr.get('costo'))}")


# -------- FOOTER --------
st.markdown(f"""
<div style='text-align:center; padding:20px 0; margin-top:30px; border-top:1px solid {COLOR}22;
    font-family:serif; font-size:10px; color:{COLOR}66; letter-spacing:3px;'>
    {NOMBRE_CLINICA.upper()} — POWERED BY A.R.I.Z.A.
</div>
""", unsafe_allow_html=True)
