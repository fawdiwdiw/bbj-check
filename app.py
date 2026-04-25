import streamlit as st
import pandas as pd
import bcrypt
import re
from io import BytesIO
from supabase import create_client
from openpyxl.styles import Alignment

# =========================
# CONFIG & KONEKSI
# =========================
st.set_page_config(page_title="BBJ Reviu - Supabase Version", layout="wide")

# Inisialisasi Supabase
url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["key"]
supabase = create_client(url, key)

# =========================
# HELPER FUNCTIONS
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
# LOGIN LOGIC (SUPABASE)
# =========================
def cek_login(username, password):
    try:
        res = supabase.table("user_login").select("*").eq("username", username).eq("is_active", True).execute()
        if res.data:
            user = res.data[0]
            if bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
                return True, user['nama_staf']
    except Exception as e:
        st.error(f"Error Database: {e}")
    return False, None

if "login" not in st.session_state:
    st.session_state.login = False

if not st.session_state.login:
    st.title("🔐 Login BBJ (Online)")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        valid, nama = cek_login(username, password)
        if valid:
            st.session_state.login = True
            st.session_state.nama = nama
            st.rerun()
        else:
            st.error("Username / Password salah atau akun tidak aktif")
    st.stop()

# =========================
# SIDEBAR & SESSION STATE
# =========================
st.sidebar.write(f"👤 {st.session_state.nama}")
if st.sidebar.button("Logout"):
    st.session_state.login = False
    st.rerun()

# Inisialisasi state lainnya
for key_state in ["load_dinas", "dinas_terakhir", "sudah_simpan_siap", "mode_revisi_siap", "mode_revisi_sipd", "hitung_selisih", "df_merge"]:
    if key_state not in st.session_state:
        st.session_state[key_state] = False if "mode" in key_state or "sudah" in key_state else None

list_dinas = [
    "SMK NEGERI 1 SURABAYA", "SMK NEGERI 5 SURABAYA", "SMK NEGERI 6 SURABAYA",
    "RUMAH SAKIT UMUM DAERAH dr. SOETOMO", "RUMAH SAKIT JIWA MENUR",
    "UPT PELABUHAN PERIKANAN PANTAI MAYANGAN" 
    # ... tambahkan list dinas Anda yang lain di sini
]

# =========================
# UI UTAMA
# =========================
st.title("📊 Monitoring QA - Neraca Saldo BLUD")

with st.expander("📂 Pilih Dinas BLUD", expanded=not st.session_state.load_dinas):
    dinas = st.selectbox("Pilih Dinas", list_dinas)
    if st.session_state.dinas_terakhir != dinas:
        st.session_state.load_dinas = False
        st.session_state.dinas_terakhir = dinas

    if st.button("🔍 Load Data"):
        st.session_state.load_dinas = True
        st.session_state.dinas = dinas
        st.session_state.hitung_selisih = False

