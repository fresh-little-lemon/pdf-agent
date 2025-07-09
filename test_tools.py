import streamlit as st
import os
from PIL import Image
import zipfile
import io
from utils.pdf_converter import pdf_to_jpg, get_pdf_info, clean_tmp_folder
from utils.image_extractor import extract_images_from_pdf, get_pdf_image_info, clean_extracted_images, convert_images_to_jpg
from utils.html_parser import parse_images_to_html, get_api_status, batch_parse_images_to_html, parse_all_images_to_html, parse_and_insert_images
from utils.html_to_markdown import convert_html_files_to_markdown, validate_html_directory, get_markdown_preview, clean_markdown_files
from utils.pdf_bbox_extractor import extract_pdf_bboxes
from utils.layout_analyzer import analyze_and_slice_pdf


def main():
    st.set_page_config(
        page_title="PDF处理工具",
        page_icon="📄",
        layout="wide"
    )
    
    st.title("📄 PDF处理工具")
    st.markdown("---")
    
    # 功能选择
    st.subheader("🔧 选择功能")
    function_choice = st.radio(
        "请选择要使用的功能：",
        ["📄➡️🖼️ PDF页面转JPG", "🖼️📤 提取PDF中的图片", "📄➡️📝 PDF解析为HTML", "📝➡️📋 HTML转Markdown", "📦🔍 PDF边框提取", "📐✂️ 布局分析与切片"],
        horizontal=True
    )
    
    # 侧边栏设置
    with st.sidebar:
        if function_choice == "📄➡️🖼️ PDF页面转JPG":
            st.header("⚙️ 页面转换设置")
            
            # DPI设置
            dpi = st.slider(
                "图片质量 (DPI)",
                min_value=72,
                max_value=300,
                value=150,
                step=24,
                help="数值越高，图片质量越好，但文件也会越大"
            )
            
            # 自动清理设置
            auto_clean = st.checkbox("自动清理旧文件", value=True, help="保留最新的转换结果，自动删除旧文件")
            
            st.markdown("---")
            st.markdown("### 📖 页面转换说明")
            st.markdown("""
            1. 上传PDF文件
            2. 调整图片质量设置
            3. 点击转换按钮
            4. 下载转换后的图片
            """)
        elif function_choice == "🖼️📤 提取PDF中的图片":
            st.header("⚙️ 图片提取设置")
            
            # 转换为JPG设置
            convert_to_jpg = st.checkbox("统一转换为JPG格式", value=True, help="将提取的所有图片统一转换为JPG格式")
            
            # 自动清理设置
            auto_clean_extract = st.checkbox("自动清理旧图片", value=True, help="清理之前提取的图片")
            
            st.markdown("---")
            st.markdown("### 📖 图片提取说明")
            st.markdown("""
            1. 上传PDF文件
            2. 查看图片信息
            3. 点击提取按钮
            4. 下载提取的图片
            """)
        elif function_choice == "📄➡️📝 PDF解析为HTML":
            st.header("⚙️ HTML解析设置")
            
            # DPI设置
            dpi = st.slider(
                "图片质量 (DPI)",
                min_value=72,
                max_value=300,
                value=150,
                step=24,
                help="数值越高，图片质量越好，解析效果更佳"
            )
            
            # 处理方式选择
            st.subheader("🔧 处理方式")
            processing_mode = st.radio(
                "选择处理方式：",
                ["🔄 串行处理", "⚡ 并行处理"],
                help="串行处理：逐页处理，稳定可靠\n并行处理：多线程同时处理，速度更快"
            )
            
            # 如果选择并行处理，显示线程数设置
            if processing_mode == "⚡ 并行处理":
                max_workers = st.slider(
                    "并行线程数",
                    min_value=1,
                    max_value=24,
                    value=3,
                    help="同时处理的线程数，建议2-6个。数值过高可能触发API限制"
                )
            else:
                max_workers = 1
            
            # HTML清理功能设置
            st.subheader("🧹 HTML清理设置")
            enable_clean = st.checkbox(
                "启用HTML清理功能",
                value=False,
                help="清理HTML中的颜色样式、边界框、多边形等信息，使输出更简洁"
            )
            
            # 图片插入功能设置
            st.subheader("🖼️ 图片插入设置")
            insert_images = st.checkbox(
                "插入提取的图片到HTML中",
                value=False,
                help="自动提取PDF中的图片并插入到HTML的img元素中，使用绝对路径"
            )
            
            # 重试设置
            st.subheader("🔄 重试设置")
            max_retries = st.slider(
                "最大重试次数",
                min_value=1,
                max_value=10,
                value=3,
                help="API调用失败时的最大重试次数，建议3-5次"
            )
            
            retry_delay = st.slider(
                "重试间隔（秒）",
                min_value=0.5,
                max_value=10.0,
                value=1.0,
                step=0.5,
                help="重试之间的等待时间，每次重试会自动增加"
            )
            
            # API状态检查
            api_status = get_api_status()
            if api_status["api_key_configured"]:
                st.success("✅ API密钥已配置")
            else:
                st.error("❌ 请设置 MODELSCOPE_SDK_TOKEN 环境变量")
            
            st.markdown("---")
            st.markdown("### 📖 HTML解析说明")
            st.markdown("""
            1. 上传PDF文件
            2. 转换为高质量图片
            3. 使用Qwen2.5-VL解析
            4. 生成QwenVL HTML格式
            5. 下载解析结果
            
            **处理方式说明：**
            - 🔄 串行处理：逐页解析，稳定可靠，适合小文档
            - ⚡ 并行处理：多线程同时解析，速度更快，适合大文档
            
            **HTML清理说明：**
            - 🧹 启用清理：移除颜色样式、边界框等信息，输出简洁HTML
            - 📄 原始输出：保留模型的完整输出，包含所有标记信息
            
            **图片插入说明：**
            - 🖼️ 启用插入：自动提取PDF中的图片并插入到HTML的img元素src属性中
            - 📂 使用绝对路径：插入的图片使用绝对路径，便于在任何位置打开HTML
            
            **重试设置说明：**
            - 🔄 自动重试：API调用失败时自动重试，提升成功率
            - ⏱️ 智能延迟：每次重试自动增加等待时间，避免频繁请求
            - 📊 实时反馈：显示重试进度和失败原因
            """)
        elif function_choice == "📝➡️📋 HTML转Markdown":
            st.header("⚙️ Markdown转换设置")
            
            # HTML目录路径输入
            st.subheader("📁 HTML文件目录")
            html_dir_input = st.text_input(
                "HTML文件目录路径",
                value="tmp/v9_html",
                help="输入包含HTML文件的目录路径，如：tmp/v9_html"
            )
            
            # PDF文件名输入
            pdf_filename_input = st.text_input(
                "PDF文件名（不含扩展名）",
                value="v9",
                help="输入PDF文件名，用于生成输出文件夹名称"
            )
            
            # 验证目录
            if html_dir_input:
                validation = validate_html_directory(html_dir_input)
                if validation['valid']:
                    st.success(f"✅ {validation['message']}")
                    st.info(f"📂 找到HTML文件: {', '.join(validation['html_files'])}")
                else:
                    st.error(f"❌ {validation['message']}")
            
            # 自动清理设置
            auto_clean_markdown = st.checkbox(
                "自动清理旧的Markdown文件",
                value=True,
                help="转换前自动清理同名的Markdown文件夹"
            )
            
            st.markdown("---")
            st.markdown("### 📖 Markdown转换说明")
            st.markdown("""
            1. 指定HTML文件目录路径
            2. 输入PDF文件名
            3. 点击转换按钮
            4. 生成单页和合并的Markdown文件
            5. 下载转换结果
            
            **转换功能特点：**
            - 📄 将HTML转换为Markdown格式
            - 🏷️ 保留页码、bbox、块类型等元信息作为注释
            - 🔧 支持文字、图片、表格、公式等内容
            - 📊 生成单页文件和完整合并文件
            - 📈 提供详细的转换统计信息
            - 💾 导出元数据JSON文件
            - ✨ 同时生成完整版和干净版文件
            
            **输出文件结构：**
            - `page_N.md`: 单页Markdown文件（完整版，含注释）
            - `page_N_clean.md`: 单页Markdown文件（干净版，纯文档）
            - `{pdf_filename}_complete.md`: 完整合并文件（含注释）
            - `{pdf_filename}_clean.md`: 干净合并文件（纯文档）
            - `{pdf_filename}_metadata.json`: 元数据文件
            
            **版本说明：**
            - 🔍 **完整版**：包含所有注释、bbox信息、页码标记等元数据
            - 🎯 **干净版**：删除所有注释和元数据，仅保留纯文档内容
            """)
        elif function_choice == "📦🔍 PDF边框提取":
            st.header("⚙️ PDF边框提取设置")
            
            # 基本设置
            st.subheader("📁 输入设置")
            
            bbox_pdf_file_source = st.radio(
                "PDF文件来源",
                ["上传文件", "指定路径"],
                help="选择PDF文件的来源方式",
                key="bbox_pdf_source"
            )
            
            if bbox_pdf_file_source == "指定路径":
                bbox_pdf_path = st.text_input(
                    "PDF文件路径",
                    help="输入PDF文件的完整路径",
                    placeholder="例如：tmp/diffcl-v34_bbox.pdf"
                )
            else:
                bbox_pdf_path = None
            
            # 输出设置
            st.subheader("📤 输出设置")
            
            bbox_output_dir = st.text_input(
                "输出目录",
                value="tmp",
                help="边框提取结果的保存目录"
            )
            
            # 提取选项
            st.subheader("🔍 提取选项")
            
            extract_text = st.checkbox(
                "提取文本块边框",
                value=True,
                help="使用PyMuPDF提取文本块边框（绿色）"
            )
            
            extract_images = st.checkbox(
                "提取图像边框",
                value=True,
                help="使用PyMuPDF提取图像边框（红色）"
            )
            
            extract_tables = st.checkbox(
                "提取表格边框",
                value=True,
                help="使用Qwen2.5-VL AI检测表格边框（蓝色）"
            )
            
            # 额外标注选项
            st.subheader("🎨 额外标注选项")
            
            show_original_lines = st.checkbox(
                "显示PDF原始框线",
                value=False,
                help="标注PDF中所有原始的线条和矩形（橙色）"
            )
            
            show_original_qwen_tables = st.checkbox(
                "显示原始Qwen表格框线",
                value=False,
                help="显示Qwen检测的原始表格框线（修正前，紫色）"
            )
            
            # 显示设置
            st.subheader("🎨 显示设置")
            
            bbox_line_width = st.slider(
                "边框线条宽度",
                min_value=0.5,
                max_value=3.0,
                value=1.0,
                step=0.1,
                help="设置绘制边框的线条宽度"
            )
            
            show_labels = st.checkbox(
                "显示元素标签",
                value=True,
                help="在边框附近显示元素类型标签"
            )
            
            # 颜色说明
            st.subheader("🌈 颜色说明")
            
            st.info(
                "🎨 **边框颜色含义**\n"
                "- 🟢 **绿色**: 文本块（PyMuPDF）\n"
                "- 🔴 **红色**: 图像（PyMuPDF）\n"
                "- 🔵 **蓝色**: 表格（Qwen2.5-VL AI检测，修正后）\n"
                "- 🟠 **橙色**: PDF原始框线（可选）\n"
                "- 🟣 **紫色**: Qwen原始表格框线（可选，修正前）"
            )
            
            st.markdown("---")
            st.markdown("### 📖 边框提取说明")
            st.markdown("""
            1. 选择PDF文件（上传或指定路径）
            2. 配置提取选项和显示设置
            3. 点击提取按钮
            4. 查看带边框的PDF结果
            5. 下载处理后的文件
            
                         **提取功能特点：**
             - 📄 使用PyMuPDF提取文本块和图像边框
             - 🤖 使用Qwen2.5-VL AI智能检测表格边框
             - 🎨 不同类型元素使用不同颜色标识
             - 🏷️ 可选显示元素类型标签和统计信息
             - 📐 可调节边框线条宽度
             - 💾 自动保存为{原文件名}_bbox.pdf格式
            
            **输出文件：**
            - 在指定目录生成{原文件名}_bbox.pdf文件
            - 包含所有选定类型的元素边框
            - 保留原PDF的所有内容和格式
            
                         **应用场景：**
             - 📋 文档布局分析和验证
             - 🔍 OCR和解析结果验证
             - 🖼️ 图像提取位置确认
             - 📊 AI表格检测效果评估
            """)
        elif function_choice == "📐✂️ 布局分析与切片":
            st.header("⚙️ 布局分析与切片设置")
            
            # 文件输入设置
            st.subheader("📁 文件输入")
            
            # PDF文件选择
            slice_pdf_source = st.radio(
                "PDF文件来源",
                ["上传文件", "指定路径"],
                help="选择PDF文件的来源方式",
                key="slice_pdf_source"
            )
            
            if slice_pdf_source == "指定路径":
                slice_pdf_path = st.text_input(
                    "PDF文件路径",
                    help="输入PDF文件的完整路径",
                    placeholder="例如：tmp/paper_bbox.pdf"
                )
            else:
                slice_pdf_path = None
            
            # bbox元数据文件路径
            slice_bbox_metadata_path = st.text_input(
                "bbox元数据文件路径",
                help="输入bbox元数据JSON文件路径（由边框提取功能生成）",
                placeholder="例如：tmp/paper_bbox_metadata.json"
            )
            
            # 输出设置
            st.subheader("📤 输出设置")
            
            slice_output_dir = st.text_input(
                "输出目录",
                value="tmp",
                help="切片图片的保存目录"
            )
            
            # 布局分析参数
            st.subheader("📐 布局分析参数")
            
            center_tolerance = st.slider(
                "中轴线容忍范围（像素）",
                min_value=10,
                max_value=200,
                value=100,
                step=10,
                help="中轴线两侧的容忍范围，用于判断元素是否属于中央区域"
            )
            
            # 切片设置说明
            st.subheader("🖼️ 切片设置")
            st.info("切片图像固定为300 DPI高分辨率，95%质量JPEG格式，确保最佳图像质量。PDF中预测框宽度或高度小于等于15px的切片将被自动丢弃。")
            
            # 布局分析说明
            st.subheader("📖 布局分析说明")
            
            st.info(
                "🔍 **布局判断逻辑**\n"
                "1. **双栏布局**: 中轴线未穿过任何元素\n"
                "2. **单栏布局**: 水平扫描线未发现多栏行（相同高度的元素都跨越中轴线）\n"
                "3. **混合布局**: 水平扫描线发现多栏行（相同高度存在不跨越中轴线的元素）\n\n"
                "📐 **切片策略**\n"
                "- 双栏区域：左右切分为两个图片\n"
                "- 单栏区域：保持完整图片\n"
                "- 混合布局：先上下分割区域，再对双栏区域左右切分"
            )
            
            st.markdown("---")
            st.markdown("### 📖 功能使用说明")
            st.markdown("""
            1. 先使用"PDF边框提取"功能生成bbox元数据
            2. 选择PDF文件和bbox元数据文件
            3. 调整布局分析参数
            4. 点击分析切片按钮
            5. 查看布局分析结果和切片图片
            6. 下载切片结果
            
            **功能特点：**
            - 🧠 智能分析论文布局（单栏/双栏/混合）
            - ✂️ 根据布局自动切片图片
            - 📊 提供详细的布局分析统计
            - 🏷️ 生成切片位置信息JSON文件
            - 📁 按页面和切片编号组织输出文件
            - 🎯 支持混合布局的复杂切片策略
            
            **输出文件结构：**
            - `{pdf文件名}_slice/`: 切片图片目录
            - `page_N_slice_M.jpg`: 切片图片文件
            - `{pdf文件名}_slice_info.json`: 切片信息文件
            
            **应用场景：**
            - 📄 论文版面分析和处理
            - 🔄 多栏文档的列分割
            - 🖼️ 图像识别的预处理
            - 📊 文档结构化分析
            """)
    
    # 根据选择的功能显示不同界面
    if function_choice == "📄➡️🖼️ PDF页面转JPG":
        show_pdf_to_jpg_interface(dpi, auto_clean)
    elif function_choice == "🖼️📤 提取PDF中的图片":
        show_image_extraction_interface(convert_to_jpg, auto_clean_extract)
    elif function_choice == "📄➡️📝 PDF解析为HTML":
        show_html_parsing_interface(dpi, processing_mode, max_workers, enable_clean, insert_images, max_retries, retry_delay)
    elif function_choice == "📝➡️📋 HTML转Markdown":
        show_html_to_markdown_interface(html_dir_input, pdf_filename_input, auto_clean_markdown)
    elif function_choice == "📦🔍 PDF边框提取":
        show_pdf_bbox_extraction_interface(
            bbox_pdf_file_source, bbox_pdf_path, bbox_output_dir,
            extract_text, extract_images, extract_tables,
            bbox_line_width, show_labels,
            show_original_lines, show_original_qwen_tables
        )
    elif function_choice == "📐✂️ 布局分析与切片":
        show_layout_analysis_interface(
            slice_pdf_source, slice_pdf_path, slice_bbox_metadata_path,
            slice_output_dir, center_tolerance
        )


