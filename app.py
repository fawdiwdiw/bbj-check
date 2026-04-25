import streamlit as st
import pandas as pd
import bcrypt
import re
from supabase import create_client

st.set_page_config(page_title="BBJ Reviu Online", layout="wide")

# =========================
# SUPABASE
# =========================
url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["key"]
supabase = create_client(url, key)

# =========================
# HELPER
# =========================
def format_rupiah(angka):
    return f"{angka:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def extract_nama_dinas(text):
    return re.sub(r"^\s*\(.*?\)\s*", "", str(text)).strip()

def normalisasi_nama(nama):
    return nama.upper().replace(".", "").strip()

def cocokkan_dinas(nama_excel, list_dinas):
    nama_excel_norm = normalisasi_nama(nama_excel)
    for d in list_dinas:
        if normalisasi_nama(d) in nama_excel_norm:
            return d
    return None

# =========================
# LOGIN
# =========================
def cek_login(username, password):
    res = supabase.table("user_login").select("*").eq("username", username).eq("is_active", True).execute()
    if res.data:
        user = res.data[0]
        if bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
            return True, user['nama_staf']
    return False, None

if "login" not in st.session_state:
    st.session_state.login = False

if not st.session_state.login:
    st.title("🔐 Login BBJ")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        ok, nama = cek_login(u, p)
        if ok:
            st.session_state.login = True
            st.session_state.nama = nama
            st.rerun()
        else:
            st.error("Login gagal")
    st.stop()

# =========================
# SESSION INIT
# =========================
for k in ["load_dinas","mode_revisi_siap","mode_revisi_sipd","hitung_selisih"]:
    if k not in st.session_state:
        st.session_state[k] = False

# =========================
# DINAS
# =========================
list_dinas = [
    "RUMAH SAKIT UMUM DAERAH dr. SOETOMO",
    "RUMAH SAKIT JIWA MENUR"
]

# =========================
# UI
# =========================
st.title("📊 Monitoring Neraca BLUD")

dinas = st.selectbox("Pilih Dinas", list_dinas)

if st.button("Load"):
    st.session_state.load_dinas = True
    st.session_state.dinas = dinas
    st.session_state.hitung_selisih = False

# =========================
# MAIN
# =========================
if st.session_state.load_dinas:

    st.success(f"Dinas: {st.session_state.dinas}")

    col1, col2 = st.columns(2)

    # =========================
    # SIAP
    # =========================
    with col1:

        st.subheader("📥 Neraca SIAP")

        res = supabase.table("neraca_siap").select("saldo_akhir").eq("dinas", st.session_state.dinas).execute()
        total_siap_db = sum(float(x["saldo_akhir"]) for x in res.data) if res.data else 0

        sudah_siap = total_siap_db > 0

        if sudah_siap and not st.session_state.mode_revisi_siap:

            st.info(f"Rp {format_rupiah(total_siap_db)}")

            if st.button("🔄 Upload Ulang SIAP"):
                st.session_state.mode_revisi_siap = True
                st.rerun()

        else:

            file = st.file_uploader("Upload SIAP")

            if file:
                df = pd.read_excel(file, header=None, dtype=str)

                dinas_raw = df.iloc[5,4]
                dinas_clean = extract_nama_dinas(dinas_raw)

                if cocokkan_dinas(dinas_clean, list_dinas) != st.session_state.dinas:
                    st.error("Dinas tidak cocok")
                    st.stop()

                data = df.iloc[7:].copy()
                data = data[[1,2,3,4,8]]
                data.columns = ["kode","u1","u2","u3","saldo"]

                data["kode"] = data["kode"].astype(str).str.strip()
                data["saldo"] = pd.to_numeric(data["saldo"].str.replace(",",""), errors="coerce").fillna(0)

                data_8102 = data[data["kode"].str.startswith("8102")].copy()

                # VALIDASI BBJ
                cek_bbj = data_8102[data_8102["kode"]=="810299999999"]

                if not cek_bbj.empty and cek_bbj["saldo"].sum()!=0:
                    st.error("Masih ada saldo BBJ")
                    st.stop()

                total = data_8102["saldo"].sum()

                st.success(f"Rp {format_rupiah(total)}")

                if st.button("💾 Simpan SIAP"):

                    supabase.table("neraca_siap").delete().eq("dinas", st.session_state.dinas).execute()

                    rows=[]
                    for _,r in data_8102.iterrows():
                        rows.append({
                            "dinas":st.session_state.dinas,
                            "kode_rekening":r["kode"],
                            "nama_rekening":f"{r['u1']} {r['u2']} {r['u3']}".strip(),
                            "saldo_akhir":float(r["saldo"]),
                            "is_active":True
                        })

                    supabase.table("neraca_siap").insert(rows).execute()

                    st.session_state.mode_revisi_siap=False
                    st.rerun()

    # =========================
    # SIPD
    # =========================
    with col2:

        st.subheader("📥 Neraca SIPD")

        res = supabase.table("neraca_sipd").select("saldo_akhir").eq("dinas", st.session_state.dinas).execute()
        total_sipd_db = sum(float(x["saldo_akhir"]) for x in res.data) if res.data else 0

        if total_sipd_db > 0 and not st.session_state.mode_revisi_sipd:

            st.info(f"Rp {format_rupiah(total_sipd_db)}")

            if st.button("🔄 Upload Ulang SIPD"):
                st.session_state.mode_revisi_sipd=True
                st.rerun()

            if total_siap_db > 0:
                if st.button("🔍 Hitung Selisih"):
                    st.session_state.hitung_selisih=True

        else:

            file = st.file_uploader("Upload SIPD")

            if file:
                df = pd.read_excel(file, header=None, dtype=str)

                dinas_raw = df.iloc[2,2]
                dinas_clean = extract_nama_dinas(dinas_raw)

                if cocokkan_dinas(dinas_clean, list_dinas) != st.session_state.dinas:
                    st.error("Dinas tidak cocok")
                    st.stop()

                data = df.iloc[7:].copy()
                data = data[[0,1,8,9]]
                data.columns=["kode","nama","debit","kredit"]

                data["kode"]=data["kode"].str.replace(".","")

                data_8102 = data[data["kode"].str.startswith("8102")].copy()

                def clean(x):
                    if pd.isna(x): return 0
                    return float(str(x).replace(".","").replace(",","."))
                
                data_8102["debit"]=data_8102["debit"].apply(clean)
                data_8102["kredit"]=data_8102["kredit"].apply(clean)

                data_8102["saldo"]=data_8102["debit"]-data_8102["kredit"]

                total = data_8102["saldo"].sum()

                if total != total_siap_db:
                    st.error("Total tidak sama SIAP")
                    st.stop()

                st.success(f"Rp {format_rupiah(total)}")

                if st.button("💾 Simpan SIPD"):

                    supabase.table("neraca_sipd").delete().eq("dinas", st.session_state.dinas).execute()

                    rows=[]
                    for _,r in data_8102.iterrows():
                        rows.append({
                            "dinas":st.session_state.dinas,
                            "kode_rekening":r["kode"],
                            "nama_rekening":r["nama"],
                            "saldo_akhir":float(r["saldo"]),
                            "is_active":True
                        })

                    supabase.table("neraca_sipd").insert(rows).execute()

                    st.session_state.mode_revisi_sipd=False
                    st.rerun()
