import streamlit as st
import re
import time
import pandas as pd
from docx import Document
from pypdf import PdfReader
from thefuzz import fuzz # <--- Thư viện mới: Trái tim của thuật toán

# --- 1. CẤU HÌNH & CSS (GIỮ NGUYÊN) ---
st.set_page_config(
    page_title="Citation Pro | Fuzzy Check",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; }
    .css-card { border-radius: 15px; padding: 20px; background-color: white; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; border: 1px solid #e9ecef; }
    .alert-error { padding: 12px; border-radius: 8px; background-color: #fff5f5; border-left: 5px solid #fc8181; color: #c53030; margin-bottom: 10px; font-size: 15px; }
    .alert-warning { padding: 12px; border-radius: 8px; background-color: #fffaf0; border-left: 5px solid #f6ad55; color: #c05621; margin-bottom: 10px; font-size: 15px; }
    .alert-success { padding: 12px; border-radius: 8px; background-color: #f0fff4; border-left: 5px solid #48bb78; color: #2f855a; font-weight: bold; }
    div[data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px; border-radius: 10px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- 2. HÀM ĐỌC & XỬ LÝ TEXT ---

def extract_text_from_docx(file):
    try:
        doc = Document(file)
        full_text = []
        for para in doc.paragraphs: full_text.append(para.text)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs: full_text.append(para.text)
        return "\n".join(full_text)
    except: return "ERROR_DOC"

def extract_text_from_pdf(file):
    try:
        reader = PdfReader(file)
        text = ""
        for page in reader.pages: text += page.extract_text() + "\n"
        return text
    except: return "ERROR_PDF"

def preprocess_text(text):
    """
    Làm sạch văn bản triệt để trước khi xử lý
    """
    # 1. Nối các từ bị ngắt dòng (Rah-\n mati -> Rahmati)
    text = re.sub(r'-\s*\n\s*', '', text)
    # 2. Xóa toàn bộ dấu xuống dòng (biến thành 1 dòng dài để regex không bị đứt)
    text = text.replace('\n', ' ').replace('\r', ' ')
    # 3. Xóa khoảng trắng thừa
    text = re.sub(r'\s+', ' ', text)
    return text

def is_legal_or_standard(text):
    text_lower = text.lower()
    keywords = [
        'tcvn', 'qcvn', 'iso', 'luật', 'nghị định', 'quyết định', 'thông tư', 
        'chỉ thị', 'qđ-ttg', 'nd-cp', 'tt-btnmt', 'luat', 'nghi dinh', 
        'quyet dinh', 'thong tu', 'tiêu chuẩn', 'quy chuẩn', 'chính phủ', 
        'quốc hội', 'bộ tài nguyên', 'bộ xây dựng', 'bộ khoa học'
    ]
    for kw in keywords:
        if kw in text_lower:
            return True
    return False

# --- 3. LOGIC FUZZY MATCHING (MỚI) ---

def check_citation_fuzzy(cit_name, cit_year, refs_list, threshold=85):
    """
    Sử dụng Fuzzy Logic để so sánh độ tương đồng.
    threshold=85: Nghĩa là giống nhau > 85% thì coi là ĐÚNG.
    """
    # Nếu là văn bản pháp luật -> Bỏ qua luôn
    if is_legal_or_standard(cit_name): return True

    # Làm sạch tên trích dẫn (Bỏ et al, và nnk...)
    clean_cit = re.sub(r'(et al\.?|và nnk\.?|và cộng sự|& cs\.?|&|and)', ' ', cit_name, flags=re.IGNORECASE).strip()
    
    for ref in refs_list:
        # Điều kiện 1: Năm phải có trong dòng Ref (Năm là con số chính xác, không fuzzy được)
        if str(cit_year) in ref:
            # Điều kiện 2: So sánh tên bằng Fuzzy
            # token_set_ratio: Cực mạnh trong việc so sánh chuỗi bị đảo từ hoặc chèn từ thừa.
            # VD: "Rahmati" vs "Rah-mati et al" -> Score rất cao
            score = fuzz.token_set_ratio(clean_cit, ref)
            
            if score >= threshold:
                return True
    return False

def find_citations_v8(text):
    citations = []
    # Pattern 1: (Name, Year)
    # Đã preprocess text thành 1 dòng nên regex đơn giản hơn
    for match in re.finditer(r'\(([^)]*?\d{4}[^)]*?)\)', text):
        content = match.group(1)
        for part in content.split(';'):
            part = part.strip()
            year_match = re.search(r'(\d{4})[a-z]?', part) 
            if year_match:
                year = year_match.group(1)
                # Loại bỏ dấu : và , ở cuối tên
                name_part = part[:year_match.start()].strip().rstrip(',:').strip()
                
                # Bộ lọc rác cơ bản
                if len(name_part) > 1 and len(name_part) < 80 and not is_legal_or_standard(name_part):
                     # Lọc thêm ngày tháng nếu còn sót
                    if not re.search(r'(tháng|ngày|trước|sau|hình|bảng)', name_part.lower()):
                        citations.append({"name": name_part, "year": year, "full": f"({name_part}, {year})"})

    # Pattern 2: Name (Year)
    for match in re.finditer(r'([A-ZÀ-ỹ][A-Za-zÀ-ỹ\s&.\-]{1,60}?)\s*\(\s*(\d{4})\s*\)', text):
        raw_name = match.group(1).strip()
        year = match.group(2)
        if not is_legal_or_standard(raw_name) and not re.search(r'(tháng|ngày|trước|sau|hình|bảng)', raw_name.lower()):
             citations.append({"name": raw_name, "year": year, "full": f"{raw_name} ({year})"})

    # Lọc trùng
    unique_citations = []
    seen = set()
    for c in citations:
        key = f"{c['name']}_{c['year']}"
        if key not in seen:
            unique_citations.append(c)
            seen.add(key)
    return unique_citations

# --- 4. GIAO DIỆN CHÍNH ---

with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #0d6efd;'>🧠 Citation Pro (AI)</h2>", unsafe_allow_html=True)
    st.markdown("---")
    uploaded_file = st.file_uploader("📂 **Upload File (.docx / .pdf)**", type=['docx', 'pdf'])
    st.caption("Version 8.0 (Fuzzy Logic) | Build by Quan HUMG")

if not uploaded_file:
    st.markdown("<div style='text-align: center; padding: 50px;'>", unsafe_allow_html=True)
    st.title("Công cụ Kiểm tra Trích dẫn (Sử dụng AI Fuzzy Logic)")
    st.markdown("### 🚀 Xử lý tốt lỗi xuống dòng, chính tả, dấu câu")
    st.image("https://cdn-icons-png.flaticon.com/512/2103/2103633.png", width=120)
    st.info("👈 Tải file báo cáo bên trái để bắt đầu")
    st.markdown("</div>", unsafe_allow_html=True)

else:
    with st.container():
        with st.status("Đang phân tích...", expanded=True) as status:
            time.sleep(0.3)
            st.write("📄 Đang đọc file...")
            if uploaded_file.name.endswith('.docx'):
                raw_text = extract_text_from_docx(uploaded_file)
            else:
                raw_text = extract_text_from_pdf(uploaded_file)
            
            if raw_text.startswith("ERROR"):
                st.error("Lỗi đọc file!")
                st.stop()

            st.write("🧹 Đang làm sạch văn bản (nối từ, xóa xuống dòng)...")
            # --- BƯỚC PREPROCESS QUAN TRỌNG ---
            # Tách phần Ref và Body trước khi Preprocess để tránh gộp lẫn lộn
            matches = list(re.finditer(r"(tài liệu tham khảo|references)", raw_text, re.IGNORECASE))
            if not matches:
                body_raw = raw_text
                ref_raw = raw_text
                st.toast("Không tìm thấy mục References riêng biệt.", icon="⚠️")
            else:
                split_idx = matches[-1].end()
                body_raw = raw_text[:matches[-1].start()]
                ref_raw = raw_text[split_idx:]
            
            # Xử lý text sau khi đã tách vùng
            body_text = preprocess_text(body_raw)
            # Ref text thì tách dòng dựa trên quy tắc riêng (VD: có năm)
            # Hoặc đơn giản là split theo enter gốc, nhưng do file lỗi nên ta split thông minh hơn
            # Ở đây ta giữ nguyên ref_raw để split dòng, nhưng khi so sánh sẽ clean từng dòng
            ref_lines = [line.strip() for line in ref_raw.split('\n') if len(line.strip()) > 10 and re.search(r'\d{4}', line)]

            st.write("🧠 Đang chạy thuật toán Fuzzy Matching...")
            citations = find_citations_v8(body_text)

            # --- CHECK MISSING ---
            missing_refs = []
            for cit in citations:
                if not check_citation_fuzzy(cit['name'], cit['year'], ref_lines):
                    missing_refs.append(cit['full'])

            # --- CHECK UNUSED ---
            unused_refs = []
            for ref in ref_lines:
                if is_legal_or_standard(ref): continue
                
                # Logic ngược: Lấy năm ref, tìm các cite cùng năm, rồi fuzzy match ngược lại
                ref_year_match = re.search(r'\d{4}', ref)
                if ref_year_match:
                    r_year = ref_year_match.group(0)
                    same_year_cites = [c for c in citations if c['year'] == r_year]
                    
                    is_found = False
                    if same_year_cites:
                        for c in same_year_cites:
                            # Check ngược: Liệu tên trong Cite có khớp với Ref này không?
                            if check_citation_fuzzy(c['name'], c['year'], [ref]):
                                is_found = True
                                break
                    if not is_found:
                        unused_refs.append(ref)
            
            status.update(label="✅ Hoàn tất!", state="complete", expanded=False)

    # --- DASHBOARD ---
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("Tổng trích dẫn", len(citations), border=True)
    with m2: st.metric("Danh mục Ref", len(ref_lines), border=True)
    with m3: st.metric("Lỗi thiếu Ref", len(missing_refs), delta="-{}".format(len(missing_refs)) if missing_refs else "OK", delta_color="inverse", border=True)
    with m4: st.metric("Lỗi thừa Ref", len(unused_refs), delta="-{}".format(len(unused_refs)) if unused_refs else "OK", delta_color="inverse", border=True)

    st.write("")
    tab1, tab2, tab3 = st.tabs(["🚫 THIẾU REF (Missing)", "⚠️ THỪA REF (Unused)", "📋 DỮ LIỆU"])

    with tab1:
        if missing_refs:
            for i in missing_refs: st.markdown(f'<div class="alert-error">❌ <b>{i}</b></div>', unsafe_allow_html=True)
        else: st.markdown('<div class="alert-success">Tuyệt vời! Không thiếu trích dẫn nào.</div>', unsafe_allow_html=True)

    with tab2:
        if unused_refs:
            for i in unused_refs: st.markdown(f'<div class="alert-warning">⚠️ {i}</div>', unsafe_allow_html=True)
        else: st.markdown('<div class="alert-success">Danh mục tài liệu chuẩn.</div>', unsafe_allow_html=True)

    with tab3:
        c1, c2 = st.columns(2)
        with c1: 
            st.caption("Citations found")
            st.write(citations)
        with c2: 
            st.caption("Reference Lines")
            st.write(ref_lines)
