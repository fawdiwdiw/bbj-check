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

# =========================
# KOLOM 2: NERACA SIPD
# =========================
with col2:
    st.subheader("📥 Neraca SIPD")
    
    # 1. Ambil data SIPD yang sudah ada di DB (jika ada)
    res_sipd_db = supabase.table("neraca_sipd").select("saldo_akhir").eq("dinas", st.session_state.dinas).execute()
    total_sipd_db = sum(float(item['saldo_akhir']) for item in res_sipd_db.data) if res_sipd_db.data else 0
    
    # Status awal
    if total_sipd_db > 0 and not st.session_state.mode_revisi_sipd:
        st.info(f"Terdata di DB: Rp {format_rupiah(total_sipd_db)}")
        if st.button("🔄 Re-upload SIPD"):
            st.session_state.mode_revisi_sipd = True
            st.rerun()
            
        # Tombol Hitung Selisih HANYA muncul jika SIPD sudah ada di DB
        if st.button("🔍 Hitung Selisih & Simpan Hasil Banding"):
            st.session_state.hitung_selisih = True
    
    else:
        # Jika belum ada data atau sedang mode revisi
        file_sipd = st.file_uploader("Upload Excel SIPD", type=["xlsx"], key="u_sipd")
        
        if file_sipd:
            # Parsing File SIPD
            df_sipd_file = pd.read_excel(file_sipd) # Sesuaikan pd.read jika ada header khusus
            
            # --- LOGIKA FILTER KODE 8102 (Sesuaikan kolomnya) ---
            # Contoh: asumsikan kolom 0 adalah kode dan kolom 4 adalah saldo
            data_sipd_8102 = df_sipd_file[df_sipd_file.iloc[:, 0].str.startswith("8102", na=False)].copy()
            total_sipd_file = pd.to_numeric(data_sipd_8102.iloc[:, 4], errors='coerce').sum()
            
            st.write(f"Total Saldo (8102) di File: **Rp {format_rupiah(total_sipd_file)}**")
            st.write(f"Total Saldo (8102) di SIAP (DB): **Rp {format_rupiah(total_siap_db)}**")

            # 2. VALIDASI BALANCE
            selisih_total = abs(total_sipd_file - total_siap_db)
            
            if selisih_total > 0.01: # Pakai toleransi kecil untuk float
                st.error(f"❌ SALDO TIDAK SAMA! Selisih: Rp {format_rupiah(selisih_total)}")
                st.warning("Silahkan revisi dahulu file Excel Anda. Sistem tidak mengizinkan simpan jika belum balance.")
            else:
                st.success("✅ Saldo Balance! Data siap disimpan.")
                
                # 3. TOMBOL SIMPAN MUNCUL JIKA BALANCE
                if st.button("💾 Simpan SIPD ke Database"):
                    # Proses Delete lama & Insert baru
                    supabase.table("neraca_sipd").delete().eq("dinas", st.session_state.dinas).execute()
                    
                    to_db_sipd = []
                    for _, r in data_sipd_8102.iterrows():
                        to_db_sipd.append({
                            "dinas": st.session_state.dinas,
                            "kode_rekening": r[0], # sesuaikan index kolom
                            "nama_rekening": r[1], # sesuaikan index kolom
                            "saldo_akhir": float(r[4]),
                            "is_active": True
                        })
                    
                    supabase.table("neraca_sipd").insert(to_db_sipd).execute()
                    st.session_state.mode_revisi_sipd = False
                    st.success("Berhasil simpan data SIPD!")
                    st.rerun()

# =========================
# LOGIKA PERBANDINGAN (Tabel Hasil)
# =========================
if st.session_state.get("hitung_selisih"):
    st.divider()
    # (Logika pengambilan data df_siap dan df_sipd dari Supabase seperti sebelumnya)
    # ...
    # Setelah df_merge terbentuk:
    st.subheader("📝 Jurnal Hasil Perbandingan")
    st.dataframe(df_merge)
    
    if st.button("🚀 Finalisasi & Simpan Jurnal Selisih"):
        # Logika simpan ke tabel hasil_perbandingan
        # ...
        st.balloons()
        st.success("Data perbandingan telah dibukukan ke database.")
