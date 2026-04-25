import streamlit as st
import pandas as pd
import bcrypt
import re
from supabase import create_client
from io import BytesIO
from openpyxl.styles import Alignment

st.set_page_config(page_title="BBJ Reviu", layout="wide")

# =========================
# SUPABASE CONNECTION
# =========================
url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["key"]
supabase = create_client(url, key)

# =========================
# LOGIN FUNCTION
# =========================
def cek_login(username, password):
    res = supabase.table("user_login")\
        .select("*")\
        .eq("username", username)\
        .eq("is_active", True)\
        .execute()

    if res.data:
        user = res.data[0]
        if bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
            return True, user["nama_staf"]
    return False, None

# =========================
# LOGIN UI
# =========================
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
            st.error("Username / Password salah")
    st.stop()

# =========================
# SIDEBAR
# =========================
st.sidebar.write(f"👤 {st.session_state.nama}")
if st.sidebar.button("Logout"):
    st.session_state.login = False
    st.rerun()

# =========================
# SESSION INIT
# =========================
defaults = {
    "load_dinas": False,
    "dinas_terakhir": None,
    "sudah_simpan_siap": False,
    "mode_revisi_siap": False,
    "trigger_revisi_siap": 0,
    "mode_revisi_sipd": False,
    "trigger_revisi_sipd": 0,
    "hitung_selisih": False,
    "df_merge": None
}
for k,v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================
# LIST DINAS (SINGKATKAN JIKA MAU)
# =========================
list_dinas = [
    "SMK NEGERI 1 SURABAYA",
    "SMK NEGERI 5 SURABAYA",
    "SMK NEGERI 6 SURABAYA",
    "RUMAH SAKIT UMUM DAERAH dr. SOETOMO",
    "RUMAH SAKIT JIWA MENUR",
    "UPT PELABUHAN PERIKANAN PANTAI MAYANGAN"
]

# =========================
# HELPER
# =========================
def extract_nama_dinas(text):
    return re.sub(r"^\s*\(.*?\)\s*", "", str(text)).strip()

def normalisasi_nama(nama):
    return nama.upper().replace(".", "").strip()

def cocokkan_dinas(nama_excel):
    nama_excel_norm = normalisasi_nama(nama_excel)
    for d in list_dinas:
        if normalisasi_nama(d) in nama_excel_norm:
            return d
    return None

def format_rupiah(angka):
    return f"{angka:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# =========================
# UI
# =========================
st.title("📊 Upload Neraca Saldo BLUD")

with st.expander("📂 Pilih Dinas BLUD", expanded=True):

    dinas = st.selectbox("Pilih Dinas", list_dinas)

    if st.session_state.dinas_terakhir != dinas:
        st.session_state.load_dinas = False
        st.session_state.dinas_terakhir = dinas

    if st.button("🔍 Load"):
        st.session_state.load_dinas = True
        st.session_state.dinas = dinas