def show_pdf_to_jpg_interface(dpi, auto_clean):
    
    """显示PDF页面转JPG界面"""
    # 主要内容区域
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📁 文件上传")
        
        # 文件上传
        uploaded_file = st.file_uploader(
            "选择PDF文件",
            type=['pdf'],
            accept_multiple_files=False,
            key="pdf_to_jpg_uploader"
        )
        
        if uploaded_file is not None:
            # 显示文件信息
            st.success(f"✅ 已上传文件: {uploaded_file.name}")
            st.info(f"📊 文件大小: {uploaded_file.size / 1024 / 1024:.2f} MB")
            
            # 获取PDF详细信息
            try:
                pdf_info = get_pdf_info(uploaded_file.getvalue())
                st.subheader("📋 PDF文件信息")
                for key, value in pdf_info.items():
                    st.text(f"{key}: {value}")
            except Exception as e:
                st.warning(f"⚠️ 无法获取PDF信息: {str(e)}")
    
    with col2:
        st.header("🔄 转换操作")
        
        if uploaded_file is not None:
            # 转换按钮
            if st.button("🚀 开始转换", type="primary", use_container_width=True, key="convert_pdf_button"):
                
                with st.spinner("正在转换PDF文件，请稍候..."):
                    try:
                        # 获取文件名（不含扩展名）
                        pdf_filename = uploaded_file.name.replace('.pdf', '')
                        
                        # 执行转换
                        output_paths = pdf_to_jpg(
                            uploaded_file.getvalue(),
                            pdf_filename=pdf_filename,
                            output_dir="tmp",
                            dpi=dpi
                        )
                        
                        st.success(f"✅ 转换完成！共生成 {len(output_paths)} 张图片")
                        
                        # 存储转换结果到session state
                        st.session_state.converted_images = output_paths
                        st.session_state.converted_filename = pdf_filename
                        
                        # 自动清理
                        if auto_clean:
                            clean_tmp_folder("tmp", keep_latest=1)
                        
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ 转换失败: {str(e)}")
        else:
            st.info("👆 请先上传PDF文件")
    
    # 显示转换结果
    if hasattr(st.session_state, 'converted_images') and st.session_state.converted_images:
        display_image_results(st.session_state.converted_images, st.session_state.converted_filename, "转换结果", "页")


