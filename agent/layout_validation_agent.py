#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import random
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
import time

from utils.html_parser import inference_with_api


class LayoutValidationAgent:
    """布局验证智能体，用于检测和修正HTML元素的排列顺序"""
    
    def __init__(self, max_workers: int = 10):
        """
        初始化布局验证智能体
        
        Args:
            max_workers: 最大工作线程数
        """
        self.max_workers = max_workers
        
    def detect_double_column_layout(self, image_paths: List[str]) -> bool:
        """
        检测论文是否为双栏布局
        
        Args:
            image_paths: 图片文件路径列表
            
        Returns:
            是否为双栏布局
        """
        try:
            if not image_paths:
                print("❌ 没有找到图片文件")
                return False
            
            # 随机选择一张图片
            random_image = random.choice(image_paths)
            print(f"🎯 随机选择图片进行布局检测: {os.path.basename(random_image)}")
            
            # 构建检测提示词
            detection_prompt = "这篇论文是否为双栏布局，回答是否"
            
            # 调用API检测
            print("🔍 正在检测论文布局...")
            response = inference_with_api(random_image, detection_prompt)
            
            if not response:
                print("❌ API调用失败，无法检测布局")
                return False
            
            print(f"📝 模型回答: {response}")
            
            # 使用正则表达式匹配"是"或"否"
            is_match = re.search(r'是', response)
            no_match = re.search(r'否', response)
            
            if is_match and not no_match:
                print("✅ 检测到双栏布局")
                return True
            elif no_match and not is_match:
                print("ℹ️ 检测到单栏布局")
                return False
            else:
                print("⚠️ 布局检测结果不明确，默认为单栏")
                return False
                
        except Exception as e:
            print(f"❌ 布局检测过程中出现错误: {str(e)}")
            return False
    
    def reorder_html_elements(self, image_path: str, html_path: str) -> Optional[str]:
        """
        重新排序HTML元素
        
        Args:
            image_path: 对应的图片路径
            html_path: HTML文件路径
            
        Returns:
            重新排序后的HTML内容，失败返回None
        """
        try:
            # 读取原始HTML内容
            with open(html_path, 'r', encoding='utf-8') as f:
                original_html = f.read()
            
            # 构建重排序提示词
            reorder_prompt = (
                "请根据论文的排版顺序对下面的html的元素块进行整理，"
                "使用order字段标注元素块实际在文章中的位置，"
                "不必复述文章的内容，但需要修改html元素添加order字段，"
                "该操作对每个元素块都要执行，"
                "阅读顺序满足从上到下，从左到右，特别注意双栏的论文。"
                f"\n\n原始HTML内容:\n{original_html}"
            )
            
            print(f"🔄 正在重新排序: {os.path.basename(html_path)}")
            
            # 调用API重新排序
            response = inference_with_api(image_path, reorder_prompt, model_id="Qwen/Qwen2.5-VL-32B-Instruct")
            
            if not response:
                print(f"❌ 重排序失败: {os.path.basename(html_path)}")
                return None
            
            # 使用正则表达式提取HTML内容
            html_match = re.search(r'```html\s*\n(.*?)\n```', response, re.DOTALL)
            if html_match:
                reordered_html = html_match.group(1).strip()
                print(f"✅ 重排序完成: {os.path.basename(html_path)}")
                return reordered_html
            else:
                print(f"⚠️ 未找到HTML内容: {os.path.basename(html_path)}")
                return None
                
        except Exception as e:
            print(f"❌ 重排序过程中出现错误: {str(e)}")
            return None
    
    def extract_order_fields(self, reordered_html: str) -> Dict[str, str]:
        """
        从重排序后的HTML中提取order字段
        
        Args:
            reordered_html: 重排序后的HTML内容
            
        Returns:
            元素标识符到order值的映射
        """
        try:
            soup = BeautifulSoup(reordered_html, 'html.parser')
            order_map = {}
            
            # 查找所有带有order属性的元素
            elements_with_order = soup.find_all(attrs={'order': True})
            
            for element in elements_with_order:
                # 构建元素标识符（使用data-bbox或其他唯一属性）
                bbox = element.get('data-bbox', '')
                tag_name = element.name
                text_content = element.get_text().strip()[:50]  # 前50个字符作为标识
                
                # 创建唯一标识符
                if bbox:
                    identifier = f"{tag_name}[data-bbox='{bbox}']"
                else:
                    identifier = f"{tag_name}[text='{text_content}']"
                
                order_value = element.get('order', '')
                if order_value:
                    order_map[identifier] = order_value
            
            print(f"📊 提取到 {len(order_map)} 个order字段")
            return order_map
            
        except Exception as e:
            print(f"❌ 提取order字段时出现错误: {str(e)}")
            return {}
    
    def apply_order_to_original(self, original_html_path: str, order_map: Dict[str, str]) -> str:
        """
        将order字段应用到原始HTML文件中
        
        Args:
            original_html_path: 原始HTML文件路径
            order_map: order字段映射
            
        Returns:
            更新后的HTML内容
        """
        try:
            # 读取原始HTML
            with open(original_html_path, 'r', encoding='utf-8') as f:
                original_html = f.read()
            
            soup = BeautifulSoup(original_html, 'html.parser')
            applied_count = 0
            
            # 应用order字段
            for identifier, order_value in order_map.items():
                # 解析标识符
                if '[data-bbox=' in identifier:
                    # 基于bbox匹配
                    bbox_match = re.search(r"data-bbox='([^']*)'", identifier)
                    tag_match = re.search(r"^(\w+)\[", identifier)
                    
                    if bbox_match and tag_match:
                        tag_name = tag_match.group(1)
                        bbox_value = bbox_match.group(1)
                        
                        # 查找匹配的元素
                        element = soup.find(tag_name, {'data-bbox': bbox_value})
                        if element:
                            element['order'] = order_value
                            applied_count += 1
                
                elif '[text=' in identifier:
                    # 基于文本内容匹配
                    text_match = re.search(r"text='([^']*)'", identifier)
                    tag_match = re.search(r"^(\w+)\[", identifier)
                    
                    if text_match and tag_match:
                        tag_name = tag_match.group(1)
                        text_content = text_match.group(1)
                        
                        # 查找匹配的元素
                        elements = soup.find_all(tag_name)
                        for element in elements:
                            if element.get_text().strip().startswith(text_content):
                                element['order'] = order_value
                                applied_count += 1
                                break
            
            print(f"✅ 成功应用 {applied_count} 个order字段")
            return str(soup)
            
        except Exception as e:
            print(f"❌ 应用order字段时出现错误: {str(e)}")
            return ""
    
    def process_single_page(self, args: Tuple[str, str, str]) -> bool:
        """
        处理单个页面的重排序
        
        Args:
            args: (image_path, html_path, tmp_dir) 的元组
            
        Returns:
            处理是否成功
        """
        image_path, html_path, tmp_dir = args
        
        try:
            # 重新排序HTML元素
            reordered_html = self.reorder_html_elements(image_path, html_path)
            if not reordered_html:
                return False
            
            # 保存重排序结果到临时目录
            html_filename = os.path.basename(html_path)
            tmp_html_path = os.path.join(tmp_dir, html_filename)
            
            with open(tmp_html_path, 'w', encoding='utf-8') as f:
                f.write(reordered_html)
            
            # 提取order字段
            order_map = self.extract_order_fields(reordered_html)
            if not order_map:
                print(f"⚠️ 未提取到order字段: {html_filename}")
                return False
            
            # 应用order字段到原始HTML
            updated_html = self.apply_order_to_original(html_path, order_map)
            if not updated_html:
                return False
            
            # 保存结果
            with open(tmp_html_path, 'w', encoding='utf-8') as f:
                f.write(updated_html)
            
            return True
            
        except Exception as e:
            print(f"❌ 处理页面时出现错误: {str(e)}")
            return False
    
    def validate_and_reorder_layout(self, pdf_filename: str, output_dir: str = "tmp") -> Dict[str, Any]:
        """
        验证并重新排序布局
        
        Args:
            pdf_filename: PDF文件名（不含扩展名）
            output_dir: 输出目录
            
        Returns:
            处理结果字典
        """
        try:
            # 构建路径
            html_dir = os.path.join(output_dir, f"{pdf_filename}_html")
            image_dir = os.path.join(output_dir, f"{pdf_filename}_converted_to_img")
            
            # 检查目录是否存在
            if not os.path.exists(html_dir):
                return {
                    'status': 'error',
                    'message': f'HTML目录不存在: {html_dir}',
                    'is_double_column': False,
                    'processed_files': []
                }
            
            if not os.path.exists(image_dir):
                return {
                    'status': 'error',
                    'message': f'图片目录不存在: {image_dir}',
                    'is_double_column': False,
                    'processed_files': []
                }
            
            # 获取所有HTML和图片文件
            html_files = [f for f in os.listdir(html_dir) if f.endswith('.html') and f.startswith('page_')]
            image_files = [f for f in os.listdir(image_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            
            if not html_files or not image_files:
                return {
                    'status': 'error',
                    'message': '未找到HTML文件或图片文件',
                    'is_double_column': False,
                    'processed_files': []
                }
            
            # 构建完整路径
            image_paths = [os.path.join(image_dir, f) for f in image_files]
            
            print(f"📁 找到 {len(html_files)} 个HTML文件和 {len(image_files)} 个图片文件")
            
            # 步骤1：检测双栏布局
            is_double_column = self.detect_double_column_layout(image_paths)
            
            if not is_double_column:
                return {
                    'status': 'success',
                    'message': '检测到单栏布局，无需重排序',
                    'is_double_column': False,
                    'processed_files': []
                }
            
            # 步骤2：创建临时目录和备份目录
            tmp_html_dir = os.path.join(html_dir, 'tmp')
            origin_html_dir = os.path.join(html_dir, 'origin')
            
            os.makedirs(tmp_html_dir, exist_ok=True)
            os.makedirs(origin_html_dir, exist_ok=True)
            
            # 步骤3：准备处理任务
            tasks = []
            for html_file in sorted(html_files):
                html_path = os.path.join(html_dir, html_file)
                
                # 查找对应的图片文件
                page_match = re.search(r'page_(\d+)', html_file)
                if page_match:
                    page_num = page_match.group(1)
                    # 查找匹配的图片
                    image_path = None
                    for img_file in image_files:
                        if f"page_{page_num}" in img_file or f"page{page_num}" in img_file:
                            image_path = os.path.join(image_dir, img_file)
                            break
                    
                    if image_path and os.path.exists(image_path):
                        tasks.append((image_path, html_path, tmp_html_dir))
            
            if not tasks:
                return {
                    'status': 'error',
                    'message': '无法匹配HTML文件和图片文件',
                    'is_double_column': True,
                    'processed_files': []
                }
            
            print(f"🚀 开始使用 {self.max_workers} 个线程处理 {len(tasks)} 个页面")
            
            # 步骤4：多线程处理
            processed_files = []
            failed_files = []
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交任务
                future_to_task = {executor.submit(self.process_single_page, task): task for task in tasks}
                
                # 收集结果
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    image_path, html_path, _ = task
                    html_filename = os.path.basename(html_path)
                    
                    try:
                        success = future.result()
                        if success:
                            processed_files.append(html_filename)
                        else:
                            failed_files.append(html_filename)
                    except Exception as e:
                        print(f"❌ 处理失败: {html_filename} - {str(e)}")
                        failed_files.append(html_filename)
            
            # 步骤5：移动文件
            if processed_files:
                print("📦 正在备份原始文件并应用新版本...")
                
                for html_file in processed_files:
                    original_path = os.path.join(html_dir, html_file)
                    backup_path = os.path.join(origin_html_dir, html_file)
                    tmp_path = os.path.join(tmp_html_dir, html_file)
                    
                    # 备份原始文件
                    if os.path.exists(original_path):
                        shutil.move(original_path, backup_path)
                    
                    # 移动新文件到原位置
                    if os.path.exists(tmp_path):
                        shutil.move(tmp_path, original_path)
            
            # 清理临时目录
            if os.path.exists(tmp_html_dir):
                shutil.rmtree(tmp_html_dir)
            
            result = {
                'status': 'success',
                'message': f'成功处理 {len(processed_files)} 个文件',
                'is_double_column': True,
                'processed_files': processed_files,
                'failed_files': failed_files,
                'total_files': len(tasks)
            }
            
            if failed_files:
                result['message'] += f'，{len(failed_files)} 个文件处理失败'
            
            return result
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'布局验证过程中出现错误: {str(e)}',
                'is_double_column': False,
                'processed_files': []
            }


def create_layout_validation_agent(max_workers: int = 10) -> LayoutValidationAgent:
    """
    创建布局验证智能体实例
    
    Args:
        max_workers: 最大工作线程数
        
    Returns:
        布局验证智能体实例
    """
    return LayoutValidationAgent(max_workers=max_workers)


if __name__ == "__main__":
    # 测试代码
    agent = create_layout_validation_agent(max_workers=5)
    
    # 示例：验证v9论文的布局
    result = agent.validate_and_reorder_layout("v9", "tmp")
    
    print("\n📊 处理结果:")
    print(f"状态: {result['status']}")
    print(f"消息: {result['message']}")
    print(f"是否双栏: {result['is_double_column']}")
    
    if result['status'] == 'success' and result.get('processed_files'):
        print(f"处理成功的文件: {result['processed_files']}")
        if result.get('failed_files'):
            print(f"处理失败的文件: {result['failed_files']}") 