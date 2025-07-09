#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
论文问答Agent
包含智能路由功能，能够处理文本和视觉问题
"""

import os
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from utils.html_parser import inference_with_api_text_only, inference_with_api


class PaperQAAgent:
    """论文问答智能代理"""
    
    def __init__(self, logger: logging.Logger = None):
        """
        初始化论文问答代理
        
        Args:
            logger: 日志记录器
        """
        self.logger = logger or logging.getLogger(__name__)
        self.router_model_id = "Qwen/Qwen3-235B-A22B"  # 路由模型
        self.text_model_id = "Qwen/Qwen2.5-14B-Instruct-1M"  # 文本问答模型
        self.vision_model_id = "Qwen/Qwen2.5-VL-72B-Instruct"  # 视觉问答模型
        
    def answer_question(self, question: str, markdown_content: str, 
                       conversation_history: List[Dict] = None,
                       slice_images_dir: str = None) -> str:
        """
        智能回答用户问题
        
        Args:
            question: 用户问题
            markdown_content: 论文Markdown内容
            conversation_history: 对话历史
            slice_images_dir: 切片图像目录路径
            
        Returns:
            回答内容
        """
        try:
            self.logger.info(f"收到问题: {question[:100]}...")
            
            # 1. 路由判断：是否需要视觉功能
            needs_vision = self._route_question(question)
            self.logger.info(f"路由判断结果: {'需要视觉功能' if needs_vision else '纯文本回答'}")
            
            if needs_vision and slice_images_dir:
                # 2. 视觉问答流程
                return self._handle_vision_question(
                    question, markdown_content, slice_images_dir, conversation_history
                )
            else:
                # 3. 普通文本问答流程
                return self._handle_text_question(
                    question, markdown_content, conversation_history
                )
            
        except Exception as e:
            error_msg = f"问答过程中出错: {str(e)}"
            self.logger.error(error_msg)
            return f"抱歉，回答您的问题时出现了错误：{error_msg}"
    
    def _route_question(self, question: str) -> bool:
        """
        使用路由模型判断问题是否需要视觉功能
        
        Args:
            question: 用户问题
            
        Returns:
            是否需要视觉功能
        """
        try:
            route_prompt = f"""请判断以下用户问题是否需要查看图片、图表、图像等视觉内容才能回答。

用户问题：{question}

请回答"是"或"否"，并简要说明理由。

判断标准：
- 如果问题涉及"图片"、"图像"、"图表"、"示意图"、"截图"等视觉元素，回答"是"
- 如果问题询问"第几张图"、"图中显示"、"图表中的数据"等，回答"是"  
- 如果问题只涉及文字内容、概念解释、数据分析等，回答"否"