def show_image_extraction_interface(convert_to_jpg, auto_clean_extract):
    """显示PDF图片提取界面"""
    # 主要内容区域
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📁 文件上传")
        
        # 文件上传
        uploaded_file = st.file_uploader(
            "选择PDF文件",
            type=['pdf'],
            accept_multiple_files=False,
            key="image_extract_uploader"
        )
        
        if uploaded_file is not None:
            # 显示文件信息
            st.success(f"✅ 已上传文件: {uploaded_file.name}")
            st.info(f"📊 文件大小: {uploaded_file.size / 1024 / 1024:.2f} MB")
            
            # 获取PDF图片信息
            try:
                image_info = get_pdf_image_info(uploaded_file.getvalue())
                st.subheader("📋 PDF图片信息")
                st.text(f"总图片数: {image_info['总图片数']}")
                st.text(f"总页数: {image_info['总页数']}")
                
                if image_info['总图片数'] > 0:
                    # 显示每页图片数
                    page_counts = image_info['每页图片数']
                    for i, count in enumerate(page_counts):
                        if count > 0:
                            st.text(f"第{i+1}页: {count}张图片")
                    
                    # 显示图片详情
                    with st.expander("📸 查看图片详情"):
                        for img_detail in image_info['图片详情']:
                            st.text(f"第{img_detail['页码']}页第{img_detail['图片序号']}张 - {img_detail['格式']} - {img_detail['宽度']}x{img_detail['高度']} - {img_detail['大小']}")
                else:
                    st.warning("⚠️ 该PDF文件中没有检测到图片")
                    
            except Exception as e:
                st.warning(f"⚠️ 无法获取PDF图片信息: {str(e)}")
    
    with col2:
        st.header("🔄 提取操作")
        
        if uploaded_file is not None:
            # 提取按钮
            if st.button("🚀 开始提取图片", type="primary", use_container_width=True, key="extract_images_button"):
                
                with st.spinner("正在提取PDF中的图片，请稍候..."):
                    try:
                        # 获取文件名（不含扩展名）
                        pdf_filename = uploaded_file.name.replace('.pdf', '')
                        
                        # 自动清理旧图片
                        if auto_clean_extract:
                            clean_extracted_images("tmp", pdf_filename)
                        
                        # 执行图片提取
                        extracted_paths = extract_images_from_pdf(
                            uploaded_file.getvalue(),
                            pdf_filename,
                            output_dir="tmp"
                        )
                        
                        if extracted_paths:
                            # 转换为JPG格式
                            if convert_to_jpg:
                                extracted_paths = convert_images_to_jpg(extracted_paths)
                            
                            st.success(f"✅ 提取完成！共提取 {len(extracted_paths)} 张图片")
                            
                            # 存储提取结果到session state
                            st.session_state.extracted_images = extracted_paths
                            st.session_state.extracted_filename = pdf_filename
                            
                            st.rerun()
                        else:
                            st.warning("⚠️ 未能从PDF中提取到任何图片")
                        
                    except Exception as e:
                        st.error(f"❌ 提取失败: {str(e)}")
        else:
            st.info("👆 请先上传PDF文件")
    
    # 显示提取结果
    if hasattr(st.session_state, 'extracted_images') and st.session_state.extracted_images:
        display_image_results(st.session_state.extracted_images, st.session_state.extracted_filename, "提取结果", "图片")