# =========================
# MAIN
# =========================
if st.session_state.load_dinas:

    st.success(f"✅ Dinas: {st.session_state.dinas}")
    col1, col2 = st.columns(2)

    # =========================
    # SIAP
    # =========================
    with col1:

        res = supabase.table("neraca_siap")\
            .select("saldo_akhir")\
            .eq("dinas", st.session_state.dinas)\
            .execute()

        total_db = sum(float(x["saldo_akhir"]) for x in res.data) if res.data else 0
        st.session_state.sudah_simpan_siap = total_db > 0

        st.subheader("📥 Neraca SIAP")

        if st.session_state.sudah_simpan_siap and not st.session_state.mode_revisi_siap:

            st.info(f"Total DB: Rp {format_rupiah(total_db)}")

            if st.button("🔄 Upload Ulang SIAP"):
                st.session_state.mode_revisi_siap = True
                st.session_state.trigger_revisi_siap += 1
                st.rerun()

        else:

            file = st.file_uploader("Upload SIAP", type=["xlsx"], key=f"siap_{st.session_state.trigger_revisi_siap}")

            if file:
                df = pd.read_excel(file, header=None, dtype=str)

                dinas_file = extract_nama_dinas(df.iloc[5,4])
                match = cocokkan_dinas(dinas_file)

                if match != st.session_state.dinas:
                    st.error("Dinas tidak sesuai")
                    st.stop()

                data = df.iloc[7:].copy()[[1,2,3,4,8]]
                data.columns = ["kode","u1","u2","u3","saldo"]

                data["kode"] = data["kode"].astype(str)
                data_8102 = data[data["kode"].str.startswith("8102")].copy()

                data_8102["nama"] = (
                    data_8102["u1"].fillna("")+" "+
                    data_8102["u2"].fillna("")+" "+
                    data_8102["u3"].fillna("")
                ).str.strip()

                data_8102["saldo"] = pd.to_numeric(
                    data_8102["saldo"].str.replace(",", ""),
                    errors="coerce"
                ).fillna(0)

                total = data_8102["saldo"].sum()
                st.success(f"Total: Rp {format_rupiah(total)}")

                # VALIDASI BBJ
                if not data_8102[data_8102["kode"]=="810299999999"]["saldo"].sum()==0:
                    st.error("❌ Masih ada BBJ")
                    st.stop()

                if st.button("💾 Simpan SIAP"):
                    supabase.table("neraca_siap").delete().eq("dinas", match).execute()

                    supabase.table("neraca_siap").insert([
                        {
                            "dinas": match,
                            "kode_rekening": r["kode"],
                            "nama_rekening": r["nama"],
                            "saldo_akhir": float(r["saldo"]),
                            "is_active": True
                        } for _,r in data_8102.iterrows()
                    ]).execute()

                    st.rerun()

    # =========================
    # SIPD
    # =========================
    with col2:

        res = supabase.table("neraca_sipd")\
            .select("saldo_akhir")\
            .eq("dinas", st.session_state.dinas)\
            .execute()

        total_db = sum(float(x["saldo_akhir"]) for x in res.data) if res.data else 0
        sudah_simpan_sipd = total_db > 0

        res_siap = supabase.table("neraca_siap")\
            .select("saldo_akhir")\
            .eq("dinas", st.session_state.dinas)\
            .execute()

        total_siap = sum(float(x["saldo_akhir"]) for x in res_siap.data) if res_siap.data else 0

        st.subheader("📥 Neraca SIPD")

        if sudah_simpan_sipd and not st.session_state.mode_revisi_sipd:

            st.info(f"Total DB: Rp {format_rupiah(total_db)}")

            if st.button("🔄 Upload Ulang SIPD"):
                st.session_state.mode_revisi_sipd = True
                st.session_state.trigger_revisi_sipd += 1
                st.rerun()

            if st.session_state.sudah_simpan_siap:
                if st.button("🔍 Hitung Selisih SIAP vs SIPD"):
                    st.session_state.hitung_selisih = True

        else:

            file = st.file_uploader("Upload SIPD", type=["xlsx"], key=f"sipd_{st.session_state.trigger_revisi_sipd}")

            if file:
                df = pd.read_excel(file, header=None, dtype=str)

                dinas_file = extract_nama_dinas(df.iloc[2,2])
                match = cocokkan_dinas(dinas_file)

                if match != st.session_state.dinas:
                    st.error("Dinas tidak sesuai")
                    st.stop()

                data = df.iloc[7:].copy()[[0,1,8,9]]
                data.columns = ["kode","nama","debit","kredit"]

                data["kode"] = data["kode"].str.replace(".","")

                def clean(x):
                    if pd.isna(x): return 0
                    return pd.to_numeric(str(x).replace(".","").replace(",","."), errors="coerce")

                data["debit"] = data["debit"].apply(clean).fillna(0)
                data["kredit"] = data["kredit"].apply(clean).fillna(0)

                data["saldo"] = data["debit"] - data["kredit"]
                data_8102 = data[data["kode"].str.startswith("8102")]

                total = data_8102["saldo"].sum()

                if total != total_siap:
                    st.error("❌ Tidak balance dengan SIAP")
                    st.stop()

                st.success("✅ Balance")

                if st.button("💾 Simpan SIPD"):
                    supabase.table("neraca_sipd").delete().eq("dinas", match).execute()

                    supabase.table("neraca_sipd").insert([
                        {
                            "dinas": match,
                            "kode_rekening": r["kode"],
                            "nama_rekening": r["nama"],
                            "saldo_akhir": float(r["saldo"]),
                            "is_active": True
                        } for _,r in data_8102.iterrows()
                    ]).execute()

                    st.rerun()

# =========================
# PERBANDINGAN + EXPORT
# =========================
if st.session_state.get("hitung_selisih"):

    res1 = supabase.table("neraca_siap").select("*").eq("dinas", st.session_state.dinas).execute()
    res2 = supabase.table("neraca_sipd").select("*").eq("dinas", st.session_state.dinas).execute()

    df1 = pd.DataFrame(res1.data)
    df2 = pd.DataFrame(res2.data)

    df1 = df1.rename(columns={"saldo_akhir":"siap"})
    df2 = df2.rename(columns={"saldo_akhir":"sipd"})

    df = pd.merge(df1, df2, on="kode_rekening", how="outer", suffixes=("_siap","_sipd"))
    df["nama_rekening"] = df["nama_rekening_siap"].combine_first(df["nama_rekening_sipd"])
    df["siap"] = df["siap"].fillna(0)
    df["sipd"] = df["sipd"].fillna(0)
    df["selisih"] = df["siap"] - df["sipd"]

    st.dataframe(df)

    if st.button("💾 Simpan Jurnal"):
        supabase.table("hasil_perbandingan").delete().eq("dinas", st.session_state.dinas).execute()

        supabase.table("hasil_perbandingan").insert([
            {
                "nomor_bukti": "JP",
                "tanggal_bukti": "2025-12-31",
                "keterangan": "Jurnal",
                "kode_bas": r["kode_rekening"],
                "uraian": r["nama_rekening"],
                "debit": r["selisih"] if r["selisih"]>0 else 0,
                "kredit": abs(r["selisih"]) if r["selisih"]<0 else 0,
                "keterangan_rinci": "-",
                "dinas": st.session_state.dinas,
                "is_active": True
            } for _,r in df.iterrows() if r["selisih"]!=0
        ]).execute()

    # EXPORT
    res = supabase.table("hasil_perbandingan").select("*").eq("dinas", st.session_state.dinas).execute()
    if res.data:

        df = pd.DataFrame(res.data)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)

        st.download_button("📥 Download Excel", data=output, file_name="jurnal.xlsx")
