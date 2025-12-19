import streamlit as st
import re
import time
from docx import Document
from pypdf import PdfReader

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(
    page_title="Citation Pro Checker v5",
    page_icon="✅",
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

# --- 2. HÀM TÌM TRÍCH DẪN (NÂNG CẤP XỬ LÝ DẤU CHẤM PHẨY) ---
def find_citations_v5(text):
    citations = []
    
    # --- A. Xử lý dạng trong ngoặc: (Name, Year; Name, Year) ---
    # Bước 1: Tìm tất cả các cụm trong ngoặc đơn có chứa ít nhất 1 năm (4 số)
    # Regex này bắt nội dung trong ngoặc (...)
    parenthetical_pattern = r'\(([^)]*?\d{4}[^)]*?)\)'
    
    for match in re.finditer(parenthetical_pattern, text):
        content = match.group(1)
        
        # Bước 2: Tách theo dấu chấm phẩy (cho trường hợp trích dẫn gộp)
        # VD: "Lee & Pradhan, 2007; Crawford et al., 2021" -> Tách làm 2
        parts = content.split(';')
        
        for part in parts:
            part = part.strip()
            # Bước 3: Trong mỗi phần nhỏ, tìm cặp Name - Year
            # Tìm 4 số cuối cùng làm Năm
            year_match = re.search(r'(\d{4})[a-z]?', part) 
            if year_match:
                year = year_match.group(1)
                # Tên là phần đứng trước năm (bỏ dấu phẩy thừa)
                # VD: "Lee & Pradhan, 2007" -> Name: "Lee & Pradhan"
                name_part = part[:year_match.start()].strip().rstrip(',').strip()
                
                if len(name_part) > 1: # Tránh rác
                    citations.append({"name": name_part, "year": year, "full": f"({name_part}, {year})"})

    # --- B. Xử lý dạng mở: Name (Year) ---
    # VD: Parlov và nnk (2019)
    pattern_open = r'([A-ZÀ-ỹ][A-Za-zÀ-ỹ\s&.]{1,50}?)\s*\(\s*(\d{4})\s*\)'
    for match in re.finditer(pattern_open, text):
        name_raw = match.group(1).strip()
        year = match.group(2)
        # Loại bỏ các từ nối cuối cùng nếu dính (VD: "ABC et al" -> "ABC")
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

# --- 3. HÀM SO KHỚP (NÂNG CẤP TỪ ĐIỂN VN) ---
def check_citation_in_refs(cit_name, cit_year, refs_list):
    # Chuẩn hóa tên: Xóa tất cả các từ nối nhiễu
    # Thêm "& cs" (cộng sự), "cs", "và nnk"
    stopwords_regex = r'(et al\.?|và nnk\.?|và cộng sự|& cs\.?|&|and|,\s*cs)'
    
    clean_cit_name = re.sub(stopwords_regex, ' ', cit_name, flags=re.IGNORECASE).strip()
    
    # Tách tên thành các từ khóa (tokens)
    # VD: "Trần Văn Tớ" -> ['trần', 'văn', 'tớ']
    cit_tokens = [t.lower() for t in clean_cit_name.split() if len(t) > 1]
    
    for ref in refs_list:
        # Điều kiện 1: Phải chứa Năm
        if cit_year in ref:
            ref_lower = ref.lower()
            
            # Điều kiện 2: Kiểm tra tên (Fuzzy Matching)
            
            # Case A: Tên Cite nằm trọn trong Ref (Dành cho tên tiếng Việt đầy đủ)
            if clean_cit_name.lower() in ref_lower:
                return True
                
            # Case B: So khớp từng từ (Dành cho tên nước ngoài hoặc tên viết tắt)
            # VD: Cite="Hà", Ref="Hà, T. T." -> Khớp token "hà"
            match_token_count = 0
            for token in cit_tokens:
                # Token phải xuất hiện TRƯỚC phần năm trong Ref (để tránh trùng với tên bài báo)
                # Tuy nhiên để đơn giản và hiệu quả, ta check trong cả string Ref trước
                if token in ref_lower:
                    match_token_count += 1
            
            # Nếu tên ngắn (1 từ) -> Phải khớp 1 từ
            # Nếu tên dài (>1 từ) -> Phải khớp ít nhất 1 từ (chấp nhận viết tắt)
            if len(cit_tokens) > 0 and match_token_count >= 1:
                return True
                
    return False

# --- 4. GIAO DIỆN ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2921/2921226.png", width=80)
    st.title("Citation Pro v5")
    st.write("Phiên bản sửa lỗi trích dẫn gộp (;)")
    uploaded_file = st.file_uploader("📂 Tải file báo cáo:", type=['docx', 'pdf'])

st.title("📑 Kiểm tra Tài liệu (Fix dấu ; và & cs)")

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
            
            # Xử lý dữ liệu
            ref_lines = [line.strip() for line in ref_text.split('\n') if len(line.strip()) > 10 and re.search(r'\d{4}', line)]
            citations = find_citations_v5(body_text) # Dùng hàm v5 mới

            # Logic Check
            missing_refs = []
            for cit in citations:
                if not check_citation_in_refs(cit['name'], cit['year'], ref_lines):
                    missing_refs.append(cit['full'])

            unused_refs = []
            for ref in ref_lines:
                # Lấy năm của Ref
                ref_year_match = re.search(r'\d{4}', ref)
                if ref_year_match:
                    r_year = ref_year_match.group(0)
                    
                    # Tìm xem có Cite nào cùng năm không
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
        c3.metric("Số lượng cảnh báo", err_num, delta_color="inverse")

        st.divider()
        t1, t2 = st.tabs(["🔴 THIẾU REF (Missing)", "🟡 THỪA REF (Unused)"])
        
        with t1:
            if missing_refs:
                for i in missing_refs: st.error(i)
            else:
                st.success("Không có trích dẫn nào bị thiếu!")
        
        with t2:
            if unused_refs:
                for i in unused_refs: st.warning(i)
            else:
                st.success("Danh mục tài liệu hoàn toàn khớp!")