def display_image_results(image_paths, filename, title, item_type):
    """显示图片结果的通用函数"""
    st.markdown("---")
    st.header(f"🖼️ {title}")
    
    # 创建ZIP下载按钮
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button(f"📦 下载所有{item_type} (ZIP)", type="secondary", use_container_width=True, key=f"zip_download_{title}"):
            zip_buffer = create_zip_file(image_paths)
            if zip_buffer:
                st.download_button(
                    label="⬇️ 点击下载ZIP文件",
                    data=zip_buffer,
                    file_name=f"{filename}_{title}.zip",
                    mime="application/zip",
                    use_container_width=True,
                    key=f"zip_download_button_{title}"
                )
    
    st.subheader(f"📸 {item_type}预览")
    
    # 显示图片网格
    cols_per_row = 3
    for i in range(0, len(image_paths), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(image_paths):
                img_path = image_paths[idx]
                if os.path.exists(img_path):
                    with col:
                        # 显示图片
                        image = Image.open(img_path)
                        caption = os.path.basename(img_path)
                        st.image(image, caption=caption, use_column_width=True)
                        
                        # 单独下载按钮
                        with open(img_path, "rb") as img_file:
                            st.download_button(
                                label=f"⬇️ 下载",
                                data=img_file.read(),
                                file_name=os.path.basename(img_path),
                                mime="image/jpeg",
                                key=f"download_{title}_{idx}",
                                use_container_width=True
                            )


def show_html_parsing_interface(dpi, processing_mode, max_workers, enable_clean, insert_images, max_retries, retry_delay):
    """显示PDF HTML解析界面"""
    # 主要内容区域
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📁 文件上传")
        
        # 文件上传
        uploaded_file = st.file_uploader(
            "选择PDF文件",
            type=['pdf'],
            accept_multiple_files=False,
            key="html_parse_uploader"
        )
        
        if uploaded_file is not None:
            # 显示文件信息
            st.success(f"✅ 已上传文件: {uploaded_file.name}")
            st.info(f"📊 文件大小: {uploaded_file.size / 1024 / 1024:.2f} MB")
            
            # 获取PDF详细信息
            try:
                pdf_info = get_pdf_info(uploaded_file.getvalue())
                st.subheader("📋 PDF文件信息")
                for key, value in pdf_info.items():
                    st.text(f"{key}: {value}")
            except Exception as e:
                st.warning(f"⚠️ 无法获取PDF信息: {str(e)}")
            
            # API状态检查
            api_status = get_api_status()
            if not api_status["api_key_configured"]:
                st.error("❌ 请先配置API密钥才能使用HTML解析功能")
                st.code("export MODELSCOPE_SDK_TOKEN=your_api_key")
    
    with col2:
        st.header("🔄 解析操作")
        
        if uploaded_file is not None:
            api_status = get_api_status()
            
            if api_status["api_key_configured"]:
                # 解析按钮
                if st.button("🚀 开始解析为HTML", type="primary", use_container_width=True, key="parse_html_button"):
                    
                    with st.spinner("正在处理PDF文件，请稍候..."):
                        try:
                            # 获取文件名（不含扩展名）
                            pdf_filename = uploaded_file.name.replace('.pdf', '')
                            
                            # 步骤1：转换PDF为图片
                            st.info("步骤1/2: 转换PDF为高质量图片...")
                            output_paths = pdf_to_jpg(
                                uploaded_file.getvalue(),
                                pdf_filename=pdf_filename,
                                output_dir="tmp",
                                dpi=dpi
                            )
                            
                            st.success(f"✅ PDF转换完成！共生成 {len(output_paths)} 张图片")
                            
                            # 使用新的综合处理函数
                            if insert_images:
                                st.info("使用完整解析流程（包含图片插入）...")
                                results = parse_and_insert_images(
                                    pdf_file_bytes=uploaded_file.getvalue(),
                                    pdf_filename=pdf_filename,
                                    output_dir="tmp",
                                    parallel=(processing_mode == "⚡ 并行处理"),
                                    max_workers=max_workers,
                                    enable_clean=enable_clean,
                                    insert_extracted_images=True,
                                    max_retries=max_retries,
                                    retry_delay=retry_delay
                                )
                                
                                if results['status'] == 'success':
                                    html_files = results['html_files']
                                    st.success(f"✅ 完整解析完成！{results['message']}")
                                    st.info(f"📄 生成HTML文件: {len(html_files)} 个")
                                    st.info(f"🖼️ 提取图片: {len(results['extracted_images'])} 张")
                                else:
                                    st.error(f"❌ 解析过程出现错误: {results['message']}")
                                    html_files = results['html_files']
                            else:
                                # 步骤2：解析图片为HTML
                                clean_status = "（启用HTML清理）" if enable_clean else "（原始HTML）"
                                if processing_mode == "⚡ 并行处理":
                                    st.info(f"步骤2/2: 使用Qwen2.5-VL并行解析图片为HTML（{max_workers}线程）{clean_status}...")
                                    html_files = parse_all_images_to_html(
                                        image_paths=output_paths,
                                        pdf_filename=pdf_filename,
                                        output_dir="tmp",
                                        parallel=True,
                                        max_workers=max_workers,
                                        enable_clean=enable_clean,
                                        max_retries=max_retries,
                                        retry_delay=retry_delay
                                    )
                                else:
                                    st.info(f"步骤2/2: 使用Qwen2.5-VL串行解析图片为HTML{clean_status}...")
                                    html_files = parse_all_images_to_html(
                                        image_paths=output_paths,
                                        pdf_filename=pdf_filename,
                                        output_dir="tmp",
                                        parallel=False,
                                        enable_clean=enable_clean,
                                        max_retries=max_retries,
                                        retry_delay=retry_delay
                                    )
                            
                            if html_files:
                                st.success(f"✅ HTML解析完成！共生成 {len(html_files)} 个HTML文件")
                                
                                # 存储解析结果到session state
                                st.session_state.parsed_html_files = html_files
                                st.session_state.parsed_filename = pdf_filename
                                
                                st.rerun()
                            else:
                                st.warning("⚠️ HTML解析未能生成任何文件")
                            
                        except Exception as e:
                            st.error(f"❌ 解析失败: {str(e)}")
            else:
                st.error("❌ 请先配置API密钥")
                st.info("需要设置 MODELSCOPE_SDK_TOKEN 环境变量")
        else:
            st.info("👆 请先上传PDF文件")
    
    # 显示解析结果
    if hasattr(st.session_state, 'parsed_html_files') and st.session_state.parsed_html_files:
        display_html_results(st.session_state.parsed_html_files, st.session_state.parsed_filename)


def display_html_results(html_files, filename):
    """显示HTML解析结果"""
    st.markdown("---")
    st.header("📝 HTML解析结果")
    
    # 创建ZIP下载按钮
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("📦 下载所有HTML文件 (ZIP)", type="secondary", use_container_width=True, key="zip_download_html"):
            zip_buffer = create_zip_file(html_files)
            if zip_buffer:
                st.download_button(
                    label="⬇️ 点击下载ZIP文件",
                    data=zip_buffer,
                    file_name=f"{filename}_html_files.zip",
                    mime="application/zip",
                    use_container_width=True,
                    key="zip_download_button_html"
                )
    
    st.subheader("📄 HTML文件预览")
    
    # 显示HTML文件列表
    for i, html_path in enumerate(html_files):
        if os.path.exists(html_path):
            with st.expander(f"📄 {os.path.basename(html_path)} - 第{i+1}页"):
                # 读取HTML内容
                try:
                    with open(html_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    
                    # 显示HTML代码
                    st.code(html_content, language='html')
                    
                    # 单独下载按钮
                    with open(html_path, "rb") as html_file:
                        st.download_button(
                            label=f"⬇️ 下载 {os.path.basename(html_path)}",
                            data=html_file.read(),
                            file_name=os.path.basename(html_path),
                            mime="text/html",
                            key=f"download_html_{i}",
                            use_container_width=True
                        )
                        
                except Exception as e:
                    st.error(f"读取HTML文件失败: {str(e)}")


def show_html_to_markdown_interface(html_dir_input, pdf_filename_input, auto_clean_markdown):
    """显示HTML到Markdown转换界面"""
    # 主要内容区域
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📁 HTML文件目录")
        
        # 显示目录信息
        if html_dir_input:
            validation = validate_html_directory(html_dir_input)
            if validation['valid']:
                st.success(f"✅ 目录有效: {html_dir_input}")
                st.info(f"📊 找到 {len(validation['html_files'])} 个HTML文件")
                
                # 显示HTML文件列表
                with st.expander("📄 查看HTML文件列表"):
                    for html_file in validation['html_files']:
                        st.text(f"• {html_file}")
            else:
                st.error(f"❌ 目录无效: {validation['message']}")
        else:
            st.warning("⚠️ 请输入HTML文件目录路径")
    
    with col2:
        st.header("🔄 转换操作")
        
        # 检查输入是否有效
        can_convert = False
        if html_dir_input and pdf_filename_input:
            validation = validate_html_directory(html_dir_input)
            if validation['valid']:
                can_convert = True
        
        if can_convert:
            # 转换按钮
            if st.button("🚀 开始转换为Markdown", type="primary", use_container_width=True, key="convert_markdown_button"):
                
                with st.spinner("正在转换HTML文件为Markdown格式，请稍候..."):
                    try:
                        # 自动清理旧文件
                        if auto_clean_markdown:
                            clean_markdown_files("tmp", pdf_filename_input)
                        
                        # 执行转换
                        results = convert_html_files_to_markdown(
                            html_dir=html_dir_input,
                            pdf_filename=pdf_filename_input,
                            output_dir="tmp"
                        )
                        
                        if results['status'] == 'success':
                            st.success(f"✅ 转换完成！{results['message']}")
                            
                            # 显示统计信息
                            stats = results['statistics']
                            st.info(f"📊 转换统计：{stats['total_pages']}页，{stats['total_elements']}个元素")
                            
                            # 存储转换结果到session state
                            st.session_state.markdown_results = results
                            st.session_state.markdown_pdf_filename = pdf_filename_input
                            
                            st.rerun()
                        else:
                            st.error(f"❌ 转换失败: {results['message']}")
                        
                    except Exception as e:
                        st.error(f"❌ 转换过程中出现错误: {str(e)}")
        else:
            st.info("👆 请先输入有效的HTML目录路径和PDF文件名")
    
    # 显示转换结果
    if hasattr(st.session_state, 'markdown_results') and st.session_state.markdown_results:
        display_markdown_results(st.session_state.markdown_results, st.session_state.markdown_pdf_filename)


def display_markdown_results(results, pdf_filename):
    """显示Markdown转换结果"""
    st.markdown("---")
    st.header("📋 Markdown转换结果")
    
    # 显示转换统计信息
    stats = results['statistics']
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总页数", stats['total_pages'])
    with col2:
        st.metric("总元素数", stats['total_elements'])
    with col3:
        st.metric("标题数", stats['total_headings'])
    with col4:
        st.metric("段落数", stats['total_paragraphs'])
    
    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("公式数", stats['total_formulas'])
    with col6:
        st.metric("图片数", stats['total_images'])
    with col7:
        st.metric("表格数", stats['total_tables'])
    with col8:
        st.metric("列表数", stats['total_lists'])
    
    col9, col10, col11, col12 = st.columns(4)
    with col9:
        st.metric("完整版单页", len(results['markdown_files']))
    with col10:
        st.metric("干净版单页", len(results['clean_markdown_files']))
    with col11:
        st.metric("完整版合并", 1 if results['merged_file'] else 0)
    with col12:
        st.metric("干净版合并", 1 if results['clean_merged_file'] else 0)
    
    # 创建ZIP下载按钮
    st.subheader("📦 下载转换结果")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("📦 下载所有Markdown文件 (ZIP)", type="secondary", use_container_width=True, key="zip_download_markdown"):
            # 创建包含所有文件的ZIP
            all_files = results['markdown_files'].copy()
            all_files.extend(results['clean_markdown_files'])
            if results['merged_file']:
                all_files.append(results['merged_file'])
            if results['clean_merged_file']:
                all_files.append(results['clean_merged_file'])
            
            # 添加元数据文件
            metadata_file = os.path.join(os.path.dirname(results['merged_file']), f"{pdf_filename}_metadata.json")
            if os.path.exists(metadata_file):
                all_files.append(metadata_file)
            
            zip_buffer = create_zip_file(all_files)
            if zip_buffer:
                st.download_button(
                    label="⬇️ 点击下载ZIP文件",
                    data=zip_buffer,
                    file_name=f"{pdf_filename}_markdown_files.zip",
                    mime="application/zip",
                    use_container_width=True,
                    key="zip_download_button_markdown"
                )
    
    # 显示合并文件预览
    st.subheader("📄 合并文档预览")
    
    col1, col2 = st.columns(2)
    
    # 完整版本
    with col1:
        if results['merged_file'] and os.path.exists(results['merged_file']):
            with st.expander(f"📄 {os.path.basename(results['merged_file'])} - 完整版（含注释）"):
                # 显示预览
                preview_content = get_markdown_preview(results['merged_file'], max_lines=50)
                st.text_area("完整版预览", preview_content, height=300, key="preview_full")
                
                # 单独下载按钮
                with open(results['merged_file'], "rb") as markdown_file:
                    st.download_button(
                        label=f"⬇️ 下载完整版",
                        data=markdown_file.read(),
                        file_name=os.path.basename(results['merged_file']),
                        mime="text/markdown",
                        key="download_merged_markdown",
                        use_container_width=True
                    )
    
    # 干净版本
    with col2:
        if results['clean_merged_file'] and os.path.exists(results['clean_merged_file']):
            with st.expander(f"📄 {os.path.basename(results['clean_merged_file'])} - 干净版（纯文档）"):
                # 显示预览
                clean_preview_content = get_markdown_preview(results['clean_merged_file'], max_lines=50)
                st.text_area("干净版预览", clean_preview_content, height=300, key="preview_clean")
                
                # 单独下载按钮
                with open(results['clean_merged_file'], "rb") as clean_markdown_file:
                    st.download_button(
                        label=f"⬇️ 下载干净版",
                        data=clean_markdown_file.read(),
                        file_name=os.path.basename(results['clean_merged_file']),
                        mime="text/markdown",
                        key="download_clean_merged_markdown",
                        use_container_width=True
                    )
    
    # 显示单页文件列表
    st.subheader("📄 单页文件列表")
    
    # 创建表格显示文件信息
    for i, markdown_file in enumerate(results['markdown_files']):
        if os.path.exists(markdown_file):
            with st.expander(f"📄 第{i+1}页 - 完整版与干净版对比"):
                col1, col2 = st.columns(2)
                
                # 完整版本
                with col1:
                    st.write("**完整版（含注释和元数据）**")
                    preview_content = get_markdown_preview(markdown_file, max_lines=20)
                    st.text_area(f"完整版预览", preview_content, height=200, key=f"preview_full_{i}")
                    
                    # 单独下载按钮
                    with open(markdown_file, "rb") as md_file:
                        st.download_button(
                            label=f"⬇️ 下载完整版第{i+1}页",
                            data=md_file.read(),
                            file_name=os.path.basename(markdown_file),
                            mime="text/markdown",
                            key=f"download_page_full_{i}",
                            use_container_width=True
                        )
                
                # 干净版本
                with col2:
                    if i < len(results['clean_markdown_files']):
                        clean_markdown_file = results['clean_markdown_files'][i]
                        if os.path.exists(clean_markdown_file):
                            st.write("**干净版（纯文档内容）**")
                            clean_preview_content = get_markdown_preview(clean_markdown_file, max_lines=20)
                            st.text_area(f"干净版预览", clean_preview_content, height=200, key=f"preview_clean_{i}")
                            
                            # 单独下载按钮
                            with open(clean_markdown_file, "rb") as clean_md_file:
                                st.download_button(
                                    label=f"⬇️ 下载干净版第{i+1}页",
                                    data=clean_md_file.read(),
                                    file_name=os.path.basename(clean_markdown_file),
                                    mime="text/markdown",
                                    key=f"download_page_clean_{i}",
                                    use_container_width=True
                                )



def show_pdf_bbox_extraction_interface(pdf_file_source, pdf_path, output_dir, 
                                      extract_text, extract_images, extract_tables,
                                      line_width, show_labels,
                                      show_original_lines, show_original_qwen_tables):
    """显示PDF边框提取界面"""
    
    # 主要内容区域
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📁 文件选择")
        
        uploaded_file = None
        input_pdf_path = None
        
        if pdf_file_source == "上传文件":
            # 文件上传
            uploaded_file = st.file_uploader(
                "选择PDF文件",
                type=['pdf'],
                accept_multiple_files=False,
                key="bbox_pdf_uploader"
            )
            
            if uploaded_file is not None:
                # 显示文件信息
                st.success(f"✅ 已上传文件: {uploaded_file.name}")
                st.info(f"📊 文件大小: {uploaded_file.size / 1024 / 1024:.2f} MB")
                
                # 将上传的文件临时保存
                temp_pdf_path = os.path.join("tmp", uploaded_file.name)
                with open(temp_pdf_path, "wb") as f:
                    f.write(uploaded_file.getvalue())
                input_pdf_path = temp_pdf_path
                
        else:  # 指定路径
            if pdf_path:
                if os.path.exists(pdf_path):
                    st.success(f"✅ 找到PDF文件: {pdf_path}")
                    
                    # 显示文件信息
                    file_size = os.path.getsize(pdf_path) / 1024 / 1024
                    st.info(f"📊 文件大小: {file_size:.2f} MB")
                    
                    input_pdf_path = pdf_path
                else:
                    st.error(f"❌ 找不到文件: {pdf_path}")
            else:
                st.info("👆 请输入PDF文件路径")
        
        # 显示提取选项摘要
        if input_pdf_path:
            st.subheader("🔍 提取选项摘要")
            options = []
            if extract_text:
                options.append("🟢 文本块")
            if extract_images:
                options.append("🔴 图像")
            if extract_tables:
                options.append("🔵 表格")
            
            extra_options = []
            if show_original_lines:
                extra_options.append("🟠 原始框线")
            if show_original_qwen_tables:
                extra_options.append("🟣 原始Qwen表格")
            
            if options:
                st.info(f"将提取: {', '.join(options)}")
                if extra_options:
                    st.info(f"额外标注: {', '.join(extra_options)}")
                st.info(f"线条宽度: {line_width}")
                st.info(f"显示标签: {'是' if show_labels else '否'}")
            else:
                st.warning("⚠️ 请至少选择一种提取类型")
    
    with col2:
        st.header("🔄 提取操作")
        
        if input_pdf_path:
            # 检查是否至少选择了一种提取类型
            any_extraction_enabled = extract_text or extract_images or extract_tables
            
            if not any_extraction_enabled:
                st.warning("⚠️ 请在侧边栏至少选择一种边框提取类型")
            else:
                # 提取按钮
                if st.button("🚀 开始提取边框", type="primary", use_container_width=True, key="extract_bbox_button"):
                    
                    with st.spinner("正在提取PDF边框，请稍候..."):
                        try:
                            # 调用边框提取函数
                            result = extract_pdf_bboxes(
                                input_pdf_path, 
                                output_dir,
                                enable_table_detection=extract_tables,
                                max_retries=3,
                                retry_delay=1.0,
                                show_original_lines=show_original_lines,
                                show_original_qwen_tables=show_original_qwen_tables
                            )
                            
                            if result['status'] == 'success':
                                st.success(f"✅ {result['message']}")
                                
                                # 显示统计信息
                                stats = result['statistics']
                                if stats:
                                    st.subheader("📊 提取统计")
                                    col_stat1, col_stat2 = st.columns(2)
                                    
                                    with col_stat1:
                                        st.metric("总页数", stats.get('pages', 0))
                                        st.metric("文本块", stats.get('text_blocks', 0))
                                    
                                    with col_stat2:
                                        st.metric("图像", stats.get('images', 0))
                                        st.metric("表格", stats.get('tables', 0))
                                    
                                    total_elements = sum([
                                        stats.get('text_blocks', 0),
                                        stats.get('images', 0),
                                        stats.get('tables', 0)
                                    ])
                                    
                                    st.metric("总元素数", total_elements)
                                
                                # 存储提取结果到session state
                                st.session_state.bbox_extraction_result = result
                                
                                st.rerun()
                            else:
                                st.error(f"❌ {result['message']}")
                                
                        except Exception as e:
                            st.error(f"❌ 提取过程中出现错误: {str(e)}")
        else:
            st.info("👆 请先选择PDF文件")
    
    # 显示提取结果
    if hasattr(st.session_state, 'bbox_extraction_result') and st.session_state.bbox_extraction_result:
        display_bbox_extraction_results(st.session_state.bbox_extraction_result)


def display_bbox_extraction_results(result):
    """显示PDF边框提取结果"""
    st.markdown("---")
    st.header("📦 边框提取结果")
    
    # 显示统计信息
    stats = result['statistics']
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("总页数", stats.get('pages', 0))
        with col2:
            st.metric("文本块", stats.get('text_blocks', 0))
        with col3:
            st.metric("图像", stats.get('images', 0))
        with col4:
            st.metric("表格", stats.get('tables', 0))
        
        # 计算总元素数
        total_elements = sum([
            stats.get('text_blocks', 0),
            stats.get('images', 0),
            stats.get('tables', 0)
        ])
        
        st.info(f"🎯 总共提取了 {total_elements} 个元素的边框")
    
    # 文件下载
    output_path = result.get('output_path', '')
    if output_path and os.path.exists(output_path):
        st.subheader("📄 下载结果文件")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            # 显示输出文件信息
            file_size = os.path.getsize(output_path) / 1024 / 1024
            st.info(f"📄 输出文件: {os.path.basename(output_path)}")
            st.info(f"📊 文件大小: {file_size:.2f} MB")
            
            # 下载按钮
            with open(output_path, "rb") as pdf_file:
                st.download_button(
                    label="📥 下载带边框的PDF文件",
                    data=pdf_file.read(),
                    file_name=os.path.basename(output_path),
                    mime="application/pdf",
                    key="download_bbox_pdf",
                    use_container_width=True,
                    type="primary"
                )
        
        # 显示颜色说明
        st.subheader("🎨 边框颜色说明")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if stats.get('text_blocks', 0) > 0:
                st.success(f"🟢 文本块: {stats.get('text_blocks', 0)} 个")
            else:
                st.info("🟢 文本块: 未提取")
        
        with col2:
            if stats.get('images', 0) > 0:
                st.error(f"🔴 图像: {stats.get('images', 0)} 个")
            else:
                st.info("🔴 图像: 未提取")
        
        with col3:
            if stats.get('tables', 0) > 0:
                st.info(f"🔵 表格: {stats.get('tables', 0)} 个")
            else:
                st.info("🔵 表格: 未提取")
        
        # 处理详情
        st.subheader("📋 处理详情")
        
        processing_info = f"""
        **输入文件:** `{result.get('input_path', 'N/A')}`
        
        **输出文件:** `{result.get('output_path', 'N/A')}`
        
        **处理状态:** ✅ {result.get('message', '处理完成')}
        
        **边框颜色含义:**
        - 🟢 **绿色**: 文本块边框 (PyMuPDF)
        - 🔴 **红色**: 图像边框 (PyMuPDF)
        - 🔵 **蓝色**: 表格边框 (Qwen2.5-VL AI检测，修正后)
        - 🟠 **橙色**: PDF原始框线 (可选)
        - 🟣 **紫色**: Qwen原始表格框线 (可选，修正前)
        
        **注意事项:**
        - 边框是绘制在原PDF内容之上的
        - 不同颜色代表不同类型的元素
        - 标签显示元素类型和相关信息
        """
        
        st.markdown(processing_info)
    
    else:
        st.error("❌ 输出文件不存在或无法访问")


def show_layout_analysis_interface(pdf_file_source, pdf_path, bbox_metadata_path,
                                  output_dir, center_tolerance):
    """显示布局分析与切片界面"""
    
    # 主要内容区域
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📁 文件选择")
        
        uploaded_file = None
        input_pdf_path = None
        
        if pdf_file_source == "上传文件":
            # 文件上传
            uploaded_file = st.file_uploader(
                "选择PDF文件",
                type=['pdf'],
                accept_multiple_files=False,
                key="layout_pdf_uploader"
            )
            
            if uploaded_file is not None:
                # 显示文件信息
                st.success(f"✅ 已上传文件: {uploaded_file.name}")
                st.info(f"📊 文件大小: {uploaded_file.size / 1024 / 1024:.2f} MB")
                
                # 将上传的文件临时保存
                temp_pdf_path = os.path.join("tmp", uploaded_file.name)
                os.makedirs("tmp", exist_ok=True)
                with open(temp_pdf_path, "wb") as f:
                    f.write(uploaded_file.getvalue())
                input_pdf_path = temp_pdf_path
                
        else:  # 指定路径
            if pdf_path:
                if os.path.exists(pdf_path):
                    st.success(f"✅ 找到PDF文件: {pdf_path}")
                    
                    # 显示文件信息
                    file_size = os.path.getsize(pdf_path) / 1024 / 1024
                    st.info(f"📊 文件大小: {file_size:.2f} MB")
                    
                    input_pdf_path = pdf_path
                else:
                    st.error(f"❌ 找不到文件: {pdf_path}")
            else:
                st.info("👆 请输入PDF文件路径")
        
        # 检查bbox元数据文件
        if bbox_metadata_path:
            if os.path.exists(bbox_metadata_path):
                st.success(f"✅ 找到bbox元数据文件: {bbox_metadata_path}")
                
                # 显示元数据文件信息
                try:
                    import json
                    with open(bbox_metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    total_pages = metadata.get('total_pages', 0)
                    summary = metadata.get('summary', {})
                    st.info(f"📄 包含{total_pages}页的bbox信息")
                    st.info(f"📊 元素统计: 文本{summary.get('total_text_blocks', 0)} | 图像{summary.get('total_images', 0)} | 表格{summary.get('total_tables', 0)}")
                    
                except Exception as e:
                    st.warning(f"⚠️ 读取元数据文件时出错: {str(e)}")
            else:
                st.error(f"❌ 找不到bbox元数据文件: {bbox_metadata_path}")
        else:
            st.info("👆 请输入bbox元数据文件路径")
        
        # 显示参数摘要
        if input_pdf_path and bbox_metadata_path and os.path.exists(bbox_metadata_path):
            st.subheader("⚙️ 分析参数摘要")
            st.info(f"中轴线容忍范围: {center_tolerance}px")
            st.info(f"图片分辨率: 300 DPI")
            st.info(f"输出目录: {output_dir}")
    
    with col2:
        st.header("🔄 分析操作")
        
        # 检查所有必需的输入
        can_analyze = (input_pdf_path and bbox_metadata_path and 
                      os.path.exists(input_pdf_path) and os.path.exists(bbox_metadata_path))
        
        if can_analyze:
            # 分析按钮
            if st.button("🚀 开始布局分析与切片", type="primary", use_container_width=True, key="analyze_layout_button"):
                
                with st.spinner("正在分析PDF布局并切片，请稍候..."):
                    try:
                        # 调用布局分析和切片函数
                        result = analyze_and_slice_pdf(
                            input_pdf_path, 
                            bbox_metadata_path, 
                            output_dir
                        )
                        
                        if result['status'] == 'success':
                            st.success(f"✅ {result['message']}")
                            
                            # 显示处理结果统计
                            results = result['results']
                            if results:
                                summary = results.get('slice_summary', {})
                                st.subheader("📊 处理统计")
                                
                                col_stat1, col_stat2 = st.columns(2)
                                
                                with col_stat1:
                                    st.metric("处理页数", summary.get('processed_pages', 0))
                                    st.metric("总切片数", summary.get('total_slices', 0))
                                
                                with col_stat2:
                                    layout_dist = summary.get('layout_distribution', {})
                                    single_count = layout_dist.get('single', 0)
                                    double_count = layout_dist.get('double', 0)
                                    mixed_count = layout_dist.get('mixed', 0)
                                    
                                    st.metric("单栏页面", single_count)
                                    st.metric("双栏页面", double_count)
                                    if mixed_count > 0:
                                        st.metric("混合布局页面", mixed_count)
                                
                                # 显示布局分布
                                if layout_dist:
                                    st.subheader("📐 布局分布")
                                    layout_info = []
                                    if single_count > 0:
                                        layout_info.append(f"🟢 单栏: {single_count}页")
                                    if double_count > 0:
                                        layout_info.append(f"🔵 双栏: {double_count}页")
                                    if mixed_count > 0:
                                        layout_info.append(f"🟡 混合: {mixed_count}页")
                                    
                                    st.info(" | ".join(layout_info))
                            
                            # 存储分析结果到session state
                            st.session_state.layout_analysis_result = result
                            
                            st.rerun()
                        else:
                            st.error(f"❌ {result['message']}")
                            
                    except Exception as e:
                        st.error(f"❌ 分析过程中出现错误: {str(e)}")
        else:
            if not input_pdf_path:
                st.info("👆 请先选择PDF文件")
            elif not bbox_metadata_path:
                st.info("👆 请输入bbox元数据文件路径")
            elif not os.path.exists(bbox_metadata_path):
                st.info("👆 请确保bbox元数据文件存在")
            else:
                st.info("👆 请检查所有输入文件")
    
    # 显示分析结果
    if hasattr(st.session_state, 'layout_analysis_result') and st.session_state.layout_analysis_result:
        display_layout_analysis_results(st.session_state.layout_analysis_result)


def display_layout_analysis_results(result):
    """显示布局分析和切片结果"""
    st.markdown("---")
    st.header("📐 布局分析与切片结果")
    
    results = result.get('results', {})
    if not results:
        st.error("❌ 无法显示分析结果")
        return
    
    # 显示总体统计
    summary = results.get('slice_summary', {})
    slice_info = results.get('slice_info', {})
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总页数", results.get('total_pages', 0))
    with col2:
        st.metric("处理页数", summary.get('processed_pages', 0))
    with col3:
        st.metric("总切片数", summary.get('total_slices', 0))
    with col4:
        avg_slices = summary.get('total_slices', 0) / max(summary.get('processed_pages', 1), 1)
        st.metric("平均切片/页", f"{avg_slices:.1f}")
    
    # 显示布局分布
    layout_dist = summary.get('layout_distribution', {})
    if layout_dist:
        st.subheader("📊 布局类型分布")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            single_count = layout_dist.get('single', 0)
            if single_count > 0:
                st.success(f"🟢 单栏布局: {single_count} 页")
            else:
                st.info("🟢 单栏布局: 0 页")
        
        with col2:
            double_count = layout_dist.get('double', 0)
            if double_count > 0:
                st.info(f"🔵 双栏布局: {double_count} 页")
            else:
                st.info("🔵 双栏布局: 0 页")
        
        with col3:
            mixed_count = layout_dist.get('mixed', 0)
            if mixed_count > 0:
                st.warning(f"🟡 混合布局: {mixed_count} 页")
            else:
                st.info("🟡 混合布局: 0 页")
    
    # 显示输出文件信息
    output_dir = results.get('output_directory', '')
    json_path = result.get('json_path', '')
    
    if output_dir and os.path.exists(output_dir):
        st.subheader("📁 输出文件")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.info(f"📁 切片图片目录: {output_dir}")
            if json_path and os.path.exists(json_path):
                st.info(f"📋 切片信息文件: {os.path.basename(json_path)}")
                
                # 下载切片信息JSON文件
                with open(json_path, "rb") as json_file:
                    st.download_button(
                        label="📥 下载切片信息JSON",
                        data=json_file.read(),
                        file_name=os.path.basename(json_path),
                        mime="application/json",
                        key="download_slice_json",
                        use_container_width=True
                    )
        
        # 创建切片图片ZIP下载
        slice_images = []
        for page_info in slice_info.values():
            for slice_data in page_info.get('slices', []):
                slice_path = slice_data.get('file_path', '')
                if slice_path and os.path.exists(slice_path):
                    slice_images.append(slice_path)
        
        if slice_images:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("📦 下载所有切片图片 (ZIP)", type="secondary", use_container_width=True, key="zip_download_slices"):
                    zip_buffer = create_zip_file(slice_images)
                    if zip_buffer:
                        pdf_filename = results.get('pdf_filename', 'pdf')
                        st.download_button(
                            label="⬇️ 点击下载ZIP文件",
                            data=zip_buffer,
                            file_name=f"{pdf_filename}_slices.zip",
                            mime="application/zip",
                            use_container_width=True,
                            key="zip_download_button_slices"
                        )
    
    # 显示详细的页面分析结果
    st.subheader("📄 页面详细分析")
    
    for page_num, page_info in slice_info.items():
        layout_analysis = page_info.get('layout_analysis', {})
        slices = page_info.get('slices', [])
        
        layout_name = layout_analysis.get('layout_name', '未知')
        layout_type = layout_analysis.get('layout_type', 'unknown')
        analysis_details = layout_analysis.get('analysis_details', '')
        
        # 根据布局类型选择颜色
        if layout_type == 'single':
            color = "🟢"
        elif layout_type == 'double':
            color = "🔵"
        elif layout_type == 'mixed':
            color = "🟡"
        else:
            color = "⚪"
        
        with st.expander(f"{color} 第{page_num}页 - {layout_name} ({len(slices)}个切片)"):
            st.text(f"分析详情: {analysis_details}")
            
            # 显示页面尺寸
            page_dims = page_info.get('page_dimensions', {})
            image_dims = page_info.get('image_dimensions', {})
            st.text(f"页面尺寸: {page_dims.get('width', 0):.1f} x {page_dims.get('height', 0):.1f}")
            st.text(f"图片尺寸: {image_dims.get('width', 0)} x {image_dims.get('height', 0)}")
            
            # 显示切片信息
            if slices:
                st.subheader("🔪 切片详情")
                
                # 显示切片图片网格
                cols_per_row = min(3, len(slices))
                for i in range(0, len(slices), cols_per_row):
                    cols = st.columns(cols_per_row)
                    for j, col in enumerate(cols):
                        idx = i + j
                        if idx < len(slices):
                            slice_data = slices[idx]
                            slice_path = slice_data.get('file_path', '')
                            
                            if slice_path and os.path.exists(slice_path):
                                with col:
                                    # 显示切片图片
                                    image = Image.open(slice_path)
                                    
                                    region_type = slice_data.get('region_type', '')
                                    slice_filename = slice_data.get('filename', '')
                                    width = slice_data.get('width', 0)
                                    height = slice_data.get('height', 0)
                                    
                                    caption = f"{slice_filename}\n类型: {region_type}\n尺寸: {width}x{height}"
                                    st.image(image, caption=caption, use_column_width=True)
                                    
                                    # 单独下载按钮
                                    with open(slice_path, "rb") as img_file:
                                        st.download_button(
                                            label="⬇️ 下载",
                                            data=img_file.read(),
                                            file_name=slice_filename,
                                            mime="image/jpeg",
                                            key=f"download_slice_{page_num}_{idx}",
                                            use_container_width=True
                                        )


def create_zip_file(image_paths):
    """创建包含所有图片的ZIP文件"""
    try:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for img_path in image_paths:
                if os.path.exists(img_path):
                    zip_file.write(img_path, os.path.basename(img_path))
        
        zip_buffer.seek(0)
        return zip_buffer.getvalue()
    except Exception as e:
        st.error(f"创建ZIP文件时出现错误: {str(e)}")
        return None


if __name__ == "__main__":
    # 确保tmp文件夹存在
    os.makedirs("tmp", exist_ok=True)
    
    main()