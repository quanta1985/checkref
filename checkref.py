import streamlit as st
import re
import time
import pandas as pd
from docx import Document
from pypdf import PdfReader

# --- 1. CẤU HÌNH & CSS (GIỮ NGUYÊN 100%) ---
st.set_page_config(
    page_title="Citation Pro | Công cụ Kiểm tra Trích dẫn",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; }
    .css-card { border-radius: 15px; padding: 20px; background-color: white; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; border: 1px solid #e9ecef; }
    .main-header { font-family: 'Helvetica Neue', sans-serif; color: #0d6efd; text-align: center; margin-bottom: 30px; }
    div[data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center; }
    .alert-error { padding: 12px; border-radius: 8px; background-color: #fff5f5; border-left: 5px solid #fc8181; color: #c53030; margin-bottom: 10px; font-size: 15px; }
    .alert-warning { padding: 12px; border-radius: 8px; background-color: #fffaf0; border-left: 5px solid #f6ad55; color: #c05621; margin-bottom: 10px; font-size: 15px; }
    .alert-success { padding: 12px; border-radius: 8px; background-color: #f0fff4; border-left: 5px solid #48bb78; color: #2f855a; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 2. CÁC HÀM LOGIC ---

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

# === HÀM HÀN GẮN TỪ BỊ NGẮT DÒNG (FIX LỖI RAH-MATI) ===
def heal_hyphenated_words(text):
    """
    Tìm các từ bị ngắt dòng bằng dấu gạch nối và nối chúng lại.
    VD: 'Rah-\n mati' -> 'Rahmati'
    VD: 'environ-\n ment' -> 'environment'
    """
    # Regex: Tìm dấu gạch nối (-), theo sau là có thể có khoảng trắng, rồi xuống dòng, rồi khoảng trắng
    return re.sub(r'-\s*\n\s*', '', text)

def is_legal_or_standard(text):
    text_lower = text.lower()
    keywords = [
        'tcvn', 'qcvn', 'iso', 'luật', 'nghị định', 'quyết định', 'thông tư', 
        'chỉ thị', 'qđ-ttg', 'nd-cp', 'tt-btnmt', 'luat', 'nghi dinh', 
        'quyet dinh', 'thong tu', 'tiêu chuẩn', 'quy chuẩn', 'chính phủ', 
        'quốc hội', 'bộ tài nguyên', 'bộ xây dựng'
    ]
    for kw in keywords:
        if kw in text_lower:
            return True
    return False

def is_valid_citation_candidate(name_part, year):
    try:
        y = int(year)
        if y < 1800 or y > 2030: return False
    except: return False
    
    name_lower = name_part.lower()
    blacklist = ['tháng', 'ngày', 'năm', 'lúc', 'trước', 'sau', 'khoảng', 'hình', 'bảng', 'biểu', 'sơ đồ', 'phương trình', 'công thức', 'hệ số', 'giá trị', 'tỉ lệ', 'kết quả', 'đoạn', 'phần', 'mục', 'bản đồ']
    for word in blacklist:
        if f" {word} " in f" {name_lower} ": return False
    
    invalid_chars = ['/', '=', '>', '<', '%', '+']
    for char in invalid_chars:
        if char in name_part: return False
        
    if len(name_part) > 80: return False
    return True

def clean_text_segment(text_segment):
    # Vẫn giữ hàm này để clean cục bộ bên trong regex
    text_segment = text_segment.replace('\n', ' ').replace('\r', ' ')
    text_segment = re.sub(r'\s+', ' ', text_segment)
    return text_segment

def find_citations_v7(text):
    citations = []
    
    # Pattern 1: (...)
    # Regex tìm nội dung trong ngoặc đơn
    for match in re.finditer(r'\(([^)]*?\d{4}[^)]*?)\)', text):
        raw_content = match.group(1)
        content = clean_text_segment(raw_content)
        
        for part in content.split(';'):
            part = part.strip()
            year_match = re.search(r'(\d{4})[a-z]?', part) 
            if year_match:
                year = year_match.group(1)
                name_part = part[:year_match.start()].strip().rstrip(',').rstrip(':').strip()
                
                if len(name_part) > 1 and is_valid_citation_candidate(name_part, year):
                    citations.append({"name": name_part, "year": year, "full": f"({name_part}, {year})"})
    
    # Pattern 2: Name (Year)
    pattern_open = r'([A-ZÀ-ỹ][A-Za-zÀ-ỹ\s&.\n-]{1,60}?)\s*\(\s*(\d{4})\s*\)'
    for match in re.finditer(pattern_open, text):
        raw_name = match.group(1)
        year = match.group(2)
        name_clean = clean_text_segment(raw_name).strip()
        
        if is_valid_citation_candidate(name_clean, year):
            citations.append({"name": name_clean, "year": year, "full": f"{name_clean} ({year})"})
    
    # Lọc trùng
    unique_citations = []
    seen = set()
    for c in citations:
        key = f"{c['name']}_{c['year']}"
        if key not in seen:
            unique_citations.append(c)
            seen.add(key)
    return unique_citations

def check_citation_in_refs(cit_name, cit_year, refs_list):
    if is_legal_or_standard(cit_name): return True

    stopwords_regex = r'(et al\.?|và nnk\.?|và cộng sự|& cs\.?|&|and|,\s*cs)'
    clean_cit_name = re.sub(stopwords_regex, ' ', cit_name, flags=re.IGNORECASE).strip()
    cit_tokens = [t.lower() for t in clean_cit_name.split() if len(t) > 1]
    
    for ref in refs_list:
        if cit_year in ref:
            # Clean ref line để so sánh chính xác
            ref_clean = ref.replace('\n', ' ')
            ref_lower = ref_clean.lower()
            
            if clean_cit_name.lower() in ref_lower: return True
            match_token_count = 0
            for token in cit_tokens:
                if token in ref_lower: match_token_count += 1
            if len(cit_tokens) > 0 and match_token_count >= 1: return True
    return False

# --- 3. GIAO DIỆN (GIỮ NGUYÊN) ---

with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #0d6efd;'>🎓 Citation Pro</h2>", unsafe_allow_html=True)
    st.markdown("---")
    uploaded_file = st.file_uploader("📂 **Tải báo cáo lên đây**:", type=['docx', 'pdf'])
    st.markdown("---")
    with st.expander("ℹ️ Hướng dẫn sử dụng"):
        st.markdown("""
        1. Upload file báo cáo (.docx/.pdf).
        2. Chờ hệ thống tự động quét.
        3. Xem kết quả tại Dashboard bên phải.
        """)
    st.caption("Version 7.3 (Hyphen Fix) | Build by Quan HUMG")

if not uploaded_file:
    st.markdown("<div style='text-align: center; padding: 50px;'>", unsafe_allow_html=True)
    st.title("Công cụ Rà soát Trích dẫn & Tài liệu tham khảo")
    st.markdown("### 🚀 Nhanh chóng - Chính xác - Chuyên nghiệp")
    st.markdown("Kiểm tra sự đồng bộ giữa *Trích dẫn trong bài (In-text)* và *Danh mục tham khảo (References)*.")
    st.image("https://cdn-icons-png.flaticon.com/512/8662/8662266.png", width=150)
    st.info("👈 Vui lòng tải file báo cáo ở thanh bên trái để bắt đầu.")
    st.markdown("</div>", unsafe_allow_html=True)

else:
    with st.container():
        with st.status("Đang phân tích dữ liệu...", expanded=True) as status:
            time.sleep(0.3)
            st.write("📄 Đang đọc nội dung file...")
            if uploaded_file.name.endswith('.docx'):
                full_text = extract_text_from_docx(uploaded_file)
            else:
                full_text = extract_text_from_pdf(uploaded_file)
            
            if full_text.startswith("ERROR"):
                status.update(label="❌ Lỗi đọc file!", state="error")
                st.stop()

            st.write("🔍 Đang tách danh mục và trích dẫn...")
            matches = list(re.finditer(r"(tài liệu tham khảo|references)", full_text, re.IGNORECASE))
            if not matches:
                ref_text = full_text
                body_text = full_text
                st.toast("⚠️ Không tìm thấy tiêu đề References, quét toàn bộ.", icon="⚠️")
            else:
                split_idx = matches[-1].end()
                body_text = full_text[:matches[-1].start()]
                ref_text = full_text[split_idx:]
            
            # === ÁP DỤNG FIX LỖI RAH-MATI (Cắt nối từ) TẠI ĐÂY ===
            body_text = heal_hyphenated_words(body_text)
            
            ref_lines = [line.strip() for line in ref_text.split('\n') if len(line.strip()) > 10 and re.search(r'\d{4}', line)]
            citations = find_citations_v7(body_text)

            # Logic Check
            missing_refs = []
            for cit in citations:
                if is_legal_or_standard(cit['name']): continue
                if not check_citation_in_refs(cit['name'], cit['year'], ref_lines):
                    missing_refs.append(cit['full'])

            unused_refs = []
            for ref in ref_lines:
                if is_legal_or_standard(ref): continue
                ref_year_match = re.search(r'\d{4}', ref)
                if ref_year_match:
                    r_year = ref_year_match.group(0)
                    same_year_cites = [c for c in citations if c['year'] == r_year]
                    is_found = False
                    if same_year_cites:
                        for c in same_year_cites:
                            if check_citation_in_refs(c['name'], c['year'], [ref]):
                                is_found = True
                                break
                    if not is_found:
                        unused_refs.append(ref)
            
            status.update(label="✅ Đã phân tích xong!", state="complete", expanded=False)

    st.markdown("<h3 style='margin-top: 20px;'>📊 Tổng quan (Dashboard)</h3>", unsafe_allow_html=True)
    
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("Tổng trích dẫn", len(citations), border=True)
    with m2: st.metric("Danh mục Ref", len(ref_lines), border=True)
    err_missing = len(missing_refs)
    err_unused = len(unused_refs)
    with m3: st.metric("Lỗi thiếu Ref", err_missing, delta="-{}".format(err_missing) if err_missing > 0 else "OK", delta_color="inverse", border=True)
    with m4: st.metric("Lỗi thừa Ref", err_unused, delta="-{}".format(err_unused) if err_unused > 0 else "OK", delta_color="inverse", border=True)

    st.write("") 

    tab_miss, tab_unused, tab_data = st.tabs(["🚫 TRÍCH DẪN THIẾU (Missing)", "⚠️ DANH MỤC THỪA (Unused)", "📋 DỮ LIỆU CHI TIẾT"])

    with tab_miss:
        st.markdown(f"**Danh sách {len(missing_refs)} trích dẫn có trong bài nhưng không tìm thấy trong danh mục:**")
        if missing_refs:
            for item in missing_refs:
                st.markdown(f'<div class="alert-error">❌ <b>{item}</b> - <i>Không tìm thấy nguồn</i></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="alert-success">🎉 Tuyệt vời! Không có trích dẫn nào bị thiếu.</div>', unsafe_allow_html=True)

    with tab_unused:
        st.markdown(f"**Danh sách {len(unused_refs)} tài liệu có trong danh mục nhưng chưa được trích dẫn:**")
        if unused_refs:
            for item in unused_refs:
                st.markdown(f'<div class="alert-warning">⚠️ {item}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="alert-success">🎉 Danh mục tài liệu rất gọn gàng.</div>', unsafe_allow_html=True)

    with tab_data:
        st.markdown("#### Tra cứu dữ liệu gốc")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.caption("Dữ liệu Trích dẫn (In-text)")
            if citations:
                df_cit = pd.DataFrame(citations)
                st.dataframe(df_cit, use_container_width=True, hide_index=True)
            else: st.info("Không có dữ liệu")
        with col_d2:
            st.caption("Dữ liệu Danh mục (References)")
            if ref_lines:
                df_ref = pd.DataFrame(ref_lines, columns=["Nội dung tham khảo"])
                st.dataframe(df_ref, use_container_width=True, hide_index=True)
            else: st.info("Không có dữ liệu")
