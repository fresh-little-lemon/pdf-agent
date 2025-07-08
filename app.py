import streamlit as st
import os
from PIL import Image
import zipfile
import io
from utils.pdf_converter import pdf_to_jpg, get_pdf_info, clean_tmp_folder
from utils.image_extractor import extract_images_from_pdf, get_pdf_image_info, clean_extracted_images, convert_images_to_jpg
from utils.html_parser import parse_images_to_html, get_api_status, batch_parse_images_to_html, parse_all_images_to_html, parse_and_insert_images
from utils.html_to_markdown import convert_html_files_to_markdown, validate_html_directory, get_markdown_preview, clean_markdown_files
from agent.layout_validation_agent import create_layout_validation_agent


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
        ["📄➡️🖼️ PDF页面转JPG", "🖼️📤 提取PDF中的图片", "📄➡️📝 PDF解析为HTML", "📝➡️📋 HTML转Markdown", "🔄📝 布局验证智能体"],
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
        else:  # 布局验证智能体
            st.header("⚙️ 布局验证智能体设置")
            
            # PDF文件名输入
            pdf_filename_layout = st.text_input(
                "PDF文件名（不含扩展名）",
                value="v9",
                help="输入PDF文件名，将在tmp目录下查找对应的_html和_converted_to_img文件夹"
            )
            
            # 线程数设置
            max_workers_layout = st.slider(
                "最大工作线程数",
                min_value=1,
                max_value=20,
                value=10,
                help="同时处理的最大线程数，建议5-10个"
            )
            
            # 检查所需文件夹是否存在
            if pdf_filename_layout:
                html_dir_layout = os.path.join("tmp", f"{pdf_filename_layout}_html")
                image_dir_layout = os.path.join("tmp", f"{pdf_filename_layout}_converted_to_img")
                
                col1, col2 = st.columns(2)
                with col1:
                    if os.path.exists(html_dir_layout):
                        html_files = [f for f in os.listdir(html_dir_layout) if f.endswith('.html')]
                        st.success(f"✅ HTML目录存在 ({len(html_files)}个文件)")
                    else:
                        st.error("❌ HTML目录不存在")
                
                with col2:
                    if os.path.exists(image_dir_layout):
                        image_files = [f for f in os.listdir(image_dir_layout) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                        st.success(f"✅ 图片目录存在 ({len(image_files)}个文件)")
                    else:
                        st.error("❌ 图片目录不存在")
            
            # API状态检查
            api_status = get_api_status()
            if api_status["api_key_configured"]:
                st.success("✅ API密钥已配置")
            else:
                st.error("❌ 请设置 MODELSCOPE_SDK_TOKEN 环境变量")
                
            st.markdown("---")
            st.markdown("### 📖 布局验证智能体说明")
            st.markdown("""
            1. 选择PDF文件名（需要已解析的HTML文件）
            2. 随机选择一张图片检测是否为双栏布局
            3. 如果是双栏布局，使用多线程重新排序HTML元素
            4. 为每个HTML元素添加order字段标注阅读顺序
            5. 备份原始文件并应用新的排序
            
            **处理流程：**
            - 🔍 双栏布局检测：使用Qwen2.5-VL分析论文布局
            - 🔄 多线程重排序：同时处理多个页面提升效率
            - 📝 元素排序：按照从上到下、从左到右的阅读顺序
            - 💾 文件管理：自动备份原始文件到origin文件夹
            
            **注意事项：**
            - 🎯 专门针对双栏布局的学术论文优化
            - 📁 需要先使用PDF解析功能生成HTML文件
            - 🔧 处理完成后会自动替换原始HTML文件
            - 📦 原始文件会备份到origin文件夹中
            """)
    
    # 根据选择的功能显示不同界面
    if function_choice == "📄➡️🖼️ PDF页面转JPG":
        show_pdf_to_jpg_interface(dpi, auto_clean)
    elif function_choice == "🖼️📤 提取PDF中的图片":
        show_image_extraction_interface(convert_to_jpg, auto_clean_extract)
    elif function_choice == "📄➡️📝 PDF解析为HTML":
        show_html_parsing_interface(dpi, processing_mode, max_workers, enable_clean, insert_images)
    elif function_choice == "📝➡️📋 HTML转Markdown":
        show_html_to_markdown_interface(html_dir_input, pdf_filename_input, auto_clean_markdown)
    else:  # 布局验证智能体
        show_layout_validation_interface(pdf_filename_layout, max_workers_layout)


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


def show_html_parsing_interface(dpi, processing_mode, max_workers, enable_clean, insert_images):
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
                                    insert_extracted_images=True
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
                                        enable_clean=enable_clean
                                    )
                                else:
                                    st.info(f"步骤2/2: 使用Qwen2.5-VL串行解析图片为HTML{clean_status}...")
                                    html_files = parse_all_images_to_html(
                                        image_paths=output_paths,
                                        pdf_filename=pdf_filename,
                                        output_dir="tmp",
                                        parallel=False,
                                        enable_clean=enable_clean
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


def show_layout_validation_interface(pdf_filename, max_workers):
    """显示布局验证智能体界面"""
    st.header("🔄 布局验证智能体")
    
    # 检查输入参数
    if not pdf_filename:
        st.warning("⚠️ 请在侧边栏输入PDF文件名")
        return
    
    # 检查必要的目录和文件
    html_dir = os.path.join("tmp", f"{pdf_filename}_html")
    image_dir = os.path.join("tmp", f"{pdf_filename}_converted_to_img")
    
    if not os.path.exists(html_dir):
        st.error(f"❌ HTML目录不存在: {html_dir}")
        st.info("💡 请先使用'PDF解析为HTML'功能生成HTML文件")
        return
    
    if not os.path.exists(image_dir):
        st.error(f"❌ 图片目录不存在: {image_dir}")
        st.info("💡 请先使用'PDF页面转JPG'功能生成图片文件")
        return
    
    # 显示文件信息
    st.subheader("📁 文件信息")
    col1, col2 = st.columns(2)
    
    with col1:
        html_files = [f for f in os.listdir(html_dir) if f.endswith('.html') and f.startswith('page_')]
        st.info(f"📄 HTML文件数量: {len(html_files)}")
        
        if html_files:
            with st.expander("查看HTML文件列表"):
                for html_file in sorted(html_files):
                    st.text(f"• {html_file}")
    
    with col2:
        image_files = [f for f in os.listdir(image_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        st.info(f"🖼️ 图片文件数量: {len(image_files)}")
        
        if image_files:
            with st.expander("查看图片文件列表"):
                for image_file in sorted(image_files):
                    st.text(f"• {image_file}")
    
    # 检查API状态
    api_status = get_api_status()
    if not api_status["api_key_configured"]:
        st.error("❌ API密钥未配置，请设置 MODELSCOPE_SDK_TOKEN 环境变量")
        return
    
    # 验证按钮
    st.subheader("🚀 开始验证")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔍 开始布局验证与重排序", type="primary", use_container_width=True, key="validate_layout_button"):
            if not html_files or not image_files:
                st.error("❌ 缺少必要的HTML或图片文件")
                return
            
            # 创建进度条
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # 创建布局验证智能体
                status_text.text("正在初始化布局验证智能体...")
                progress_bar.progress(10)
                
                agent = create_layout_validation_agent(max_workers=max_workers)
                
                # 开始验证和重排序
                status_text.text("正在进行布局验证和重排序...")
                progress_bar.progress(30)
                
                result = agent.validate_and_reorder_layout(pdf_filename, "tmp")
                
                progress_bar.progress(100)
                status_text.text("处理完成！")
                
                # 显示处理结果
                st.success("✅ 布局验证完成！")
                
                # 存储结果到session state
                st.session_state.layout_validation_result = result
                st.session_state.layout_validation_pdf = pdf_filename
                
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ 布局验证过程中出现错误: {str(e)}")
                progress_bar.empty()
                status_text.empty()
    
    # 显示验证结果
    if hasattr(st.session_state, 'layout_validation_result') and st.session_state.layout_validation_result:
        display_layout_validation_results(st.session_state.layout_validation_result, st.session_state.layout_validation_pdf)


def display_layout_validation_results(result, pdf_filename):
    """显示布局验证结果"""
    st.markdown("---")
    st.header("📊 布局验证结果")
    
    # 显示基本信息
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        status_color = "🟢" if result['status'] == 'success' else "🔴"
        st.metric("处理状态", f"{status_color} {result['status']}")
    
    with col2:
        layout_type = "双栏" if result['is_double_column'] else "单栏"
        st.metric("布局类型", f"📄 {layout_type}")
    
    with col3:
        if result['status'] == 'success' and result.get('processed_files'):
            st.metric("处理成功", len(result['processed_files']))
        else:
            st.metric("处理成功", 0)
    
    with col4:
        if result['status'] == 'success' and result.get('failed_files'):
            st.metric("处理失败", len(result['failed_files']))
        else:
            st.metric("处理失败", 0)
    
    # 显示处理消息
    if result['status'] == 'success':
        st.success(f"✅ {result['message']}")
    else:
        st.error(f"❌ {result['message']}")
    
    # 显示详细结果
    if result['status'] == 'success' and result['is_double_column']:
        st.subheader("📄 处理详情")
        
        # 成功处理的文件
        if result.get('processed_files'):
            with st.expander(f"✅ 成功处理的文件 ({len(result['processed_files'])}个)"):
                for file in result['processed_files']:
                    st.text(f"• {file}")
        
        # 失败处理的文件
        if result.get('failed_files'):
            with st.expander(f"❌ 处理失败的文件 ({len(result['failed_files'])}个)"):
                for file in result['failed_files']:
                    st.text(f"• {file}")
        
        # 文件管理信息
        st.subheader("📁 文件管理")
        html_dir = os.path.join("tmp", f"{pdf_filename}_html")
        origin_dir = os.path.join(html_dir, "origin")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("📂 原始文件备份")
            st.text(f"备份目录: {origin_dir}")
            if os.path.exists(origin_dir):
                backup_files = [f for f in os.listdir(origin_dir) if f.endswith('.html')]
                st.text(f"备份文件数: {len(backup_files)}个")
        
        with col2:
            st.info("🔄 更新后的文件")
            st.text(f"HTML目录: {html_dir}")
            if os.path.exists(html_dir):
                updated_files = [f for f in os.listdir(html_dir) if f.endswith('.html') and f.startswith('page_')]
                st.text(f"更新文件数: {len(updated_files)}个")
        
        # 提示信息
        st.info("💡 处理完成后，原始HTML文件已备份到origin文件夹，新的带有order字段的HTML文件已替换原始文件")
    
    elif result['status'] == 'success' and not result['is_double_column']:
        st.info("ℹ️ 检测到单栏布局，无需重新排序HTML元素")


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
    if not os.path.exists("tmp"):
        os.makedirs("tmp")
    
    main()