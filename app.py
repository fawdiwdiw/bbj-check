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


@st.cache_data(ttl=60)
def get_siap(dinas):
    return supabase.table("neraca_siap") \
        .select("kode_rekening,nama_rekening,saldo_akhir") \
        .eq("dinas", dinas).execute().data

@st.cache_data(ttl=60)
def get_sipd(dinas):
    return supabase.table("neraca_sipd") \
        .select("kode_rekening,nama_rekening,saldo_akhir") \
        .eq("dinas", dinas).execute().data

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
    "df_merge": None,
    "boleh_simpan": False,
    "sudah_simpan_jurnal": False,
}
for k,v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================
# LIST DINAS (SINGKATKAN JIKA MAU)
# =========================
# =========================
# LIST DINAS
# =========================
list_dinas = [
    "SMK NEGERI 1 SURABAYA",
    "SMK NEGERI 5 SURABAYA",
    "SMK NEGERI 6 SURABAYA",
    "SMK NEGERI 1 BUDURAN SIDOARJO",
    "SMK NEGERI 3 BUDURAN SIDOARJO",
    "SMK NEGERI 2 MALANG",
    "SMK NEGERI 4 MALANG",
    "SMK NEGERI 11 MALANG",
    "SMK NEGERI 1 SINGOSARI MALANG",
    "SMK NEGERI 1 PANJI SITUBONDO",
    "SMK NEGERI 1 KALIPURO BANYUWANGI",
    "SMK NEGERI 2 BONDOWOSO",
    "SMK NEGERI 5 JEMBER",
    "SMK NEGERI 3 MADIUN",
    "SMK NEGERI 1 PACITAN",
    "SMK NEGERI 2 KOTA PASURUAN",
    "SMK NEGERI 3 BOYOLANGU TULUNGAGUNG",
    "SMK NEGERI 1 GLAGAH BANYUWANGI",
    "SMK NEGERI 1 TEGALAMPEL BONDOWOSO",
    "SMK NEGERI 1 JENANGAN PONOROGO",
    "SMK NEGERI 2 NGANJUK",
    "SMK NEGERI 1 BANYUWANGI",
    "SMK NEGERI 1 LUMAJANG",
    "SMK NEGERI KALIBARU BANYUWANGI",
    "SMK NEGERI 6 JEMBER",
    "SMK NEGERI DARUL ULUM BANYUWANGI",
    "SMK NEGERI 1 PASURUAN",
    "SMK NEGERI 2 TUBAN",
    "SMK NEGERI 1 GRATI PASURUAN",
    "SMK NEGERI 1 PUNGGING MOJOKERTO",
    "SMK NEGERI 10 SURABAYA",
    "SMK NEGERI 2 BATU",
    "SMK NEGERI 2 JIWAN MADIUN",
    "SMK NEGERI 2 PROBOLINGGO",
    "SMK NEGERI 7 SURABAYA",
    "SMK NEGERI 1 BENDO MAGETAN",
    "SMK NEGERI 1 NGANJUK",
    "SMK NEGERI 1 GEMPOL PASURUAN",
    "SMK NEGERI RENGEL TUBAN",

    "RUMAH SAKIT UMUM DAERAH dr. SOETOMO",
    "RUMAH SAKIT UMUM DAERAH dr. SAIFUL ANWAR",
    "RUMAH SAKIT UMUM DAERAH dr. SOEDONO MADIUN",
    "RUMAH SAKIT UMUM DAERAH HAJI PROVINSI JAWA TIMUR",
    "RUMAH SAKIT JIWA MENUR",
    "RUMAH SAKIT UMUM DAERAH KARSA HUSADA BATU",
    "RUMAH SAKIT PARU JEMBER",
    "RUMAH SAKIT UMUM DAERAH DUNGUS",
    "RUMAH SAKIT UMUM DAERAH DAHA HUSADA",
    "RUMAH SAKIT UMUM DAERAH SUMBERGLAGAH",
    "RUMAH SAKIT MATA MASYARAKAT JAWA TIMUR",
    "RUMAH SAKIT UMUM DAERAH HUSADA PRIMA",
    "RUMAH SAKIT UMUM DAERAH MOHAMMAD NOER PAMEKASAN",
    "RUMAH SAKIT PARU MANGUHARJO PROVINSI JAWA TIMUR",
    "UPT PELATIHAN KESEHATAN MASYARAKAT MURNAJATI",

    "UPT PENGEMBANGAN BENIH PADI DAN PALAWIJA",
    "UPT PENGEMBANGAN BENIH HORTIKULTURA",
    "UPT PENGEMBANGAN AGRIBISNIS TANAMAN PANGAN DAN HORTIKULTURA",

    "UPT PELABUHAN PERIKANAN PANTAI MAYANGAN",
    "UPT PELABUHAN PERIKANAN PANTAI TAMPERAN",
    "UPT PELABUHAN PERIKANAN PANTAI PONDOKDADAP"
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

        data_siap = get_siap(st.session_state.dinas)
        df_siap = pd.DataFrame(data_siap)
        
        total_db = df_siap["saldo_akhir"].astype(float).sum() if not df_siap.empty else 0

        #total_db = sum(float(x["saldo_akhir"]) for x in res.data) if res.data else 0
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
                    st.error("❌ Masih ada BBJ BLUD, Silahkan revisi dahulu")
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

        data_sipd = get_sipd(st.session_state.dinas)
        df_sipd = pd.DataFrame(data_sipd)
        
        total_db = df_sipd["saldo_akhir"].astype(float).sum() if not df_sipd.empty else 0
        st.session_state.sudah_simpan_sipd = total_db > 0

        res_siap = supabase.table("neraca_siap")\
            .select("saldo_akhir")\
            .eq("dinas", st.session_state.dinas)\
            .execute()

        total_siap = sum(float(x["saldo_akhir"]) for x in res_siap.data) if res_siap.data else 0

        st.subheader("📥 Neraca SIPD")

        if st.session_state.sudah_simpan_sipd and not st.session_state.mode_revisi_sipd:

            st.info(f"Total DB: Rp {format_rupiah(total_db)}")

            if st.button("🔄 Upload Ulang SIPD"):
                st.session_state.mode_revisi_sipd = True
                st.session_state.trigger_revisi_sipd += 1
                st.session_state.sudah_simpan_sipd = False   # 🔥 TAMBAH INI
                st.rerun()
            if st.session_state.sudah_simpan_siap:
                if st.button("🔍 Hitung Selisih SIAP vs SIPD"):
                    st.session_state.hitung_selisih = True
                    st.session_state.boleh_simpan = True
                    st.session_state.sudah_simpan_jurnal = False

        else:

            file = st.file_uploader("Upload SIPD", type=["xlsx"], key=f"sipd_{st.session_state.trigger_revisi_sipd}")

            # ✅ SIMPAN FILE KE SESSION
            if file is not None:
                st.session_state.file_sipd = file
            
            # ✅ AMBIL DARI SESSION
            if "file_sipd" in st.session_state:
                file = st.session_state.file_sipd

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
                st.session_state.data_sipd_fix = data_8102.copy()
                st.session_state.match_sipd = match

                total = data_8102["saldo"].sum()

                if abs(total - total_siap) > 1:
                    selisih = total - total_siap
                
                    st.error(f"""
                    ❌ Tidak balance dengan SIAP, Silahkan revisi dahulu  
                    SIAP : Rp {format_rupiah(total_siap)}  
                    SIPD : Rp {format_rupiah(total)}  
                    Selisih : Rp {format_rupiah(selisih)}
                    """)
                    st.stop()
                
                # kalau balance
                st.success("✅ Balance dengan SIAP")
                
                st.markdown(f"""
                <div style="padding:10px;border-radius:10px;background:#e6f4ea;">
                    <b>✅ Total SIPD</b><br>
                    <span style="font-size:24px;font-weight:bold;">
                        Rp {format_rupiah(total)}
                    </span>
                </div>
                """, unsafe_allow_html=True)

                if st.button("💾 Simpan SIPD", key="btn_simpan_sipd"):

                    if "data_sipd_fix" not in st.session_state:
                        st.error("Data belum siap disimpan")
                        st.stop()
                
                    data_8102 = st.session_state.data_sipd_fix
                    match = st.session_state.match_sipd
                    supabase.table("neraca_sipd").delete().eq("dinas", match).execute()
                    data_insert = [
                                {
                                    "dinas": match,
                                    "kode_rekening": r["kode"],
                                    "nama_rekening": r["nama"],
                                    "saldo_akhir": float(r["saldo"]),
                                    "is_active": True
                                } for _, r in data_8102.iterrows()
                            ]
                            
                            # 🔥 insert bertahap
                    for i in range(0, len(data_insert), 500):
                        supabase.table("neraca_sipd").insert(data_insert[i:i+500]).execute()
    
                    st.rerun() 

                         

# =========================
# PERBANDINGAN + EXPORT (FINAL)
# =========================
if not st.session_state.get("hitung_selisih"):
    st.stop()

    # =========================
    # AMBIL DATA
    # =========================
    df1 = pd.DataFrame(get_siap(st.session_state.dinas))
    df2 = pd.DataFrame(get_sipd(st.session_state.dinas))
    
    # =========================
    # HANDLE DF1 (SIAP)
    # =========================
    if df1.empty:
        df1 = pd.DataFrame(columns=["kode_rekening", "nama_rekening_siap", "siap"])
    else:
        df1 = df1.rename(columns={
            "saldo_akhir": "siap",
            "nama_rekening": "nama_rekening_siap"
        })
    
        if "siap" not in df1.columns:
            df1["siap"] = 0
    
    # =========================
    # HANDLE DF2 (SIPD)
    # =========================
    if df2.empty:
        df2 = pd.DataFrame(columns=["kode_rekening", "nama_rekening_sipd", "sipd"])
    else:
        df2 = df2.rename(columns={
            "saldo_akhir": "sipd",
            "nama_rekening": "nama_rekening_sipd"
        })
    
        if "sipd" not in df2.columns:
            df2["sipd"] = 0
    
    # =========================
    # PASTIKAN NUMERIC
    # =========================
    df1["siap"] = pd.to_numeric(df1["siap"], errors="coerce").fillna(0)
    df2["sipd"] = pd.to_numeric(df2["sipd"], errors="coerce").fillna(0)
    # =========================
    # MERGE (GABUNGAN)
    # =========================
    df = pd.merge(
        df1,
        df2,
        on="kode_rekening",
        how="outer"
    )

    # =========================
    # GABUNG NAMA
    # =========================
    df["nama_rekening"] = df["nama_rekening_siap"].combine_first(
        df["nama_rekening_sipd"]
    )

    # =========================
    # HANDLE NULL
    # =========================
    df["siap"] = df["siap"].fillna(0)
    df["sipd"] = df["sipd"].fillna(0)

    # =========================
    # HITUNG SELISIH
    # =========================
    df["selisih"] = df["siap"] - df["sipd"]

    # =========================
    # PILIH KOLOM FINAL
    # =========================
    df = df[[
        "kode_rekening",
        "nama_rekening",
        "siap",
        "sipd",
        "selisih"
    ]]

    # simpan session
    st.session_state.df_merge = df.copy()

    # =========================
    # FORMAT DISPLAY
    # =========================
    def fmt(x):
        return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    df_display = df.copy()
    df_display = df.round(2)
    df_display["sipd"] = df_display["sipd"].apply(fmt)
    df_display["selisih"] = df_display["selisih"].apply(fmt)

    # =========================
    # TAMPILKAN
    # =========================
    st.subheader("📊 Perbandingan SIAP vs SIPD")
    st.dataframe(df_display, use_container_width=True)

    # =========================
    # TOTAL SELISIH
    # =========================
    total_selisih = df["selisih"].sum()

    st.markdown(f"""
    <div style="
        margin-top:10px;
        padding:10px;
        border-radius:10px;
        background-color:#f0f2f6;
        text-align:right;
        font-size:20px;
        font-weight:bold;
    ">
        Total Selisih : Rp {format_rupiah(total_selisih)}
    </div>
    """, unsafe_allow_html=True)

        # =========================
    # SIMPAN JURNAL
    # =========================
    if st.session_state.boleh_simpan:
        if st.button("💾 Simpan Jurnal"):

            supabase.table("hasil_perbandingan") \
                .delete() \
                .eq("dinas", st.session_state.dinas) \
                .execute()
    
            insert_data = []
    
            df_filtered = df[df["selisih"] != 0]

            insert_data = df_filtered.apply(lambda r: {
                "nomor_bukti": "JP Reviu Inspektorat/BBJ BLUD/2025",
                "tanggal_bukti": "2025-12-31",
                "keterangan": f"Jurnal Rinci BBJ BLUD {st.session_state.dinas}",
                "kode_bas": r["kode_rekening"],
                "uraian": r["nama_rekening"],
                "debit": r["selisih"] if r["selisih"] > 0 else 0,
                "kredit": abs(r["selisih"]) if r["selisih"] < 0 else 0,
                "keterangan_rinci": "-",
                "dinas": st.session_state.dinas,
                "is_active": True
            }, axis=1).tolist()
    
            if insert_data:
                supabase.table("hasil_perbandingan").insert(insert_data).execute()
    
            st.success("✅ Jurnal berhasil disimpan")
            st.session_state.sudah_simpan_jurnal = True
    
        # =========================
        # EXPORT EXCEL (AUTO MUNCUL JIKA DATA ADA)
        # =========================
        res = supabase.table("hasil_perbandingan") \
            .select("""
                nomor_bukti,
                tanggal_bukti,
                keterangan,
                kode_bas,
                uraian,
                debit,
                kredit,
                keterangan_rinci
            """) \
            .eq("dinas", st.session_state.dinas) \
            .order("kode_bas") \
            .execute()
    
        if st.session_state.sudah_simpan_jurnal and res.data:
    
            df_export = pd.DataFrame(res.data)
    
            df_export.columns = [
                "Nomor Bukti",
                "Tanggal Bukti",
                "Keterangan",
                "Kode BAS",
                "Uraian",
                "Debit",
                "Kredit",
                "Keterangan Rinci"
            ]
    
            # kosongkan kolom A-C baris ke-2 dst
            df_export_display = df_export.copy()
            for col in ["Nomor Bukti", "Tanggal Bukti", "Keterangan"]:
                df_export_display.loc[1:, col] = ""
    
            output = BytesIO()
    
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export_display.to_excel(
                    writer,
                    index=False,
                    sheet_name='jurnal'
                )
    
                ws = writer.sheets['jurnal']
    
                # alignment
                for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=3):
                    for cell in row:
                        cell.alignment = Alignment(vertical="top")
    
                # width
                widths = {
                    "A": 45, "B": 18, "C": 60, "D": 18,
                    "E": 45, "F": 18, "G": 18, "H": 25
                }
                for col, w in widths.items():
                    ws.column_dimensions[col].width = w
    
                # ✅ FORMAT ANGKA 2 DESIMAL
                for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=6, max_col=7):
                    for cell in row:
                        cell.number_format = '0.00'
    
            output.seek(0)
    
            st.download_button(
                label="📥 Download Excel Jurnal",
                data=output,
                file_name=f"Jurnal_{st.session_state.dinas}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
