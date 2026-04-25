import streamlit as st
import pandas as pd
import bcrypt
import re
from supabase import create_client

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
# SESSION INIT (FULL LOKAL)
# =========================
default_states = {
    "load_dinas": False,
    "dinas_terakhir": None,
    "sudah_simpan_siap": False,
    "mode_revisi_siap": False,
    "last_uploaded_siap": None,
    "trigger_revisi_siap": 0,
    "df_merge": None,
    "hitung_selisih": False
}

for k, v in default_states.items():
    if k not in st.session_state:
        st.session_state[k] = v

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
# LOAD DATA
# =========================
if st.session_state.load_dinas:

    st.success(f"✅ Dinas terpilih: {st.session_state.dinas}")

    col1, col2 = st.columns(2)

    # =========================
    # SIAP (FIX FULL RULE)
    # =========================
    with col1:

        # =========================
        # CEK DATA DI DB
        # =========================
        res = supabase.table("neraca_siap")\
            .select("saldo_akhir")\
            .eq("dinas", st.session_state.dinas)\
            .execute()

        total_db = sum(float(x["saldo_akhir"]) for x in res.data) if res.data else 0

        st.session_state.sudah_simpan_siap = total_db > 0

        # =========================
        # HEADER
        # =========================
        if st.session_state.sudah_simpan_siap:
            st.subheader("📥 Upload Neraca SIAP ✅")
        else:
            st.subheader("📥 Upload Neraca SIAP")

        # =========================
        # MODE SUDAH ADA
        # =========================
        if st.session_state.sudah_simpan_siap and not st.session_state.mode_revisi_siap:

            st.markdown(f"""
            <div style="padding:12px; border-radius:12px; background:#e6f4ea;">
                <b>✅ Neraca SIAP {st.session_state.dinas}</b><br>
                <span style="font-size:26px;font-weight:bold;">
                    Rp {format_rupiah(total_db)}
                </span>
            </div>
            """, unsafe_allow_html=True)

            if st.button("🔄 Upload Ulang"):
                st.session_state.mode_revisi_siap = True
                st.session_state.trigger_revisi_siap += 1
                st.rerun()

        # =========================
        # MODE UPLOAD
        # =========================
        else:

            file_siap = st.file_uploader(
                "Upload Excel SIAP",
                type=["xlsx"],
                key=f"siap_{st.session_state.trigger_revisi_siap}"
            )

            if file_siap:
                try:
                    df = pd.read_excel(file_siap, header=None, dtype=str)

                    dinas_raw = df.iloc[5, 4]
                    dinas_clean = extract_nama_dinas(dinas_raw)
                    dinas_match = cocokkan_dinas(dinas_clean)

                    st.info(f"📄 Dinas di file: {dinas_clean}")

                    if dinas_match == st.session_state.dinas:

                        data = df.iloc[7:].copy()[[1,2,3,4,8]]
                        data.columns = ["kode","u1","u2","u3","saldo"]

                        data["kode"] = data["kode"].astype(str).str.strip()

                        data_8102 = data[data["kode"].str.startswith("8102")].copy()

                        data_8102["nama"] = (
                            data_8102["u1"].fillna("") + " " +
                            data_8102["u2"].fillna("") + " " +
                            data_8102["u3"].fillna("")
                        ).str.strip()

                        data_8102["saldo"] = (
                            data_8102["saldo"]
                            .str.replace(",", "", regex=True)
                        )
                        data_8102["saldo"] = pd.to_numeric(data_8102["saldo"], errors="coerce").fillna(0)

                        total_saldo = data_8102["saldo"].sum()

                        st.markdown(f"""
                        <div style="padding:10px;border-radius:10px;background:#e6f4ea;">
                            <b>✅ Neraca SIAP {dinas_match}</b><br>
                            <span style="font-size:24px;font-weight:bold;">
                                Rp {format_rupiah(total_saldo)}
                            </span>
                        </div>
                        """, unsafe_allow_html=True)

                        # =========================
                        # VALIDASI BBJ
                        # =========================
                        cek_bbj = data_8102[data_8102["kode"] == "810299999999"]

                        if not cek_bbj.empty and cek_bbj["saldo"].sum() != 0:

                            nilai = cek_bbj["saldo"].sum()

                            st.error(f"""
                            ❌ Masih ada saldo BBJ:
                            Rp {format_rupiah(nilai)}
                            """)

                            st.stop()

                        else:
                            st.success("✅ Tidak ada saldo BBJ")

                            if st.button("💾 Simpan ke Database"):

                                # DELETE
                                supabase.table("neraca_siap")\
                                    .delete()\
                                    .eq("dinas", dinas_match)\
                                    .execute()

                                # INSERT
                                data_insert = []
                                for _, r in data_8102.iterrows():
                                    data_insert.append({
                                        "dinas": dinas_match,
                                        "kode_rekening": r["kode"],
                                        "nama_rekening": r["nama"],
                                        "saldo_akhir": float(r["saldo"]),
                                        "is_active": True
                                    })

                                supabase.table("neraca_siap")\
                                    .insert(data_insert)\
                                    .execute()

                                st.session_state.mode_revisi_siap = False
                                st.session_state.sudah_simpan_siap = True
                                st.rerun()

                    else:
                        st.warning("⚠️ Dinas tidak sesuai")

                except Exception as e:
                    st.error(f"Error: {e}")

