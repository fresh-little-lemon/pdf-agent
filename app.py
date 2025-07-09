#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import streamlit as st
import os
import tempfile
import logging
import sys
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import time

# 导入自定义工具
from utils.pdf_bbox_extractor import extract_pdf_bboxes
from utils.layout_analyzer import analyze_and_slice_pdf
from utils.html_parser import parse_all_images_to_html, get_api_status
from utils.html_to_markdown import convert_html_files_to_markdown, validate_html_directory

# 导入Agent模块
from agent.paper_summary_agent import PaperSummaryAgent
from agent.paper_qa_agent import PaperQAAgent


class WorkflowLogger:
    """工作流日志管理器"""
    
    def __init__(self, log_file: str = "pdf_workflow.log"):
        self.log_file = log_file
        self.setup_logging()
    
    def setup_logging(self):
        """设置日志系统"""
        # 创建日志目录在/tmp下
        logs_dir = "/tmp/logs"
        os.makedirs(logs_dir, exist_ok=True)
        log_path = os.path.join(logs_dir, self.log_file)
        
        # 配置日志格式
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        
    def info(self, message: str):
        """记录信息日志"""
        self.logger.info(message)
    
    def error(self, message: str):
        """记录错误日志"""
        self.logger.error(message)
    
    def warning(self, message: str):
        """记录警告日志"""
        self.logger.warning(message)


