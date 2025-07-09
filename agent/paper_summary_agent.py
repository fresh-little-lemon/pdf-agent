#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
论文总结Agent
负责使用AI模型对论文内容进行智能总结
"""

import os
import logging
from typing import Dict, Any
from utils.html_parser import inference_with_api_text_only


class PaperSummaryAgent:
    """论文总结智能代理"""
    
    def __init__(self, logger: logging.Logger = None):
        """
        初始化论文总结代理
        
        Args:
            logger: 日志记录器
        """
        self.logger = logger or logging.getLogger(__name__)
        self.model_id = "Qwen/Qwen2.5-14B-Instruct-1M"  # 使用更新的模型
        
    def summarize_paper(self, markdown_file: str) -> Dict[str, Any]:
        """
        使用AI模型总结论文内容
        
        Args:
            markdown_file: Markdown文件路径
            
        Returns:
            包含总结结果的字典
        """
        self.logger.info("=" * 60)
        self.logger.info("开始使用AI模型总结论文")
        self.logger.info("=" * 60)
        
        try:
            # 读取markdown内容
            with open(markdown_file, 'r', encoding='utf-8') as f:
                markdown_content = f.read()
            
            if not markdown_content.strip():
                error_msg = "Markdown文件内容为空"
                self.logger.error(error_msg)
                return {'status': 'error', 'message': error_msg}
            
            self.logger.info(f"读取Markdown文件成功，内容长度: {len(markdown_content)} 字符")
            
            # 准备总结提示词
            summary_prompt = self._create_summary_prompt(markdown_content)
            
            # 调用AI模型进行总结
            summary = inference_with_api_text_only(
                prompt=summary_prompt,
                sys_prompt=self._get_system_prompt(),
                model_id=self.model_id,
                max_retries=3,
                retry_delay=2.0
            )
            
            result = {
                'status': 'success',
                'message': '论文总结生成成功',
                'summary': summary,
                'markdown_content': markdown_content
            }
            
            self.logger.info(f"✅ 论文总结成功，总结长度: {len(summary)} 字符")
            return result
            
        except Exception as e:
            error_msg = f"论文总结过程中出错: {str(e)}"
            self.logger.error(error_msg)
            return {'status': 'error', 'message': error_msg}
    
    def _create_summary_prompt(self, markdown_content: str) -> str:
        """
        创建论文总结的提示词
        
        Args:
            markdown_content: Markdown内容
            
        Returns:
            格式化的提示词
        """
        # 截取内容长度，避免过长
        content_limit = 8000
        truncated_content = markdown_content[:content_limit]
        is_truncated = len(markdown_content) > content_limit
        
        prompt = f"""请对以下论文内容进行详细总结，包括：

1. **论文标题和作者**（如果有）
2. **研究背景和问题**
3. **主要方法和技术**
4. **核心贡献和创新点**
5. **实验结果和数据**
6. **结论和未来工作**

请用中文回答，保持学术严谨性。论文内容如下：

{truncated_content}

{"..." if is_truncated else ""}"""

        return prompt
    
    def _get_system_prompt(self) -> str:
        """
        获取系统提示词
        
        Returns:
            系统提示词
        """
        return "你是一个专业的学术论文分析专家，擅长理解和总结各领域的研究论文。请用中文提供准确、详细的论文总结。"
    
    def validate_markdown_content(self, markdown_file: str) -> Dict[str, Any]:
        """
        验证Markdown文件内容
        
        Args:
            markdown_file: Markdown文件路径
            
        Returns:
            验证结果
        """
        try:
            if not os.path.exists(markdown_file):
                return {
                    'valid': False,
                    'message': f'Markdown文件不存在: {markdown_file}'
                }
            
            with open(markdown_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                return {
                    'valid': False,
                    'message': 'Markdown文件内容为空'
                }
            
            return {
                'valid': True,
                'message': f'Markdown文件有效，内容长度: {len(content)} 字符',
                'content_length': len(content)
            }
            
        except Exception as e:
            return {
                'valid': False,
                'message': f'验证Markdown文件时出错: {str(e)}'
            } 