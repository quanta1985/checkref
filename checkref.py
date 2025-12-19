import streamlit as st
import re
import time
from docx import Document
from pypdf import PdfReader

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(
    page_title="Citation Pro Checker v6",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS ---
st.markdown("""
<style>
    .big-font { font-size:20px !important; font-weight: bold; }
    .success-box { padding:15px; border-radius:10px; background-color:#d4edda; color:#155724; border: 1px solid #c3e6cb; }
    .error-box { padding:15px; border-radius:10px; background-color:#f8d7da; color:#721c24; border: 1px solid #f5c6cb; }
    .warning-box { padding:15px; border-radius:10px; background-color:#fff3cd; color:#856404; border: 1px solid #ffeeba; }
</style>
""", unsafe_allow_html=True)

# --- 1. HÀM ĐỌC FILE ---
def extract_text_from_docx(file):
    try:
        doc = Document(file)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        full_text.append(para.text)
        return "\n".join(full_text)
    except:
        return "ERROR_DOC"

def extract_text_from_pdf(file):
    try:
        reader = PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except:
        return "ERROR_PDF"

# --- 2. BỘ LỌC THÔNG MINH (CHẶN NGÀY THÁNG, SỐ LIỆU) ---
def is_valid_citation_candidate(name_part, year):
    # 1. Kiểm tra năm hợp lệ (Chỉ chấp nhận từ 1800 đến 2030)
    # Loại bỏ số liệu kiểu "6742"
    try:
        y = int(year)
        if y < 1800 or y > 2030:
            return False
    except:
        return False

    name_lower = name_part.lower()

    # 2. Từ khóa BLACKLIST (Nếu tên chứa từ này -> Không phải trích dẫn)
    # Loại bỏ: tháng 8, ngày 1, hình 1, bảng 2, hệ số, phương trình...
    blacklist = [
        'tháng', 'ngày', 'năm', 'lúc', 'trước', 'sau', 'khoảng', 
        'hình', 'bảng', 'biểu', 'sơ đồ', 'phương trình', 'công thức',
        'hệ số', 'giá trị', 'tỉ lệ', 'kết quả', 'đoạn', 'phần', 'mục'
    ]
    
    for word in blacklist:
        # Kiểm tra từ đơn để tránh bắt nhầm tên người (VD: "Nguyệt" chứa "ngày" -> check kỹ hơn nếu cần)
        # Ở đây dùng check đơn giản: ' từ ' hoặc bắt đầu bằng 'từ '
        if f" {word} " in f" {name_lower} ": 
            return False

    # 3. Ký tự toán học/đặc biệt BLACKLIST
    # Loại bỏ: 1/7/2025 (chứa /), Scf = 0 (chứa =), > <
    invalid_chars = ['/', '=', '>', '<', '%', '+']
    for char in invalid_chars:
        if char in name_part:
            return False
            
    # 4. Kiểm tra độ dài tên
    # Tên tác giả thường không quá dài (> 50 ký tự thường là văn bản rác)
    if len(name_part) > 60:
        return False
        
    return True

# --- 3. HÀM TÌM TRÍCH DẪN (NÂNG CẤP V6) ---
def find_citations_v6(text):
    citations = []
    
    # --- Pattern trong ngoặc (...) ---
    parenthetical_pattern = r'\(([^)]*?\d{4}[^)]*?)\)'
    
    for match in re.finditer(parenthetical_pattern, text):
        content = match.group(1)
        
        # Tách theo dấu chấm phẩy (đa trích dẫn)
        parts = content.split(';')
        
        for part in parts:
            part = part.strip()
            # Tìm 4 số cuối cùng
            year_match = re.search(r'(\d{4})[a-z]?', part) 
            if year_match:
                year = year_match.group(1)
                # Lấy phần tên phía trước
                name_part = part[:year_match.start()].strip().rstrip(',').strip()
                
                # CHẠY BỘ LỌC THÔNG MINH
                if len(name_part) > 1 and is_valid_citation_candidate(name_part, year):
                    citations.append({"name": name_part, "year": year, "full": f"({name_part}, {year})"})

    # --- Pattern mở: Name (Year) ---
    pattern_open = r'([A-ZÀ-ỹ][A-Za-zÀ-ỹ\s&.]{1,50}?)\s*\(\s*(\d{4})\s*\)'
    for match in re.finditer(pattern_open, text):
        name_raw = match.group(1).strip()
        year = match.group(2)
        
        # CHẠY BỘ LỌC THÔNG MINH
        if is_valid_citation_candidate(name_raw, year):
            citations.append({"name": name_raw, "year": year, "full": f"{name_raw} ({year})"})

    # Lọc trùng
    unique_citations = []
    seen = set()
    for c in citations:
        key = f"{c['name']}_{c['year']}"
        if key not in seen:
            unique_citations.append(c)
            seen.add(key)
            
    return unique_citations

# --- 4. HÀM SO KHỚP ---
def check_citation_in_refs(cit_name, cit_year, refs_list):
    # Chuẩn hóa tên: Xóa các từ nối
    stopwords_regex = r'(et al\.?|và nnk\.?|và cộng sự|& cs\.?|&|and|,\s*cs)'
    clean_cit_name = re.sub(stopwords_regex, ' ', cit_name, flags=re.IGNORECASE).strip()
    cit_tokens = [t.lower() for t in clean_cit_name.split() if len(t) > 1]
    
    for ref in refs_list:
        if cit_year in ref:
            ref_lower = ref.lower()
            if clean_cit_name.lower() in ref_lower:
                return True
            match_token_count = 0
            for token in cit_tokens:
                if token in ref_lower:
                    match_token_count += 1
            if len(cit_tokens) > 0 and match_token_count >= 1:
                return True
    return False

# --- 5. GIAO DIỆN ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2921/2921226.png", width=80)
    st.title("Citation Pro v6")
    st.write("🛡️ **Smart Filter:** Tự động loại bỏ ngày tháng, số liệu, phương trình.")
    uploaded_file = st.file_uploader("📂 Tải file báo cáo:", type=['docx', 'pdf'])

st.title("🛡️ Kiểm tra Tài liệu (Bộ lọc thông minh)")

if uploaded_file:
    if st.button("🚀 Bắt đầu Phân tích", type="primary"):
        with st.status("Đang xử lý...", expanded=True) as status:
            time.sleep(0.5)
            
            # Đọc file
            if uploaded_file.name.endswith('.docx'):
                full_text = extract_text_from_docx(uploaded_file)
            else:
                full_text = extract_text_from_pdf(uploaded_file)
            
            if full_text.startswith("ERROR"):
                st.error("Lỗi đọc file.")
                st.stop()

            # Tách References
            matches = list(re.finditer(r"(tài liệu tham khảo|references)", full_text, re.IGNORECASE))
            if not matches:
                st.warning("⚠️ Không tìm thấy mục 'Tài liệu tham khảo'. Đang quét toàn bộ file.")
                ref_text = full_text
                body_text = full_text
            else:
                split_idx = matches[-1].end()
                body_text = full_text[:matches[-1].start()]
                ref_text = full_text[split_idx:]
            
            # Xử lý
            ref_lines = [line.strip() for line in ref_text.split('\n') if len(line.strip()) > 10 and re.search(r'\d{4}', line)]
            citations = find_citations_v6(body_text) # Dùng hàm v6

            # Logic Check
            missing_refs = []
            for cit in citations:
                if not check_citation_in_refs(cit['name'], cit['year'], ref_lines):
                    missing_refs.append(cit['full'])

            unused_refs = []
            for ref in ref_lines:
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
            
            status.update(label="✅ Hoàn tất!", state="complete", expanded=False)

        # Kết quả
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Citation (In-text)", len(citations))
        c2.metric("Reference List", len(ref_lines))
        err_num = len(missing_refs) + len(unused_refs)
        c3.metric("Cảnh báo", err_num, delta_color="inverse")

        st.divider()
        t1, t2, t3 = st.tabs(["🔴 THIẾU REF (Missing)", "🟡 THỪA REF (Unused)", "📋 DANH SÁCH TÌM THẤY"])
        
        with t1:
            if missing_refs:
                for i in missing_refs: st.error(i)
            else:
                st.success("Tuyệt vời! Không thiếu trích dẫn nào.")
        
        with t2:
            if unused_refs:
                for i in unused_refs: st.warning(i)
            else:
                st.success("Danh mục tài liệu khớp hoàn toàn.")
                
        with t3:
            st.info("Kiểm tra lại xem máy có bắt nhầm ngày tháng không:")
            st.write(citations)