class PDFAnalysisWorkflow:
    """PDF分析工作流管理器"""
    
    def __init__(self, logger: WorkflowLogger):
        self.logger = logger
        self.temp_dir = None
        self.workflow_results = {}
        
        # 初始化Agent
        self.summary_agent = PaperSummaryAgent(logger.logger)
        self.qa_agent = PaperQAAgent(logger.logger)
        
    def create_temp_directory(self) -> str:
        """创建临时目录"""
        if self.temp_dir is None:
            # 使用固定的/tmp目录
            base_tmp_dir = "/tmp"
            if not os.path.exists(base_tmp_dir):
                os.makedirs(base_tmp_dir, exist_ok=True)
            self.temp_dir = tempfile.mkdtemp(prefix="pdf_workflow_", dir=base_tmp_dir)
            self.logger.info(f"创建临时工作目录: {self.temp_dir}")
        return self.temp_dir
    
    def save_uploaded_file(self, uploaded_file, filename: str) -> str:
        """保存上传的文件"""
        temp_dir = self.create_temp_directory()
        file_path = os.path.join(temp_dir, filename)
        
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        self.logger.info(f"保存上传文件: {file_path}")
        return file_path
    
    def step1_extract_bboxes(self, pdf_path: str) -> Dict[str, Any]:
        """步骤1: 提取PDF边界框"""
        self.logger.info("=" * 60)
        self.logger.info("步骤1: 开始PDF边界框提取")
        self.logger.info("=" * 60)
        
        try:
            result = extract_pdf_bboxes(
                input_pdf_path=pdf_path,
                output_dir=self.temp_dir,
                enable_table_detection=True,
                show_original_lines=True,  # 启用原始框线以支持矢量图检测
                show_original_qwen_tables=False,
                max_workers=10  # 使用10个工作线程
            )
            
            self.workflow_results['bbox_extraction'] = result
            
            if result['status'] == 'success':
                self.logger.info(f"✅ 边界框提取成功: {result['message']}")
                self.logger.info(f"📊 统计信息: {result['statistics']}")
                return result
            else:
                self.logger.error(f"❌ 边界框提取失败: {result['message']}")
                return result
                
        except Exception as e:
            error_msg = f"边界框提取过程中出错: {str(e)}"
            self.logger.error(error_msg)
            return {'status': 'error', 'message': error_msg}
    
    def step2_analyze_layout_and_slice(self, pdf_path: str, metadata_path: str) -> Dict[str, Any]:
        """步骤2: 布局分析和切片"""
        self.logger.info("=" * 60)
        self.logger.info("步骤2: 开始布局分析和切片")
        self.logger.info("=" * 60)
        
        try:
            result = analyze_and_slice_pdf(
                pdf_path=pdf_path,
                bbox_metadata_path=metadata_path,
                output_dir=self.temp_dir
            )
            
            self.workflow_results['layout_analysis'] = result
            
            if result['status'] == 'success':
                self.logger.info(f"✅ 布局分析和切片成功: {result['message']}")
                
                # 获取切片统计信息
                if 'results' in result and 'slice_summary' in result['results']:
                    summary = result['results']['slice_summary']
                    self.logger.info(f"📊 切片统计: 总切片数={summary['total_slices']}, "
                                   f"丢弃={summary['total_discarded']}, "
                                   f"不规则切片={summary['total_irregular']}")
                
                return result
            else:
                self.logger.error(f"❌ 布局分析和切片失败: {result['message']}")
                return result
                
        except Exception as e:
            error_msg = f"布局分析和切片过程中出错: {str(e)}"
            self.logger.error(error_msg)
            return {'status': 'error', 'message': error_msg}
    
    def step3_parse_slices_to_html(self, slice_dir: str, pdf_filename: str) -> Dict[str, Any]:
        """步骤3: 将切片图像解析为HTML"""
        self.logger.info("=" * 60)
        self.logger.info("步骤3: 开始将切片图像解析为HTML")
        self.logger.info("=" * 60)
        
        try:
            # 获取切片图像文件
            slice_images = []
            if os.path.exists(slice_dir):
                for file in sorted(os.listdir(slice_dir)):
                    if file.endswith('.jpg') and 'slice' in file:
                        slice_images.append(os.path.join(slice_dir, file))
            
            if not slice_images:
                error_msg = f"在切片目录中未找到图像文件: {slice_dir}"
                self.logger.error(error_msg)
                return {'status': 'error', 'message': error_msg}
            
            self.logger.info(f"找到 {len(slice_images)} 个切片图像")
            
            # 解析切片图像为HTML
            html_files = parse_all_images_to_html(
                image_paths=slice_images,
                pdf_filename=f"{pdf_filename}_slices",
                output_dir=self.temp_dir,
                parallel=True,  # 使用并行处理提高效率
                max_workers=10,  # 使用10个工作线程
                enable_clean=False,
                max_retries=3,
                retry_delay=2.0
            )
            
            result = {
                'status': 'success',
                'message': f'成功解析 {len(html_files)} 个切片为HTML',
                'html_files': html_files,
                'slice_count': len(slice_images)
            }
            
            self.workflow_results['html_parsing'] = result
            self.logger.info(f"✅ HTML解析成功: {result['message']}")
            
            return result
            
        except Exception as e:
            error_msg = f"HTML解析过程中出错: {str(e)}"
            self.logger.error(error_msg)
            return {'status': 'error', 'message': error_msg}
    
    def step4_convert_html_to_markdown(self, html_dir: str, pdf_filename: str) -> Dict[str, Any]:
        """步骤4: 将HTML转换为Markdown"""
        self.logger.info("=" * 60)
        self.logger.info("步骤4: 开始将HTML转换为Markdown")
        self.logger.info("=" * 60)
        
        try:
            # 验证HTML目录
            validation = validate_html_directory(html_dir)
            if not validation['valid']:
                self.logger.error(f"❌ HTML目录验证失败: {validation['message']}")
                return {'status': 'error', 'message': validation['message']}
            
            self.logger.info(f"HTML目录验证成功: {validation['message']}")
            
            # 转换HTML为Markdown
            result = convert_html_files_to_markdown(
                html_dir=html_dir,
                pdf_filename=f"{pdf_filename}_slices",
                output_dir=self.temp_dir
            )
            
            self.workflow_results['markdown_conversion'] = result
            
            if result['status'] == 'success':
                self.logger.info(f"✅ Markdown转换成功: {result['message']}")
                self.logger.info(f"📊 文档统计: {result['statistics']}")
                return result
            else:
                self.logger.error(f"❌ Markdown转换失败: {result['message']}")
                return result
                
        except Exception as e:
            error_msg = f"Markdown转换过程中出错: {str(e)}"
            self.logger.error(error_msg)
            return {'status': 'error', 'message': error_msg}
    
    def step5_summarize_paper(self, markdown_file: str) -> Dict[str, Any]:
        """步骤5: 使用论文总结Agent"""
        try:
            # 使用PaperSummaryAgent进行总结
            result = self.summary_agent.summarize_paper(markdown_file)
            self.workflow_results['paper_summary'] = result
            return result
            
        except Exception as e:
            error_msg = f"论文总结过程中出错: {str(e)}"
            self.logger.error(error_msg)
            return {'status': 'error', 'message': error_msg}
    
    def answer_question(self, question: str, markdown_content: str, 
                       conversation_history: List[Dict] = None, slice_images_dir: str = None) -> str:
        """基于论文内容回答问题（支持视觉功能）"""
        try:
            # 使用PaperQAAgent进行智能问答
            answer = self.qa_agent.answer_question(
                question=question,
                markdown_content=markdown_content,
                conversation_history=conversation_history,
                slice_images_dir=slice_images_dir
            )
            
            self.logger.info(f"✅ 问答成功，问题: {question[:50]}...")
            return answer
            
        except Exception as e:
            error_msg = f"问答过程中出错: {str(e)}"
            self.logger.error(error_msg)
            return f"抱歉，回答您的问题时出现了错误：{error_msg}"