请直接回答"是"或"否"："""

            response = inference_with_api_text_only(
                prompt=route_prompt,
                sys_prompt="你是一个专业的问题路由系统，能够准确判断问题是否需要视觉功能。",
                model_id=self.router_model_id,
                max_retries=3,
                retry_delay=1.0
            )
            
            # 解析路由结果
            needs_vision = "是" in response.strip()[:5]  # 检查开头是否包含"是"
            
            self.logger.info(f"路由模型回答: {response.strip()}")
            return needs_vision
            
        except Exception as e:
            self.logger.warning(f"路由判断失败，默认使用文本模式: {str(e)}")
            return False
    
    def _handle_vision_question(self, question: str, markdown_content: str, 
                               slice_images_dir: str, conversation_history: List[Dict] = None) -> str:
        """
        处理需要视觉功能的问题
        
        Args:
            question: 用户问题
            markdown_content: 论文内容
            slice_images_dir: 切片图像目录
            conversation_history: 对话历史
            
        Returns:
            回答内容
        """
        try:
            # 1. 从markdown中提取图片信息
            image_refs = self._extract_image_references(markdown_content)
            
            # 2. 获取可用的图片文件
            available_images = self._get_available_images(slice_images_dir)
            
            if not available_images:
                return "抱歉，没有找到可用的图片文件来回答您的视觉相关问题。"
            
            # 3. 选择最相关的图片
            selected_images = self._select_relevant_images(
                question, image_refs, available_images
            )
            
            if not selected_images:
                # 如果没有找到特定图片，使用所有可用图片
                selected_images = available_images[:3]  # 限制最多3张图片
            
            # 4. 为每张选中的图片生成回答
            answers = []
            for img_path in selected_images:
                try:
                    img_answer = self._query_single_image(question, img_path, markdown_content)
                    if img_answer.strip():
                        img_name = os.path.basename(img_path)
                        answers.append(f"**{img_name}**: {img_answer}")
                except Exception as e:
                    self.logger.warning(f"处理图片 {img_path} 时出错: {str(e)}")
                    continue
            
            if answers:
                final_answer = "基于论文中的图片内容，我为您分析如下：\n\n" + "\n\n".join(answers)
            else:
                # 如果视觉分析失败，降级为文本回答
                self.logger.warning("视觉分析失败，降级为文本回答")
                final_answer = self._handle_text_question(question, markdown_content, conversation_history)
                final_answer = "抱歉，无法直接分析图片内容，基于文本内容为您回答：\n\n" + final_answer
            
            return final_answer
            
        except Exception as e:
            self.logger.error(f"视觉问答处理失败: {str(e)}")
            # 降级为文本回答
            return self._handle_text_question(question, markdown_content, conversation_history)
    
    def _handle_text_question(self, question: str, markdown_content: str, 
                             conversation_history: List[Dict] = None) -> str:
        """
        处理纯文本问题
        
        Args:
            question: 用户问题
            markdown_content: 论文内容
            conversation_history: 对话历史
            
        Returns:
            回答内容
        """
        try:
            # 构建对话历史
            history_text = ""
            if conversation_history:
                for item in conversation_history[-3:]:  # 只保留最近3轮对话
                    history_text += f"Q: {item['question']}\nA: {item['answer']}\n\n"
            
            # 准备问答提示词
            qa_prompt = self._create_text_qa_prompt(question, markdown_content, history_text)
            
            answer = inference_with_api_text_only(
                prompt=qa_prompt,
                sys_prompt=self._get_text_qa_system_prompt(),
                model_id=self.text_model_id,
                max_retries=3,
                retry_delay=1.0
            )
            
            self.logger.info(f"✅ 文本问答成功")
            return answer
            
        except Exception as e:
            error_msg = f"文本问答处理失败: {str(e)}"
            self.logger.error(error_msg)
            return f"抱歉，处理您的问题时出现了错误：{error_msg}"
    
    def _query_single_image(self, question: str, image_path: str, context: str) -> str:
        """
        查询单张图片
        
        Args:
            question: 用户问题
            image_path: 图片路径
            context: 上下文信息
            
        Returns:
            图片分析结果
        """
        try:
            vision_prompt = f"""请仔细分析这张图片，并根据用户问题回答。

用户问题：{question}

请结合图片内容和以下论文上下文信息进行分析：

上下文（前200字符）：
{context[:200]}...