# =========================
# KOLOM 2: NERACA SIPD (FINAL FIX)
# =========================
with col2:

    if "trigger_revisi_sipd" not in st.session_state:
        st.session_state.trigger_revisi_sipd = 0

    if "mode_revisi_sipd" not in st.session_state:
        st.session_state.mode_revisi_sipd = False

    # =========================
    # CEK DATA DI DB
    # =========================
    res = supabase.table("neraca_sipd") \
        .select("saldo_akhir") \
        .eq("dinas", st.session_state.dinas) \
        .execute()

    total_db = sum(float(r["saldo_akhir"]) for r in res.data) if res.data else 0
    sudah_simpan_sipd = total_db > 0

    # =========================
    # AMBIL TOTAL SIAP
    # =========================
    res_siap = supabase.table("neraca_siap") \
        .select("saldo_akhir") \
        .eq("dinas", st.session_state.dinas) \
        .execute()

    total_siap_db = sum(float(r["saldo_akhir"]) for r in res_siap.data) if res_siap.data else 0

    # =========================
    # HEADER
    # =========================
    if sudah_simpan_sipd:
        st.subheader("📥 Upload Neraca SIPD ✅")
    else:
        st.subheader("📥 Upload Neraca SIPD")

    # =========================
    # MODE: SUDAH TERSIMPAN
    # =========================
    if sudah_simpan_sipd and not st.session_state.mode_revisi_sipd:

        st.markdown(f"""
        <div style="padding:12px; border-radius:12px; background-color:#e6f4ea;">
            <b>✅ Neraca SIPD pada {st.session_state.dinas}</b><br>
            <span style="font-size:26px; font-weight:bold;">
                Rp {format_rupiah(total_db)}
            </span>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🔄 Upload Ulang SIPD"):
            st.session_state.mode_revisi_sipd = True
            st.session_state.trigger_revisi_sipd += 1
            st.rerun()

        # ✅ POSISI BENAR (SAMA DENGAN LOKAL)
        if st.session_state.sudah_simpan_siap:
            if st.button("🔍 Hitung Selisih SIAP vs SIPD"):
                st.session_state.hitung_selisih = True

    # =========================
    # MODE: UPLOAD
    # =========================
    else:

        file_sipd = st.file_uploader(
            "Upload Excel SIPD",
            type=["xlsx"],
            key=f"sipd_{st.session_state.trigger_revisi_sipd}"
        )

        if file_sipd:
            try:
                df = pd.read_excel(file_sipd, header=None, dtype=str)

                dinas_raw = df.iloc[2, 2]
                dinas_clean = extract_nama_dinas(dinas_raw)
                dinas_match = cocokkan_dinas(dinas_clean, list_dinas)

                st.info(f"📄 Dinas di file: {dinas_clean}")

                if dinas_match == st.session_state.dinas:

                    data = df.iloc[7:].copy()
                    data = data[[0,1,8,9]]
                    data.columns = ["kode","nama","debit","kredit"]

                    data["kode"] = (
                        data["kode"]
                        .astype(str)
                        .str.replace(".", "", regex=False)
                        .str.strip()
                    )

                    data_8102 = data[data["kode"].str.startswith("8102")].copy()

                    def clean_angka(x):
                        if pd.isna(x):
                            return 0
                        x = str(x)
                        x = x.replace(".", "")
                        x = x.replace(",", ".")
                        return pd.to_numeric(x, errors="coerce")

                    data_8102["debit"] = data_8102["debit"].apply(clean_angka).fillna(0)
                    data_8102["kredit"] = data_8102["kredit"].apply(clean_angka).fillna(0)

                    data_8102["saldo"] = data_8102["debit"] - data_8102["kredit"]

                    total_saldo = data_8102["saldo"].sum()

                    # ❗ VALIDASI HARUS EXACT (SAMAIN DENGAN LOKAL)
                    if total_saldo != total_siap_db:

                        selisih = total_saldo - total_siap_db

                        st.error(f"""
                        ❌ Total SIPD tidak sama dengan SIAP  
                        SIAP : Rp {format_rupiah(total_siap_db)}  
                        SIPD : Rp {format_rupiah(total_saldo)}  
                        Selisih : Rp {format_rupiah(selisih)}
                        """)
                        st.stop()
                    else:
                        st.success("✅ Total SIPD sudah sama dengan SIAP")

                    st.success("✅ Data siap disimpan")

                    if st.button("💾 Simpan SIPD ke Database"):

                        supabase.table("neraca_sipd") \
                            .delete() \
                            .eq("dinas", st.session_state.dinas) \
                            .execute()

                        to_db = []
                        for _, r in data_8102.iterrows():
                            to_db.append({
                                "dinas": st.session_state.dinas,
                                "kode_rekening": r["kode"],
                                "nama_rekening": r["nama"],
                                "saldo_akhir": float(r["saldo"]),
                                "is_active": True
                            })

                        supabase.table("neraca_sipd").insert(to_db).execute()

                        st.session_state.mode_revisi_sipd = False
                        st.rerun()

                else:
                    st.warning("⚠️ Dinas tidak sesuai")

            except Exception as e:
                st.error(f"Error: {e}")

# =========================
# PERBANDINGAN (FINAL)
# =========================
if (
    st.session_state.get("hitung_selisih", False)
    and st.session_state.sudah_simpan_siap
):

    res_siap = supabase.table("neraca_siap") \
        .select("kode_rekening,nama_rekening,saldo_akhir") \
        .eq("dinas", st.session_state.dinas).execute()

    res_sipd = supabase.table("neraca_sipd") \
        .select("kode_rekening,nama_rekening,saldo_akhir") \
        .eq("dinas", st.session_state.dinas).execute()

    df_siap = pd.DataFrame(res_siap.data)
    df_sipd = pd.DataFrame(res_sipd.data)

    df_siap = df_siap.rename(columns={"saldo_akhir": "siap"})
    df_sipd = df_sipd.rename(columns={"saldo_akhir": "sipd"})

    df_siap["siap"] = pd.to_numeric(df_siap["siap"], errors="coerce").fillna(0)
    df_sipd["sipd"] = pd.to_numeric(df_sipd["sipd"], errors="coerce").fillna(0)

    df_merge = pd.merge(
        df_siap,
        df_sipd,
        on=["kode_rekening"],
        how="outer",
        suffixes=("_siap", "_sipd")
    )

    df_merge["nama_rekening"] = df_merge["nama_rekening_siap"].combine_first(
        df_merge["nama_rekening_sipd"]
    )

    df_merge["siap"] = df_merge["siap"].fillna(0)
    df_merge["sipd"] = df_merge["sipd"].fillna(0)

    df_merge["selisih"] = df_merge["siap"] - df_merge["sipd"]

    st.session_state.df_merge = df_merge

    st.subheader("📊 Perbandingan SIAP vs SIPD")
    st.dataframe(df_merge, use_container_width=True)

    # =========================
    # SIMPAN HASIL
    # =========================
    if st.button("💾 Simpan Hasil Perbandingan"):

        supabase.table("hasil_perbandingan") \
            .delete() \
            .eq("dinas", st.session_state.dinas) \
            .execute()

        insert_data = []

        for _, row in df_merge.iterrows():

            if row["selisih"] == 0:
                continue

            debit = row["selisih"] if row["selisih"] > 0 else 0
            kredit = abs(row["selisih"]) if row["selisih"] < 0 else 0

            insert_data.append({
                "nomor_bukti": "JP Reviu Inspektorat/BBJ BLUD/2025",
                "tanggal_bukti": "2025-12-31",
                "keterangan": f"Jurnal Rinci BBJ BLUD {st.session_state.dinas}",
                "kode_bas": row["kode_rekening"],
                "uraian": row["nama_rekening"],
                "debit": debit,
                "kredit": kredit,
                "keterangan_rinci": "-",
                "dinas": st.session_state.dinas,
                "is_active": True
            })

        if insert_data:
            supabase.table("hasil_perbandingan").insert(insert_data).execute()

        st.success("✅ Hasil berhasil disimpan")