def initialize_session_state():
    """初始化Session State"""
    if 'workflow' not in st.session_state:
        st.session_state.workflow = None
    if 'workflow_completed' not in st.session_state:
        st.session_state.workflow_completed = False
    if 'paper_summary' not in st.session_state:
        st.session_state.paper_summary = None
    if 'markdown_content' not in st.session_state:
        st.session_state.markdown_content = None
    if 'conversation_history' not in st.session_state:
        st.session_state.conversation_history = []
    if 'slice_images_dir' not in st.session_state:
        st.session_state.slice_images_dir = None
    if 'logger' not in st.session_state:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state.logger = WorkflowLogger(f"pdf_workflow_{timestamp}.log")


def main():
    """主应用入口"""
    st.set_page_config(
        page_title="PDF论文分析助手",
        page_icon="📄",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 初始化Session State
    initialize_session_state()
    
    logger = st.session_state.logger
    
    st.title("📄 PDF论文分析助手")
    st.markdown("---")
    
    # 侧边栏 - 工作流控制
    with st.sidebar:
        st.header("🔧 工作流控制")
        
        # API状态检查
        api_status = get_api_status()
        if api_status['api_key_configured']:
            st.success("✅ API配置正常")
        else:
            st.error("❌ 请配置API密钥")
            st.info("请设置 MODELSCOPE_SDK_TOKEN 或 DASHSCOPE_API_KEY 环境变量")
        
        st.markdown("---")
        
        # 文件上传
        uploaded_file = st.file_uploader(
            "📤 上传PDF文件",
            type=['pdf'],
            help="支持PDF格式文件"
        )
        
        if uploaded_file is not None:
            st.success(f"✅ 文件已上传: {uploaded_file.name}")
            
            # 开始工作流按钮
            if st.button("🚀 开始分析", type="primary", use_container_width=True):
                if not api_status['api_key_configured']:
                    st.error("请先配置API密钥")
                else:
                    run_workflow(uploaded_file, logger)
        
        st.markdown("---")
        
        # 工作流状态
        st.header("📊 处理状态")
        if st.session_state.workflow is not None:
            workflow = st.session_state.workflow
            results = workflow.workflow_results
            
            # 显示各步骤状态
            steps = [
                ("1️⃣ 边界框提取", "bbox_extraction"),
                ("2️⃣ 布局分析切片", "layout_analysis"),
                ("3️⃣ HTML解析", "html_parsing"),
                ("4️⃣ Markdown转换", "markdown_conversion"),
                ("5️⃣ 论文总结", "paper_summary")
            ]
            
            for step_name, step_key in steps:
                if step_key in results:
                    result = results[step_key]
                    if result['status'] == 'success':
                        st.success(f"{step_name} ✅")
                    else:
                        st.error(f"{step_name} ❌")
                else:
                    st.info(f"{step_name} ⏳")
        
        # 清除数据按钮
        if st.button("🗑️ 清除数据", use_container_width=True):
            clear_session_data()
    
    # 主内容区域
    if st.session_state.workflow_completed and st.session_state.paper_summary:
        # 显示论文总结和问答界面
        show_chat_interface(logger)
    else:
        # 显示欢迎页面
        show_welcome_page()


def run_workflow(uploaded_file, logger: WorkflowLogger):
    """运行完整的PDF分析工作流"""
    try:
        # 创建工作流实例
        workflow = PDFAnalysisWorkflow(logger)
        st.session_state.workflow = workflow
        
        # 显示进度
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 保存上传的文件
        status_text.text("保存上传文件...")
        pdf_filename = os.path.splitext(uploaded_file.name)[0]
        pdf_path = workflow.save_uploaded_file(uploaded_file, uploaded_file.name)
        progress_bar.progress(10)
        
        # 步骤1: 边界框提取
        status_text.text("步骤1/5: 提取PDF边界框...")
        bbox_result = workflow.step1_extract_bboxes(pdf_path)
        if bbox_result['status'] != 'success':
            st.error(f"边界框提取失败: {bbox_result['message']}")
            return
        progress_bar.progress(30)
        
        # 步骤2: 布局分析和切片
        status_text.text("步骤2/5: 布局分析和切片...")
        metadata_path = bbox_result['metadata_path']
        slice_result = workflow.step2_analyze_layout_and_slice(pdf_path, metadata_path)
        if slice_result['status'] != 'success':
            st.error(f"布局分析和切片失败: {slice_result['message']}")
            return
        progress_bar.progress(50)
        
        # 获取切片目录
        slice_output_dir = slice_result['results']['output_directory']
        
        # 步骤3: HTML解析
        status_text.text("步骤3/5: 解析切片为HTML...")
        html_result = workflow.step3_parse_slices_to_html(slice_output_dir, pdf_filename)
        if html_result['status'] != 'success':
            st.error(f"HTML解析失败: {html_result['message']}")
            return
        progress_bar.progress(70)
        
        # 步骤4: Markdown转换
        status_text.text("步骤4/5: 转换HTML为Markdown...")
        html_dir = os.path.join(workflow.temp_dir, f"{pdf_filename}_slices_html")
        markdown_result = workflow.step4_convert_html_to_markdown(html_dir, pdf_filename)
        if markdown_result['status'] != 'success':
            st.error(f"Markdown转换失败: {markdown_result['message']}")
            return
        progress_bar.progress(85)
        
        # 步骤5: 论文总结
        status_text.text("步骤5/5: 生成论文总结...")
        clean_markdown_file = markdown_result['clean_merged_file']
        summary_result = workflow.step5_summarize_paper(clean_markdown_file)
        if summary_result['status'] != 'success':
            st.error(f"论文总结失败: {summary_result['message']}")
            return
        progress_bar.progress(100)
        
        # 工作流完成
        status_text.text("✅ 分析完成！")
        st.session_state.workflow_completed = True
        st.session_state.paper_summary = summary_result['summary']
        st.session_state.markdown_content = summary_result['markdown_content']
        st.session_state.slice_images_dir = slice_output_dir  # 保存切片图像目录
        
        # 显示成功消息
        st.success("🎉 PDF分析工作流已完成！您现在可以开始提问了。")
        
        # 自动刷新页面显示聊天界面
        st.rerun()
        
    except Exception as e:
        logger.error(f"工作流执行失败: {str(e)}")
        st.error(f"工作流执行失败: {str(e)}")


def show_welcome_page():
    """显示欢迎页面"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        ## 🎯 功能特点
        
        ### 📋 完整工作流
        1. **边界框提取** - 智能识别文本、图像、表格、矢量图
        2. **布局分析** - 自动检测单栏/双栏/混合布局并切片
        3. **内容解析** - 将切片转换为结构化HTML
        4. **文档生成** - 转换为高质量Markdown文档
        5. **智能总结** - AI自动生成论文摘要
        
        ### 💬 智能问答
        - 基于论文内容的精准回答
        - 自动引用来源和页面位置
        - 支持多轮对话
        - 理解表格、公式、图像内容
        
        ### 🚀 开始使用
        1. 在左侧上传PDF文件
        2. 点击"开始分析"按钮
        3. 等待处理完成
        4. 开始与论文对话
        
        ---
        
        ### 📝 支持的内容类型
        - 📄 **文本段落** - 正文、标题、摘要等
        - 📊 **表格数据** - 实验结果、数据统计
        - 🖼️ **图像图表** - 图片、图表、示意图
        - 🔗 **矢量图形** - 复杂图形、流程图
        - 📐 **数学公式** - LaTeX公式、数学表达式
        """)


