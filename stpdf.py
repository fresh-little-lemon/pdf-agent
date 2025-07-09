import streamlit as st
import base64

# 显示PDF文件的函数
def st_display_pdf(pdf_file):
    with open(pdf_file, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="800" height="1000" type="application/pdf">'
    st.markdown(pdf_display, unsafe_allow_html=True)

def main():
    st.title("在Streamlit中嵌入PDF文件")
    st.subheader("Learn Streamlit")

    st_display_pdf(r"E:\浙江大学软件学院\pdf-agent-qwenvl\tmp\1396_FinRGAgents_A_Multi_Agent.pdf")

if __name__ == '__main__':
    main()