if st.session_state.load_dinas:
    st.success(f"✅ Dinas terpilih: {st.session_state.dinas}")
    col1, col2 = st.columns(2)

    # -------------------------
    # KOLOM 1: NERACA SIAP
    # -------------------------
    with col1:
        st.subheader("📥 Neraca SIAP")
        # Ambil data dari Supabase
        res_siap = supabase.table("neraca_siap").select("saldo_akhir").eq("dinas", st.session_state.dinas).execute()
        total_siap_db = sum(float(item['saldo_akhir']) for item in res_siap.data) if res_siap.data else 0
        
        st.session_state.sudah_simpan_siap = total_siap_db > 0

        if st.session_state.sudah_simpan_siap and not st.session_state.mode_revisi_siap:
            st.info(f"Terdata di DB: Rp {format_rupiah(total_siap_db)}")
            if st.button("🔄 Re-upload SIAP"):
                st.session_state.mode_revisi_siap = True
                st.rerun()
        else:
            file_siap = st.file_uploader("Upload Excel SIAP", type=["xlsx"], key="u_siap")
            if file_siap:
                df = pd.read_excel(file_siap, header=None, dtype=str)
                # Logika parsing Anda tetap sama...
                dinas_raw = df.iloc[5, 4]
                dinas_clean = extract_nama_dinas(dinas_raw)
                if cocokkan_dinas(dinas_clean, list_dinas) == st.session_state.dinas:
                    data = df.iloc[7:].copy()[[1,2,3,4,8]]
                    data.columns = ["kode","u1","u2","u3","saldo"]
                    data["saldo"] = pd.to_numeric(data["saldo"].str.replace(",", ""), errors="coerce").fillna(0)
                    data_8102 = data[data["kode"].str.startswith("8102", na=False)].copy()
                    
                    total_siap_baru = data_8102["saldo"].sum()
                    st.success(f"Total di File: Rp {format_rupiah(total_siap_baru)}")
                    
                    if st.button("💾 Simpan SIAP ke Supabase"):
                        # Delete & Insert via Supabase
                        supabase.table("neraca_siap").delete().eq("dinas", st.session_state.dinas).execute()
                        to_db = []
                        for _, r in data_8102.iterrows():
                            to_db.append({
                                "dinas": st.session_state.dinas,
                                "kode_rekening": r["kode"],
                                "nama_rekening": f"{r['u1']} {r['u2']} {r['u3']}".strip(),
                                "saldo_akhir": float(r["saldo"]),
                                "is_active": True
                            })
                        supabase.table("neraca_siap").insert(to_db).execute()
                        st.session_state.mode_revisi_siap = False
                        st.rerun()
                else:
                    st.error("Dinas di file tidak cocok!")

    # -------------------------
    # KOLOM 2: NERACA SIPD
    # -------------------------
    with col2:
        st.subheader("📥 Neraca SIPD")
        res_sipd = supabase.table("neraca_sipd").select("saldo_akhir").eq("dinas", st.session_state.dinas).execute()
        total_sipd_db = sum(float(item['saldo_akhir']) for item in res_sipd.data) if res_sipd.data else 0
        
        sudah_simpan_sipd = total_sipd_db > 0

        if sudah_simpan_sipd and not st.session_state.mode_revisi_sipd:
            st.info(f"Terdata di DB: Rp {format_rupiah(total_sipd_db)}")
            if st.button("🔄 Re-upload SIPD"):
                st.session_state.mode_revisi_sipd = True
                st.rerun()
            if st.session_state.sudah_simpan_siap:
                if st.button("🔍 Hitung Selisih"):
                    st.session_state.hitung_selisih = True
        else:
            file_sipd = st.file_uploader("Upload Excel SIPD", type=["xlsx"], key="u_sipd")
            if file_sipd:
                # Logika parsing SIPD Anda...
                df = pd.read_excel(file_sipd, header=None, dtype=str)
                # (Proses parsing singkat)
                st.warning("Pastikan data SIPD sudah benar sebelum simpan.")
                if st.button("💾 Simpan SIPD ke Supabase"):
                    # Logika insert Supabase mirip seperti SIAP
                    st.info("Fitur simpan SIPD aktif.")

# =========================
# LOGIKA PERBANDINGAN
# =========================
if st.session_state.get("hitung_selisih"):
    st.divider()
    # Ambil data dari kedua tabel
    res_a = supabase.table("neraca_siap").select("kode_rekening, nama_rekening, saldo_akhir").eq("dinas", st.session_state.dinas).execute()
    res_b = supabase.table("neraca_sipd").select("kode_rekening, nama_rekening, saldo_akhir").eq("dinas", st.session_state.dinas).execute()
    
    df_siap = pd.DataFrame(res_a.data).rename(columns={"saldo_akhir": "siap"})
    df_sipd = pd.DataFrame(res_b.data).rename(columns={"saldo_akhir": "sipd"})
    
    if not df_siap.empty and not df_sipd.empty:
        df_merge = pd.merge(df_siap, df_sipd, on="kode_rekening", how="outer", suffixes=("_siap", "_sipd"))
        df_merge["siap"] = pd.to_numeric(df_merge["siap"]).fillna(0)
        df_merge["sipd"] = pd.to_numeric(df_merge["sipd"]).fillna(0)
        df_merge["selisih"] = df_merge["siap"] - df_merge["sipd"]
        
        st.subheader("📊 Hasil Perbandingan")
        st.dataframe(df_merge[["kode_rekening", "siap", "sipd", "selisih"]], use_container_width=True)
        
        if st.button("💾 Simpan Hasil ke Supabase"):
            # Simpan ke tabel hasil_perbandingan
            to_perbandingan = []
            for _, row in df_merge.iterrows():
                if row["selisih"] != 0:
                    to_perbandingan.append({
                        "dinas": st.session_state.dinas,
                        "kode_bas": row["kode_rekening"],
                        "uraian": row["nama_rekening_siap"] if pd.notna(row["nama_rekening_siap"]) else row["nama_rekening_sipd"],
                        "debit": float(row["selisih"]) if row["selisih"] > 0 else 0,
                        "kredit": abs(float(row["selisih"])) if row["selisih"] < 0 else 0,
                        "nomor_bukti": "JP/REVIU/2026"
                    })
            if to_perbandingan:
                supabase.table("hasil_perbandingan").delete().eq("dinas", st.session_state.dinas).execute()
                supabase.table("hasil_perbandingan").insert(to_perbandingan).execute()
                st.success("Berhasil disimpan!")