def show_chat_interface(logger: WorkflowLogger):
    """显示聊天界面"""
    st.header("📝 论文总结")
    
    # 显示论文总结
    with st.expander("查看完整总结", expanded=True):
        st.markdown(st.session_state.paper_summary)
    
    st.markdown("---")
    st.header("💬 论文问答")
    
    # 显示对话历史
    for chat in st.session_state.conversation_history:
        with st.chat_message("user"):
            st.write(chat["question"])
        with st.chat_message("assistant"):
            st.write(chat["answer"])
    
    # 用户输入
    if prompt := st.chat_input("请输入您的问题..."):
        # 显示用户问题
        with st.chat_message("user"):
            st.write(prompt)
        
        # 生成回答
        with st.chat_message("assistant"):
            with st.spinner("正在思考..."):
                workflow = st.session_state.workflow
                
                # 获取切片图像目录（支持视觉问答）
                slice_images_dir = st.session_state.slice_images_dir
                
                answer = workflow.answer_question(
                    question=prompt,
                    markdown_content=st.session_state.markdown_content,
                    conversation_history=st.session_state.conversation_history,
                    slice_images_dir=slice_images_dir
                )
            st.write(answer)
        
        # 保存对话历史
        st.session_state.conversation_history.append({
            "question": prompt,
            "answer": answer,
            "timestamp": datetime.now().isoformat()
        })
        
        # 限制历史记录长度
        if len(st.session_state.conversation_history) > 10:
            st.session_state.conversation_history = st.session_state.conversation_history[-10:]


def clear_session_data():
    """清除会话数据"""
    st.session_state.workflow = None
    st.session_state.workflow_completed = False
    st.session_state.paper_summary = None
    st.session_state.markdown_content = None
    st.session_state.conversation_history = []
    st.session_state.slice_images_dir = None
    st.success("✅ 数据已清除")
    st.rerun()


if __name__ == "__main__":
    main() 