请详细描述图片中的内容，并针对用户问题给出准确的回答。用中文回答。"""

            answer = inference_with_api(
                image_path=image_path,
                prompt=vision_prompt,
                sys_prompt="你是一个专业的学术图像分析专家，能够准确理解和分析学术论文中的图片、图表、示意图等视觉内容。",
                model_id=self.vision_model_id,
                max_retries=2,
                retry_delay=1.0
            )
            
            return answer
            
        except Exception as e:
            self.logger.warning(f"分析图片 {image_path} 失败: {str(e)}")
            return ""
    
    def _extract_image_references(self, markdown_content: str) -> List[Dict[str, Any]]:
        """
        从Markdown内容中提取图片引用信息
        
        Args:
            markdown_content: Markdown内容
            
        Returns:
            图片引用信息列表
        """
        image_refs = []
        
        # 匹配markdown图片语法：![alt](path)
        img_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        matches = re.findall(img_pattern, markdown_content)
        
        for alt_text, img_path in matches:
            image_refs.append({
                'alt_text': alt_text,
                'path': img_path,
                'type': 'markdown'
            })
        
        # 匹配HTML img标签
        html_img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
        html_matches = re.findall(html_img_pattern, markdown_content)
        
        for img_path in html_matches:
            image_refs.append({
                'alt_text': '',
                'path': img_path,
                'type': 'html'
            })
        
        return image_refs
    
    def _get_available_images(self, slice_images_dir: str) -> List[str]:
        """
        获取可用的图片文件
        
        Args:
            slice_images_dir: 切片图像目录
            
        Returns:
            图片文件路径列表
        """
        if not slice_images_dir or not os.path.exists(slice_images_dir):
            return []
        
        available_images = []
        for file in sorted(os.listdir(slice_images_dir)):
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                full_path = os.path.join(slice_images_dir, file)
                available_images.append(full_path)
        
        return available_images
    
    def _select_relevant_images(self, question: str, image_refs: List[Dict], 
                               available_images: List[str]) -> List[str]:
        """
        根据问题选择相关的图片
        
        Args:
            question: 用户问题
            image_refs: 图片引用信息
            available_images: 可用图片列表
            
        Returns:
            选中的图片路径列表
        """
        selected_images = []
        
        # 检查问题中是否包含序数词
        number_patterns = [
            r'第([一二三四五六七八九十\d]+)[张个幅]?图',
            r'图([一二三四五六七八九十\d]+)',
            r'第([一二三四五六七八九十\d]+)[张个幅]?表',
            r'表([一二三四五六七八九十\d]+)'
        ]
        
        for pattern in number_patterns:
            matches = re.findall(pattern, question)
            for match in matches:
                # 转换中文数字为阿拉伯数字
                num = self._chinese_to_arabic(match)
                if num and num <= len(available_images):
                    img_path = available_images[num - 1]  # 索引从0开始
                    if img_path not in selected_images:
                        selected_images.append(img_path)
        
        # 如果没有找到特定编号，检查关键词
        if not selected_images:
            keywords = ['图', '表', '图片', '图像', '图表', '示意图', '流程图']
            if any(keyword in question for keyword in keywords):
                # 返回前几张图片作为候选
                selected_images = available_images[:2]
        
        return selected_images
    
    def _chinese_to_arabic(self, chinese_num: str) -> Optional[int]:
        """
        将中文数字转换为阿拉伯数字
        
        Args:
            chinese_num: 中文数字字符串
            
        Returns:
            阿拉伯数字
        """
        chinese_dict = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
        }
        
        # 如果已经是阿拉伯数字
        if chinese_num.isdigit():
            return int(chinese_num)
        
        # 简单的中文数字转换
        if chinese_num in chinese_dict:
            return chinese_dict[chinese_num]
        
        return None
    
    def _create_text_qa_prompt(self, question: str, markdown_content: str, history_text: str) -> str:
        """
        创建文本问答提示词
        
        Args:
            question: 用户问题
            markdown_content: 论文内容
            history_text: 对话历史
            
        Returns:
            格式化的提示词
        """
        content_limit = 6000
        truncated_content = markdown_content[:content_limit]
        is_truncated = len(markdown_content) > content_limit
        
        prompt = f"""基于以下论文内容回答用户的问题。请按照以下要求：

1. 根据论文内容准确回答问题
2. 如果引用了论文中的特定内容，请明确标注来源（如第几页、哪个部分等）
3. 如果论文中没有相关信息，请明确说明
4. 保持回答的学术性和准确性
5. 用中文回答

论文内容：
{truncated_content}

{"..." if is_truncated else ""}

{f"对话历史：{history_text}" if history_text else ""}

用户问题：{question}

请根据论文内容回答："""

        return prompt
    
    def _get_text_qa_system_prompt(self) -> str:
        """
        获取文本问答的系统提示词
        
        Returns:
            系统提示词
        """
        return "你是一个专业的学术论文分析助手，能够基于论文内容准确回答用户的问题，并提供引用来源。" 