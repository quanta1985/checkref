import streamlit as st
import re
from docx import Document
from pypdf import PdfReader

# --- Cấu hình trang ---
st.set_page_config(page_title="Smart Reference Check", page_icon="🔍", layout="wide")

st.title("🔍 Kiểm tra Trích dẫn EMNR 2026 - by Quân DST&CNMT")
st.write("Check nhanh tài liệu")

# --- Hàm xử lý đọc file ---
def extract_text_from_docx(file):
    doc = Document(file)
    return "\n".join([para.text for para in doc.paragraphs])

def extract_text_from_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

# --- HÀM SO KHỚP THÔNG MINH (TRÁI TIM CỦA APP) ---
def is_citation_in_ref(citation_raw, ref_line):
    """
    citation_raw: "(Mir & Dhawan, 2021)"
    ref_line: "Mir S., and Dhawan N., (2021). Characterization..."
    """
    # 1. KIỂM TRA NĂM (Bắt buộc phải trùng năm trước)
    try:
        cit_year = re.search(r'\d{4}', citation_raw).group(0)
    except:
        return False # Không tìm thấy năm trong cite
        
    if cit_year not in ref_line:
        return False # Năm không khớp -> Chắc chắn sai

    # 2. XỬ LÝ TÊN TÁC GIẢ TRONG CITE
    # Lấy phần tên trước dấu phẩy năm: "(Mir & Dhawan, 2021)" -> "Mir & Dhawan"
    author_part = citation_raw.split(',')[0].replace('(', '')
    
    # Loại bỏ các từ nối vô nghĩa để lấy tên gốc
    # Xóa: et al, và cộng sự, &, and, dấu chấm
    clean_author = re.sub(r'(et al\.?|và cộng sự|&|and)', ' ', author_part, flags=re.IGNORECASE)
    
    # Tách thành danh sách tên: "Mir Dhawan" -> ['mir', 'dhawan']
    cit_names = [n.strip().lower() for n in clean_author.split() if len(n.strip()) > 1]

    # 3. SO SÁNH VỚI DÒNG REF
    ref_lower = ref_line.lower()
    
    # Logic: Nếu tìm thấy ít nhất 1 cái tên từ Cite xuất hiện trong Ref -> HỢP LỆ
    # VD: "Huy" có trong "pham khanh huy" -> True
    # VD: "Torre" có trong "de la torre" -> True
    # VD: "David" có trong "david j. fisher" -> True
    for name in cit_names:
        if name in ref_lower:
            return True
            
    return False

# --- Hàm phân tích chính ---
def analyze_citations(text):
    # 1. Tách văn bản
    keywords_pattern = r"(tài liệu tham khảo|tài liệu tham khảp|references)"
    matches = list(re.finditer(keywords_pattern, text, re.IGNORECASE))
    
    if not matches:
        return None, None, "❌ Không tìm thấy mục 'Tài liệu tham khảo' hoặc 'References'."

    last_match = matches[-1]
    split_index = last_match.end()
    
    body_text = text[:last_match.start()]
    ref_text = text[split_index:]

    # 2. Tìm trích dẫn (In-text)
    # Pattern mở rộng để bắt cả tiếng Việt có dấu: (Tên..., Năm)
    citation_pattern = r'\(([A-Za-zÀ-ỹ\s&.,]+),\s*(\d{4})\)'
    citations_found = re.findall(citation_pattern, body_text)
    
    # List các trích dẫn unique
    citation_list = sorted(list(set([f"({c[0].strip()}, {c[1]})" for c in citations_found])))

    # 3. Tìm danh mục tham khảo (Ref list)
    ref_lines = ref_text.split('\n')
    ref_list_extracted = []
    
    for line in ref_lines:
        line = line.strip()
        # Dòng > 15 ký tự và có chứa Năm được coi là 1 Ref
        if len(line) > 15 and re.search(r'\d{4}', line):
            ref_list_extracted.append(line)

    return citation_list, ref_list_extracted, None

# --- Giao diện ---
col1, col2 = st.columns([1, 3])

with col1:
    st.info("Bấm Browse files để tải báo cáo lên 👇")
    uploaded_file = st.file_uploader("", type=['docx', 'pdf'])
    if uploaded_file and st.button("🚀 Kiểm tra ngay"):
        st.session_state.processing = True

if uploaded_file and st.session_state.get('processing'):
    with st.spinner("Đang phân tích kỹ lưỡng..."):
        if uploaded_file.name.endswith('.docx'):
            full_text = extract_text_from_docx(uploaded_file)
        else:
            full_text = extract_text_from_pdf(uploaded_file)
        
        citations, refs, error = analyze_citations(full_text)
        
        if error:
            st.error(error)
        else:
            # --- LOGIC KIỂM TRA MỚI ---
            
            # 1. Tìm Cite bị thiếu trong Ref
            missing_refs = []
            for cit in citations:
                is_found = False
                for r in refs:
                    if is_citation_in_ref(cit, r):
                        is_found = True
                        break
                if not is_found:
                    missing_refs.append(cit)

            # 2. Tìm Ref thừa (không được Cite)
            unused_refs = []
            for r in refs:
                is_cited = False
                for cit in citations:
                    if is_citation_in_ref(cit, r):
                        is_cited = True
                        break
                if not is_cited:
                    unused_refs.append(r)

            # --- HIỂN THỊ KẾT QUẢ ---
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("Tổng trích dẫn (In-text)", len(citations))
            m2.metric("Tổng tài liệu (Ref List)", len(refs))
            
            # Tính điểm "Sạch"
            total_issues = len(missing_refs) + len(unused_refs)
            if total_issues == 0:
                m3.success("✅ Perfect!")
            else:
                m3.warning(f"⚠️ Phát hiện {total_issues} vấn đề")

            st.divider()
            
            c1, c2 = st.columns(2)
            
            with c1:
                st.subheader(f"❌ Cite thiếu Ref ({len(missing_refs)})")
                if missing_refs:
                    for item in missing_refs:
                        st.error(item)
                else:
                    st.success("Không có trích dẫn nào bị thiếu.")

            with c2:
                st.subheader(f"⚠️ Ref thừa ({len(unused_refs)})")
                if unused_refs:
                    for item in unused_refs:
                        st.warning(item)
                        st.caption("---")
                else:
                    st.success("Không có tài liệu thừa.")