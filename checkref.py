import streamlit as st
import re
import time
from docx import Document
from pypdf import PdfReader

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(
    page_title="Citation Pro Checker",
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS TÙY CHỈNH (Làm đẹp) ---
st.markdown("""
<style>
    .big-font { font-size:20px !important; font-weight: bold; }
    .success-box { padding:15px; border-radius:10px; background-color:#d4edda; color:#155724; border: 1px solid #c3e6cb; }
    .error-box { padding:15px; border-radius:10px; background-color:#f8d7da; color:#721c24; border: 1px solid #f5c6cb; }
    .warning-box { padding:15px; border-radius:10px; background-color:#fff3cd; color:#856404; border: 1px solid #ffeeba; }
</style>
""", unsafe_allow_html=True)

# --- 1. CORE LOGIC (GIỮ NGUYÊN TỪ BẢN TRƯỚC) ---
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

def find_citations_v3(text):
    citations = []
    # Pattern 1: (Name, Year)
    pattern_closed = r'\(([^)]+?),\s*(\d{4})\)'
    for match in re.finditer(pattern_closed, text):
        name_raw = match.group(1)
        year = match.group(2)
        citations.append({"name": name_raw, "year": year, "full": f"({name_raw}, {year})"})

    # Pattern 2: Name (Year)
    pattern_open = r'([A-ZÀ-ỹ][A-Za-zÀ-ỹ\s]{1,50}?)\s*(?:và nnk\.?|và cộng sự|et al\.?)?\s*\(\s*(\d{4})\s*\)'
    for match in re.finditer(pattern_open, text):
        name_raw = match.group(1).strip()
        year = match.group(2)
        citations.append({"name": name_raw, "year": year, "full": f"{name_raw} ({year})"})

    # Unique
    unique_citations = []
    seen = set()
    for c in citations:
        if c['full'] not in seen:
            unique_citations.append(c)
            seen.add(c['full'])
    return unique_citations

def check_citation_in_refs(cit_name, cit_year, refs_list):
    clean_name = re.sub(r'(et al\.?|và nnk\.?|và cộng sự|&|and)', '', cit_name, flags=re.IGNORECASE)
    name_tokens = [t.lower() for t in clean_name.split() if len(t) > 1]
    
    for ref in refs_list:
        if cit_year in ref:
            ref_lower = ref.lower()
            if clean_name.strip().lower() in ref_lower:
                return True
            match_token_count = 0
            for token in name_tokens:
                if token in ref_lower:
                    match_token_count += 1
            if match_token_count >= 1: 
                return True
    return False

# --- 2. GIAO DIỆN NGƯỜI DÙNG (UI) ---

# Sidebar: Upload và thông tin
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2921/2921226.png", width=80)
    st.title("Công cụ Rà soát")
    st.write("Dành cho báo cáo khoa học, luận văn.")
    st.markdown("---")
    
    uploaded_file = st.file_uploader("📂 Tải file báo cáo lên đây:", type=['docx', 'pdf'])
    
    st.info("💡 **Tips:** Hỗ trợ tốt nhất cho file `.docx` và chuẩn trích dẫn dạng `Tên (Năm)` hoặc `(Tên, Năm)`.")

# Main content
st.title("📑 Kiểm tra Trích dẫn & Tài liệu tham khảo")
st.caption("Phiên bản v4.0 | Hỗ trợ phát hiện lỗi thiếu/thừa danh mục tự động")
st.caption("Phần mềm vẫn đang trong quát trình hoàn thiện nên vẫn còn nhiều sai sót, chỉ dùng để kiểm tra nhanh")


if uploaded_file:
    # Nút bấm kích hoạt
    if st.button("🚀 Bắt đầu Phân tích", type="primary"):
        
        # Hiệu ứng Loading chuyên nghiệp
        with st.status("Đang xử lý dữ liệu...", expanded=True) as status:
            st.write("📄 Đang đọc nội dung file...")
            time.sleep(0.5) # Giả lập độ trễ để người dùng kịp đọc
            
            # 1. Đọc file
            if uploaded_file.name.endswith('.docx'):
                full_text = extract_text_from_docx(uploaded_file)
            else:
                full_text = extract_text_from_pdf(uploaded_file)
            
            if full_text.startswith("ERROR"):
                status.update(label="❌ Lỗi định dạng file!", state="error")
                st.stop()

            st.write("🔍 Đang quét danh mục tham khảo...")
            # 2. Tách text
            matches = list(re.finditer(r"(tài liệu tham khảo|references)", full_text, re.IGNORECASE))
            if not matches:
                body_text = full_text
                ref_text = full_text
                st.warning("⚠️ Không tìm thấy mục 'Tài liệu tham khảo' riêng biệt.")
            else:
                split_idx = matches[-1].end()
                body_text = full_text[:matches[-1].start()]
                ref_text = full_text[split_idx:]
            
            # 3. Phân tích
            ref_lines = [line.strip() for line in ref_text.split('\n') if len(line.strip()) > 10 and re.search(r'\d{4}', line)]
            citations = find_citations_v3(body_text)

            # 4. Logic Check
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
                    if not same_year_cites:
                        unused_refs.append(ref)
                    else:
                        match_found = False
                        for c in same_year_cites:
                            c_name_clean = re.sub(r'(et al|và nnk|&).*', '', c['name'], flags=re.IGNORECASE).strip()
                            ref_start = ref.split(r_year)[0].lower()
                            tokens = c_name_clean.lower().split()
                            for t in tokens:
                                if len(t) > 2 and t in ref_start:
                                    match_found = True
                                    break
                            if match_found: break
                        if not match_found:
                            unused_refs.append(ref)
            
            status.update(label="✅ Đã phân tích xong!", state="complete", expanded=False)

        # --- KẾT QUẢ HIỂN THỊ (DASHBOARD) ---
        
        st.divider()
        
        # 1. Overview Metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Tổng Trích dẫn (In-text)", len(citations), border=True)
        col2.metric("Tổng Tài liệu (References)", len(ref_lines), border=True)
        
        error_count = len(missing_refs) + len(unused_refs)
        if error_count == 0:
            col3.metric("Trạng thái", "Hoàn hảo", "✅ OK", border=True)
        else:
            col3.metric("Trạng thái", f"Cần sửa {error_count} lỗi", "-Issues", delta_color="inverse", border=True)

        st.divider()

        # 2. Chi tiết bằng Tabs
        tab1, tab2, tab3 = st.tabs(["🚫 TRÍCH DẪN THIẾU (Missing)", "⚠️ DANH MỤC THỪA (Unused)", "📋 DỮ LIỆU GỐC"])

        with tab1:
            if missing_refs:
                st.markdown(f"""<div class="error-box"><b>Phát hiện {len(missing_refs)} trích dẫn có trong bài nhưng KHÔNG CÓ trong danh mục:</b></div>""", unsafe_allow_html=True)
                st.write("")
                for item in missing_refs:
                    st.error(f"❌ {item}")
            else:
                st.markdown("""<div class="success-box">✅ Tuyệt vời! Tất cả trích dẫn trong bài đều đã có nguồn.</div>""", unsafe_allow_html=True)

        with tab2:
            if unused_refs:
                st.markdown(f"""<div class="warning-box"><b>Phát hiện {len(unused_refs)} tài liệu có trong danh mục nhưng CHƯA ĐƯỢC trích dẫn trong bài:</b></div>""", unsafe_allow_html=True)
                st.write("")
                # Dùng expander cho gọn nếu danh sách dài
                with st.expander("Xem chi tiết danh sách thừa"):
                    for item in unused_refs:
                        st.warning(f"⚠️ {item}")
            else:
                st.markdown("""<div class="success-box">✅ Danh mục tài liệu rất gọn gàng, không có tài liệu thừa.</div>""", unsafe_allow_html=True)

        with tab3:
            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("Danh sách Trích dẫn đã tìm thấy")
                st.dataframe([c['full'] for c in citations], use_container_width=True, hide_index=True, column_config={0: "Citation"})
            with col_b:
                st.subheader("Danh sách Tài liệu đã tìm thấy")
                st.dataframe(ref_lines, use_container_width=True, hide_index=True, column_config={0: "Reference Line"})

else:
    # Màn hình chờ khi chưa upload
    st.write("👈 *Vui lòng tải file báo cáo ở cột bên trái để bắt đầu.*")
    st.markdown("""
    ### Ứng dụng này giúp bạn:
    * Kiểm tra sự đồng nhất giữa **(Tác giả, Năm)** trong bài và danh mục cuối bài.
    * Hỗ trợ tốt tên tác giả tiếng Việt (VD: *Trần Thành Lê*).
    * Bỏ qua các từ nối như *và nnk*, *et al*, *and*...
    """)
