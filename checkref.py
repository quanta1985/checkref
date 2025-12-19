import streamlit as st
import re
from docx import Document
from pypdf import PdfReader

# --- Cấu hình trang ---
st.set_page_config(page_title="Smart Reference Check v3", page_icon="🔍", layout="wide")
st.title("🔍 Kiểm tra Trích dẫn (Hỗ trợ định dạng: Tác giả (Năm))")
st.write("Phiên bản cập nhật: Bắt được cả 'Nguyen (2020)' và '(Nguyen, 2020)'")

# --- 1. HÀM ĐỌC FILE (Giữ nguyên, bổ sung try-except) ---
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

# --- 2. HÀM TÌM KIẾM TRÍCH DẪN (NÂNG CẤP) ---
def find_citations(text):
    citations = []
    
    # Pattern 1: Dạng đóng ngoặc kín -> (Nguyen, 2020) hoặc (Nguyen et al., 2020)
    # Tìm chuỗi trong ngoặc, kết thúc bằng 4 số
    pattern_closed = r'\(([^)]+?),\s*(\d{4})\)'
    for match in re.finditer(pattern_closed, text):
        name_raw = match.group(1)
        year = match.group(2)
        citations.append({"name": name_raw, "year": year, "full": f"({name_raw}, {year})"})

    # Pattern 2: Dạng mở -> Nguyen (2020) hoặc Pham Quy Nhan va nnk (2014)
    # Logic: Tìm một chuỗi Viết Hoa (Tên) đứng trước (Năm), có thể kẹp giữa bởi 'và nnk', 'et al'
    # Regex giải thích:
    # [A-ZÀ-ỹ]: Bắt đầu bằng chữ hoa hoặc tiếng Việt
    # [A-Za-zÀ-ỹ\s]{1,50}?: Theo sau là các ký tự chữ/khoảng trắng, lấy ngắn nhất có thể (tối đa 50 ký tự để tránh bắt nhầm cả câu)
    pattern_open = r'([A-ZÀ-ỹ][A-Za-zÀ-ỹ\s]{1,50}?)\s*(?:và nnk\.?|và cộng sự|et al\.?)?\s*\(\s*(\d{4})\s*\)'
    
    for match in re.finditer(pattern_open, text):
        name_raw = match.group(1).strip()
        year = match.group(2)
        
        # Lọc nhiễu: Tên tác giả thường không quá dài và không chứa từ lạ.
        # Nếu "name_raw" chứa quá nhiều từ thường (không viết hoa), có thể là text thường.
        # Ở đây ta tạm chấp nhận để bắt được nhiều nhất.
        citations.append({"name": name_raw, "year": year, "full": f"{name_raw} ({year})"})

    # Loại bỏ trùng lặp (Convert list of dicts to unique set based on 'full' string)
    unique_citations = []
    seen = set()
    for c in citations:
        if c['full'] not in seen:
            unique_citations.append(c)
            seen.add(c['full'])
            
    return unique_citations

# --- 3. HÀM SO KHỚP (FUZZY MATCHING) ---
def check_citation_in_refs(cit_name, cit_year, refs_list):
    # Chuẩn hóa tên từ trích dẫn: Xóa "et al", "và nnk", ký tự lạ
    clean_name = re.sub(r'(et al\.?|và nnk\.?|và cộng sự|&|and)', '', cit_name, flags=re.IGNORECASE)
    # Tách thành các từ đơn: "Trần Thành Lê" -> ['trần', 'thành', 'lê']
    name_tokens = [t.lower() for t in clean_name.split() if len(t) > 1]
    
    for ref in refs_list:
        if cit_year in ref: # Điều kiện 1: Phải trùng Năm
            ref_lower = ref.lower()
            
            # Điều kiện 2: Kiểm tra tên
            # Nếu là tên tiếng Việt đầy đủ (VD: Trần Thành Lê), kiểm tra xem chuỗi đó có nằm trong ref không
            if clean_name.strip().lower() in ref_lower:
                return True
            
            # Nếu không match cả cụm, kiểm tra từng từ khóa (Dành cho tên nước ngoài: Parlov -> Parlov J.)
            # Logic: Nếu tìm thấy bất kỳ token quan trọng nào (như Họ) trong Ref
            match_token_count = 0
            for token in name_tokens:
                if token in ref_lower:
                    match_token_count += 1
            
            # Nếu tìm thấy ít nhất 1 từ trùng khớp (với tên ngắn) hoặc 2 từ (với tên dài)
            if match_token_count >= 1: 
                return True
                
    return False

# --- 4. GIAO DIỆN CHÍNH ---
col1, col2 = st.columns([1, 2])
with col1:
    uploaded_file = st.file_uploader("Tải file báo cáo (.docx, .pdf)", type=['docx', 'pdf'])
    if uploaded_file and st.button("Kiểm tra"):
        st.session_state.processing = True

if uploaded_file and st.session_state.get('processing'):
    # Đọc file
    if uploaded_file.name.endswith('.docx'):
        full_text = extract_text_from_docx(uploaded_file)
    else:
        full_text = extract_text_from_pdf(uploaded_file)

    if full_text.startswith("ERROR"):
        st.error("Lỗi đọc file. Vui lòng kiểm tra định dạng.")
    else:
        # Tách Reference và Body
        # Cải tiến: Tìm từ khóa Reference cuối cùng để tránh nhầm với Mục lục
        matches = list(re.finditer(r"(tài liệu tham khảo|references)", full_text, re.IGNORECASE))
        
        if not matches:
            st.warning("⚠️ Không tìm thấy mục 'Tài liệu tham khảo'. Đang quét toàn bộ file...")
            body_text = full_text
            ref_text = full_text # Quét cả bài nếu không thấy mục riêng
        else:
            split_idx = matches[-1].end()
            body_text = full_text[:matches[-1].start()]
            ref_text = full_text[split_idx:]

        # Xử lý Reference List
        ref_lines = [line.strip() for line in ref_text.split('\n') if len(line.strip()) > 10 and re.search(r'\d{4}', line)]
        
        # Xử lý Citations (Dùng hàm mới)
        citations = find_citations(body_text)

        # --- LOGIC CHECK ---
        missing_refs = [] # Có cite nhưng không có ref
        
        for cit in citations:
            is_valid = check_citation_in_refs(cit['name'], cit['year'], ref_lines)
            if not is_valid:
                missing_refs.append(cit['full'])

        unused_refs = [] # Có ref nhưng không được cite
        for ref in ref_lines:
            is_used = False
            # Check ngược lại: Xem ref này có từ khóa nào xuất hiện trong danh sách cite không
            # Cách này tương đối phức tạp, ta dùng heuristic đơn giản: Check năm
            ref_year_match = re.search(r'\d{4}', ref)
            if ref_year_match:
                r_year = ref_year_match.group(0)
                # Lấy danh sách cite có cùng năm này
                same_year_cites = [c for c in citations if c['year'] == r_year]
                
                if not same_year_cites:
                    unused_refs.append(ref) # Không có cite nào dùng năm này -> Chắc chắn thừa
                else:
                    # Có cite cùng năm -> Kiểm tra tên
                    # Nếu tên trong Ref xuất hiện trong tên của Cite (hoặc ngược lại)
                    match_found = False
                    for c in same_year_cites:
                        # Clean tên cite
                        c_name_clean = re.sub(r'(et al|và nnk|&).*', '', c['name'], flags=re.IGNORECASE).strip()
                        # Tách tên Ref (thường là đoạn đầu trước năm)
                        ref_start = ref.split(r_year)[0].lower()
                        
                        # So sánh fuzzy
                        tokens = c_name_clean.lower().split()
                        for t in tokens:
                            if len(t) > 2 and t in ref_start:
                                match_found = True
                                break
                        if match_found: break
                    
                    if not match_found:
                        unused_refs.append(ref)

        # --- HIỂN THỊ ---
        st.divider()
        m1, m2 = st.columns(2)
        m1.metric("Số trích dẫn tìm thấy", len(citations))
        m2.metric("Số tài liệu tham khảo", len(ref_lines))
        st.divider()

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("❌ Trích dẫn thiếu trong danh mục")
            if missing_refs:
                for item in missing_refs:
                    st.error(item)
            else:
                st.success("Tất cả trích dẫn đều có nguồn!")

        with c2:
            st.subheader("⚠️ Tài liệu thừa (Có thể chưa cite)")
            if unused_refs:
                for item in unused_refs:
                    st.warning(item)
                    st.caption("---")
            else:
                st.success("Danh mục tài liệu gọn gàng!")
