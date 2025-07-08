#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import fitz  # PyMuPDF
import json
import math
import time
from typing import Dict, List, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import threading


class PDFBboxExtractor:
    """PDF边框提取器，用于提取和可视化文本块、图像和表格边框"""
    
    def __init__(self, max_workers: int = 10):
        """
        初始化PDF边框提取器
        
        Args:
            max_workers: 最大工作线程数，默认10个
        """
        self.colors = {
            'text': (0, 1, 0),      # 绿色 - 文本块
            'image': (1, 0, 0),     # 红色 - 图像
            'table': (0, 0, 1),     # 蓝色 - 表格
        }
        self.line_width = 1.0
        self.max_workers = max_workers
        self._print_lock = Lock()  # 用于线程安全的打印
    
    def _thread_safe_print(self, message: str):
        """线程安全的打印函数"""
        with self._print_lock:
            print(message)
    
    def _boxes_overlap(self, box1: List[float], box2: List[float], overlap_threshold: float = 0.3) -> bool:
        """
        检查两个边界框是否重叠
        
        Args:
            box1: 第一个边界框 [x1, y1, x2, y2]
            box2: 第二个边界框 [x1, y1, x2, y2]
            overlap_threshold: 重叠阈值（面积重叠比例）
            
        Returns:
            是否重叠
        """
        # 计算交集
        x1_inter = max(box1[0], box2[0])
        y1_inter = max(box1[1], box2[1])
        x2_inter = min(box1[2], box2[2])
        y2_inter = min(box1[3], box2[3])
        
        # 如果没有交集
        if x1_inter >= x2_inter or y1_inter >= y2_inter:
            return False
        
        # 计算交集面积
        inter_area = (x2_inter - x1_inter) * (y2_inter - y1_inter)
        
        # 计算两个框的面积
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        
        # 计算较小框的重叠比例
        smaller_area = min(area1, area2)
        overlap_ratio = inter_area / smaller_area if smaller_area > 0 else 0
        
        return overlap_ratio > overlap_threshold
    
    def _remove_overlapping_text_blocks(self, text_blocks: List[Dict[str, Any]], 
                                       table_boxes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        移除与表格重叠的文字块
        
        Args:
            text_blocks: 文字块列表
            table_boxes: 表格边界框列表
            
        Returns:
            过滤后的文字块列表
        """
        if not table_boxes:
            return text_blocks
        
        filtered_text_blocks = []
        removed_count = 0
        
        for text_block in text_blocks:
            text_bbox = text_block['bbox']
            is_overlapping = False
            
            # 检查是否与任何表格重叠
            for table_box in table_boxes:
                table_bbox = table_box['bbox']
                if self._boxes_overlap(text_bbox, table_bbox):
                    is_overlapping = True
                    removed_count += 1
                    break
            
            if not is_overlapping:
                filtered_text_blocks.append(text_block)
        
        if removed_count > 0:
            self._thread_safe_print(f"  移除了 {removed_count} 个与表格重叠的文字块")
        
        return filtered_text_blocks
    
    def _remove_overlapping_tables(self, tables: List[Dict[str, Any]], 
                                  images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        移除与图像重叠的表格预测框，以图像为准
        
        Args:
            tables: 表格预测框列表
            images: 图像边界框列表
            
        Returns:
            过滤后的表格列表
        """
        if not images or not tables:
            return tables
        
        filtered_tables = []
        removed_count = 0
        
        for table in tables:
            table_bbox = table['bbox']
            is_overlapping = False
            
            # 检查是否与任何图像重叠
            for image in images:
                image_bbox = image['bbox']
                if self._boxes_overlap(table_bbox, image_bbox, overlap_threshold=0.3):
                    is_overlapping = True
                    removed_count += 1
                    self._thread_safe_print(f"    🖼️ 表格 {table.get('index', 0)+1} 与图像 {image.get('index', 0)} 重叠，移除表格预测框")
                    break
            
            if not is_overlapping:
                filtered_tables.append(table)
        
        if removed_count > 0:
            self._thread_safe_print(f"  移除了 {removed_count} 个与图像重叠的表格预测框")
        
        return filtered_tables
    
    def _remove_duplicate_images(self, images: List[Dict[str, Any]], overlap_threshold: float = 0.8) -> List[Dict[str, Any]]:
        """
        去除重叠的图像边框
        
        Args:
            images: 图像列表
            overlap_threshold: 重叠阈值（面积重叠比例）
            
        Returns:
            去重后的图像列表
        """
        if len(images) <= 1:
            return images
        
        # 按面积排序，保留较大的图像
        sorted_images = sorted(images, key=lambda x: (x['bbox'][2] - x['bbox'][0]) * (x['bbox'][3] - x['bbox'][1]), reverse=True)
        
        unique_images = []
        removed_count = 0
        
        for current_image in sorted_images:
            is_duplicate = False
            current_bbox = current_image['bbox']
            
            # 检查是否与已保留的图像重叠
            for existing_image in unique_images:
                existing_bbox = existing_image['bbox']
                if self._boxes_overlap(current_bbox, existing_bbox, overlap_threshold):
                    is_duplicate = True
                    removed_count += 1
                    break
            
            if not is_duplicate:
                unique_images.append(current_image)
        
        # 重新分配索引
        for i, image in enumerate(unique_images):
            image['index'] = i
        
        if removed_count > 0:
            self._thread_safe_print(f"  去除了 {removed_count} 个重复的图像边框")
        
        return unique_images
    
    def _extract_page_lines(self, page: fitz.Page) -> List[Dict[str, Any]]:
        """
        提取页面中的线条和矩形边框
        
        Args:
            page: PyMuPDF页面对象
            
        Returns:
            线条信息列表
        """
        lines = []
        
        try:
            # 获取页面的绘图命令
            drawings = page.get_drawings()
            
            for drawing in drawings:
                for item in drawing.get("items", []):
                    # 检查是否是线条或矩形
                    if item[0] == "l":  # 线条
                        x1, y1 = item[1]
                        x2, y2 = item[2]
                        lines.append({
                            'type': 'line',
                            'start': [x1, y1],
                            'end': [x2, y2],
                            'bbox': [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]
                        })
                    elif item[0] == "re":  # 矩形
                        rect = item[1]
                        lines.append({
                            'type': 'rect',
                            'bbox': [rect.x0, rect.y0, rect.x1, rect.y1]
                        })
            
            return lines
            
        except Exception as e:
            self._thread_safe_print(f"  ⚠️ 提取页面线条时出错: {str(e)}")
            return []
    
    def _find_nearest_table_borders(self, predicted_bbox: List[float], page_lines: List[Dict[str, Any]], 
                                   tolerance: float = 30.0) -> Optional[List[float]]:
        """
        根据预测框查找最近的表格边框线条，并修正坐标
        
        Args:
            predicted_bbox: Qwen预测的表格边框 [x1, y1, x2, y2]
            page_lines: 页面中的线条列表
            tolerance: 容忍距离（像素）
            
        Returns:
            修正后的边框坐标，如果未找到则返回None
        """
        if not page_lines:
            return None
        
        # 预测框的四个边
        pred_left, pred_top, pred_right, pred_bottom = predicted_bbox
        pred_height = pred_bottom - pred_top
        pred_width = pred_right - pred_left
        
        # 检查是否为小高度表格（需要特殊处理）
        is_small_height_table = pred_height < 50.0
        
        # 存储候选边框线及其距离
        candidates = {
            'left': [],    # [(x_pos, distance, y_range)]
            'right': [],   # [(x_pos, distance, y_range)]
            'top': [],     # [(y_pos, distance, x_range)]
            'bottom': []   # [(y_pos, distance, x_range)]
        }
        
        if is_small_height_table:
            self._thread_safe_print(f"    🔍 检测到小高度表格 (高度: {pred_height:.1f}px)，使用优化策略")
        
        # 遍历所有线条，找出在容忍度范围内的候选线条
        for line in page_lines:
            line_bbox = line['bbox']
            
            if line['type'] == 'line':
                start_x, start_y = line['start']
                end_x, end_y = line['end']
                
                # 垂直线条（可能是左右边框）
                if abs(start_x - end_x) <= 2:  # 垂直线
                    x_pos = (start_x + end_x) / 2
                    y_range = [min(start_y, end_y), max(start_y, end_y)]
                    
                    # 检查是否与预测框的垂直范围有足够重叠
                    overlap_top = max(y_range[0], pred_top - tolerance)
                    overlap_bottom = min(y_range[1], pred_bottom + tolerance)
                    overlap_height = overlap_bottom - overlap_top
                    
                    if overlap_height > 0:
                        # 计算与左边框的距离
                        left_distance = abs(x_pos - pred_left)
                        if left_distance <= tolerance:
                            candidates['left'].append((x_pos, left_distance, y_range))
                        
                        # 计算与右边框的距离
                        right_distance = abs(x_pos - pred_right)
                        if right_distance <= tolerance:
                            candidates['right'].append((x_pos, right_distance, y_range))
                
                # 水平线条（可能是上下边框）
                elif abs(start_y - end_y) <= 2:  # 水平线
                    y_pos = (start_y + end_y) / 2
                    x_range = [min(start_x, end_x), max(start_x, end_x)]
                    
                    # 检查是否与预测框的水平范围有足够重叠
                    overlap_left = max(x_range[0], pred_left - tolerance)
                    overlap_right = min(x_range[1], pred_right + tolerance)
                    overlap_width = overlap_right - overlap_left
                    
                    if overlap_width > 0:
                        # 计算与上边框的距离
                        top_distance = abs(y_pos - pred_top)
                        if top_distance <= tolerance:
                            candidates['top'].append((y_pos, top_distance, x_range))
                        
                        # 计算与下边框的距离
                        bottom_distance = abs(y_pos - pred_bottom)
                        if bottom_distance <= tolerance:
                            candidates['bottom'].append((y_pos, bottom_distance, x_range))
            
            elif line['type'] == 'rect':
                # 矩形边框 - 检查是否完全匹配
                rect_x1, rect_y1, rect_x2, rect_y2 = line_bbox
                
                if (abs(pred_left - rect_x1) <= tolerance and abs(pred_top - rect_y1) <= tolerance and
                    abs(pred_right - rect_x2) <= tolerance and abs(pred_bottom - rect_y2) <= tolerance):
                    self._thread_safe_print(f"    📐 找到完整匹配的矩形边框")
                    return [rect_x1, rect_y1, rect_x2, rect_y2]
        
        # 从候选线条中选择最近的边框，并验证修正幅度
        refined_coords = [pred_left, pred_top, pred_right, pred_bottom]
        found_borders = {'left': False, 'top': False, 'right': False, 'bottom': False}
        refinement_details = []
        max_correction_threshold = 30.0  # 最大修正幅度阈值（像素）
        
        # 小高度表格的特殊处理逻辑
        if is_small_height_table:
            # 1. 优先处理上边框
            if candidates['top']:
                candidates['top'].sort(key=lambda x: x[1])
                best_top = candidates['top'][0]
                
                # 验证上边框修正幅度
                top_correction = abs(best_top[0] - pred_top)
                if top_correction <= max_correction_threshold:
                    refined_coords[1] = best_top[0]  # y坐标
                    found_borders['top'] = True
                    refinement_details.append(f"上边框(优先): {pred_top:.1f} → {best_top[0]:.1f} (距离: {best_top[1]:.1f})")
                else:
                    self._thread_safe_print(f"      ⚠️ 上边框修正幅度过大({top_correction:.1f}px > {max_correction_threshold}px)，跳过修正")
                
                # 2. 基于上边框位置和原始高度计算下边框目标位置
                if found_borders['top']:
                    target_bottom = refined_coords[1] + pred_height
                    self._thread_safe_print(f"      基于上边框和原始高度计算下边框目标位置: {target_bottom:.1f}")
                    
                    # 3. 重新搜索下边框，使用更小的容忍度在目标位置附近查找
                    adjusted_bottom_candidates = []
                    small_tolerance = min(tolerance * 0.85, 25.0)  # 使用更小的容忍度
                    
                    for line in page_lines:
                        if line['type'] == 'line':
                            start_x, start_y = line['start']
                            end_x, end_y = line['end']
                            
                            # 水平线条（可能是下边框）
                            if abs(start_y - end_y) <= 2:  # 水平线
                                y_pos = (start_y + end_y) / 2
                                x_range = [min(start_x, end_x), max(start_x, end_x)]
                                
                                # 检查是否与预测框的水平范围有重叠，且在目标下边框位置附近
                                overlap_left = max(x_range[0], pred_left - tolerance)
                                overlap_right = min(x_range[1], pred_right + tolerance)
                                overlap_width = overlap_right - overlap_left
                                
                                if overlap_width > 0:
                                    # 计算与目标下边框的距离
                                    bottom_distance = abs(y_pos - target_bottom)
                                    if bottom_distance <= small_tolerance:
                                        adjusted_bottom_candidates.append((y_pos, bottom_distance, x_range))
                    
                    # 从调整后的候选中选择最近的下边框
                    if adjusted_bottom_candidates:
                        adjusted_bottom_candidates.sort(key=lambda x: x[1])
                        best_bottom = adjusted_bottom_candidates[0]
                        
                        # 验证下边框修正幅度
                        bottom_correction = abs(best_bottom[0] - target_bottom)
                        if bottom_correction <= max_correction_threshold:
                            refined_coords[3] = best_bottom[0]  # y坐标
                            found_borders['bottom'] = True
                            refinement_details.append(f"下边框(平移搜索): {pred_bottom:.1f} → {target_bottom:.1f} → {best_bottom[0]:.1f} (距离: {best_bottom[1]:.1f})")
                        else:
                            # 如果修正幅度过大，使用计算位置
                            refined_coords[3] = target_bottom
                            found_borders['bottom'] = True
                            refinement_details.append(f"下边框(保持计算): {pred_bottom:.1f} → {target_bottom:.1f} (修正幅度过大: {bottom_correction:.1f}px)")
                    else:
                        # 如果找不到合适的下边框，使用原始计算位置
                        refined_coords[3] = target_bottom
                        found_borders['bottom'] = True  # 标记为已处理，虽然是计算得出的
                        refinement_details.append(f"下边框(保持计算): {pred_bottom:.1f} → {target_bottom:.1f} (基于上边框+原始高度)")
            
            else:
                # 如果没有找到上边框，回退到标准处理
                self._thread_safe_print(f"      未找到上边框，回退到标准处理模式")
                # 处理上边框
                if candidates['top']:
                    candidates['top'].sort(key=lambda x: x[1])
                    best_top = candidates['top'][0]
                    
                    # 验证上边框修正幅度
                    top_correction = abs(best_top[0] - pred_top)
                    if top_correction <= max_correction_threshold:
                        refined_coords[1] = best_top[0]  # y坐标
                        found_borders['top'] = True
                        refinement_details.append(f"上边框: {pred_top:.1f} → {best_top[0]:.1f} (距离: {best_top[1]:.1f})")
                    else:
                        self._thread_safe_print(f"      ⚠️ 上边框修正幅度过大({top_correction:.1f}px > {max_correction_threshold}px)，保持原值")
                
                # 处理下边框
                if candidates['bottom']:
                    candidates['bottom'].sort(key=lambda x: x[1])
                    best_bottom = candidates['bottom'][0]
                    
                    # 验证下边框修正幅度
                    bottom_correction = abs(best_bottom[0] - pred_bottom)
                    if bottom_correction <= max_correction_threshold:
                        refined_coords[3] = best_bottom[0]  # y坐标
                        found_borders['bottom'] = True
                        refinement_details.append(f"下边框: {pred_bottom:.1f} → {best_bottom[0]:.1f} (距离: {best_bottom[1]:.1f})")
                    else:
                        self._thread_safe_print(f"      ⚠️ 下边框修正幅度过大({bottom_correction:.1f}px > {max_correction_threshold}px)，保持原值")
        
        else:
            # 标准高度表格的正常处理
            # 处理上边框
            if candidates['top']:
                candidates['top'].sort(key=lambda x: x[1])
                best_top = candidates['top'][0]
                
                # 验证上边框修正幅度
                top_correction = abs(best_top[0] - pred_top)
                if top_correction <= max_correction_threshold:
                    refined_coords[1] = best_top[0]  # y坐标
                    found_borders['top'] = True
                    refinement_details.append(f"上边框: {pred_top:.1f} → {best_top[0]:.1f} (距离: {best_top[1]:.1f})")
                else:
                    self._thread_safe_print(f"      ⚠️ 上边框修正幅度过大({top_correction:.1f}px > {max_correction_threshold}px)，保持原值")
            
            # 处理下边框
            if candidates['bottom']:
                candidates['bottom'].sort(key=lambda x: x[1])
                best_bottom = candidates['bottom'][0]
                
                # 验证下边框修正幅度
                bottom_correction = abs(best_bottom[0] - pred_bottom)
                if bottom_correction <= max_correction_threshold:
                    refined_coords[3] = best_bottom[0]  # y坐标
                    found_borders['bottom'] = True
                    refinement_details.append(f"下边框: {pred_bottom:.1f} → {best_bottom[0]:.1f} (距离: {best_bottom[1]:.1f})")
                else:
                    self._thread_safe_print(f"      ⚠️ 下边框修正幅度过大({bottom_correction:.1f}px > {max_correction_threshold}px)，保持原值")
        
        # 左右边框处理（对所有表格都相同）
        # 处理左边框
        if candidates['left']:
            # 按距离排序，选择最近的
            candidates['left'].sort(key=lambda x: x[1])
            best_left = candidates['left'][0]
            
            # 验证左边框修正幅度
            left_correction = abs(best_left[0] - pred_left)
            if left_correction <= max_correction_threshold:
                refined_coords[0] = best_left[0]  # x坐标
                found_borders['left'] = True
                refinement_details.append(f"左边框: {pred_left:.1f} → {best_left[0]:.1f} (距离: {best_left[1]:.1f})")
            else:
                self._thread_safe_print(f"      ⚠️ 左边框修正幅度过大({left_correction:.1f}px > {max_correction_threshold}px)，保持原值")
        
        # 处理右边框
        if candidates['right']:
            candidates['right'].sort(key=lambda x: x[1])
            best_right = candidates['right'][0]
            
            # 验证右边框修正幅度
            right_correction = abs(best_right[0] - pred_right)
            if right_correction <= max_correction_threshold:
                refined_coords[2] = best_right[0]  # x坐标
                found_borders['right'] = True
                refinement_details.append(f"右边框: {pred_right:.1f} → {best_right[0]:.1f} (距离: {best_right[1]:.1f})")
            else:
                self._thread_safe_print(f"      ⚠️ 右边框修正幅度过大({right_correction:.1f}px > {max_correction_threshold}px)，保持原值")
        
        # 根据找到的边框线的两端坐标进行坐标修正
        coordinate_adjustments = []
        
        # 1. 如果找到水平边框（上/下），使用其水平范围修正左右边界
        horizontal_x_ranges = []
        if found_borders['top']:
            top_info = candidates['top'][0]
            horizontal_x_ranges.append(top_info[2])  # [x_start, x_end]
        if found_borders['bottom']:
            bottom_info = candidates['bottom'][0]
            horizontal_x_ranges.append(bottom_info[2])  # [x_start, x_end]
        
        if horizontal_x_ranges:
            # 取所有水平边框的最小和最大x坐标
            all_x_starts = [x_range[0] for x_range in horizontal_x_ranges]
            all_x_ends = [x_range[1] for x_range in horizontal_x_ranges]
            
            min_x = min(all_x_starts)
            max_x = max(all_x_ends)
            
            # 验证左边界修正幅度
            left_x_correction = abs(min_x - refined_coords[0])
            if not found_borders['left'] or abs(min_x - pred_left) < abs(refined_coords[0] - pred_left):
                if left_x_correction > 2 and left_x_correction <= max_correction_threshold:  # 避免微小调整且不超过阈值
                    coordinate_adjustments.append(f"左边界: {refined_coords[0]:.1f} → {min_x:.1f} (基于水平边框)")
                    refined_coords[0] = min_x
                elif left_x_correction > max_correction_threshold:
                    self._thread_safe_print(f"      ⚠️ 基于水平边框的左边界修正幅度过大({left_x_correction:.1f}px > {max_correction_threshold}px)，保持原值")
            
            # 验证右边界修正幅度
            right_x_correction = abs(max_x - refined_coords[2])
            if not found_borders['right'] or abs(max_x - pred_right) < abs(refined_coords[2] - pred_right):
                if right_x_correction > 2 and right_x_correction <= max_correction_threshold:  # 避免微小调整且不超过阈值
                    coordinate_adjustments.append(f"右边界: {refined_coords[2]:.1f} → {max_x:.1f} (基于水平边框)")
                    refined_coords[2] = max_x
                elif right_x_correction > max_correction_threshold:
                    self._thread_safe_print(f"      ⚠️ 基于水平边框的右边界修正幅度过大({right_x_correction:.1f}px > {max_correction_threshold}px)，保持原值")
        
        # 2. 如果找到垂直边框（左/右），使用其垂直范围修正上下边界
        vertical_y_ranges = []
        if found_borders['left']:
            left_info = candidates['left'][0]
            vertical_y_ranges.append(left_info[2])  # [y_start, y_end]
        if found_borders['right']:
            right_info = candidates['right'][0]
            vertical_y_ranges.append(right_info[2])  # [y_start, y_end]
        
        if vertical_y_ranges:
            # 取所有垂直边框的最小和最大y坐标
            all_y_starts = [y_range[0] for y_range in vertical_y_ranges]
            all_y_ends = [y_range[1] for y_range in vertical_y_ranges]
            
            min_y = min(all_y_starts)
            max_y = max(all_y_ends)
            
            # 验证上边界修正幅度
            top_y_correction = abs(min_y - refined_coords[1])
            if not found_borders['top'] or abs(min_y - pred_top) < abs(refined_coords[1] - pred_top):
                if top_y_correction > 2 and top_y_correction <= max_correction_threshold:  # 避免微小调整且不超过阈值
                    coordinate_adjustments.append(f"上边界: {refined_coords[1]:.1f} → {min_y:.1f} (基于垂直边框)")
                    refined_coords[1] = min_y
                elif top_y_correction > max_correction_threshold:
                    self._thread_safe_print(f"      ⚠️ 基于垂直边框的上边界修正幅度过大({top_y_correction:.1f}px > {max_correction_threshold}px)，保持原值")
            
            # 验证下边界修正幅度
            bottom_y_correction = abs(max_y - refined_coords[3])
            if not found_borders['bottom'] or abs(max_y - pred_bottom) < abs(refined_coords[3] - pred_bottom):
                if bottom_y_correction > 2 and bottom_y_correction <= max_correction_threshold:  # 避免微小调整且不超过阈值
                    coordinate_adjustments.append(f"下边界: {refined_coords[3]:.1f} → {max_y:.1f} (基于垂直边框)")
                    refined_coords[3] = max_y
                elif bottom_y_correction > max_correction_threshold:
                    self._thread_safe_print(f"      ⚠️ 基于垂直边框的下边界修正幅度过大({bottom_y_correction:.1f}px > {max_correction_threshold}px)，保持原值")
        
        # 3. 边框对齐：确保找到的边框线与修正后的坐标一致
        alignment_adjustments = []
        if found_borders['top'] and found_borders['left'] and found_borders['right']:
            # 上边框应该与左右边框的x坐标对齐
            top_info = candidates['top'][0]
            top_x_range = top_info[2]
            if abs(top_x_range[0] - refined_coords[0]) > 3:
                alignment_adjustments.append(f"上边框左端对齐: {top_x_range[0]:.1f} → {refined_coords[0]:.1f}")
            if abs(top_x_range[1] - refined_coords[2]) > 3:
                alignment_adjustments.append(f"上边框右端对齐: {top_x_range[1]:.1f} → {refined_coords[2]:.1f}")
        
        if found_borders['bottom'] and found_borders['left'] and found_borders['right']:
            # 下边框应该与左右边框的x坐标对齐
            bottom_info = candidates['bottom'][0]
            bottom_x_range = bottom_info[2]
            if abs(bottom_x_range[0] - refined_coords[0]) > 3:
                alignment_adjustments.append(f"下边框左端对齐: {bottom_x_range[0]:.1f} → {refined_coords[0]:.1f}")
            if abs(bottom_x_range[1] - refined_coords[2]) > 3:
                alignment_adjustments.append(f"下边框右端对齐: {bottom_x_range[1]:.1f} → {refined_coords[2]:.1f}")
        
        # 合并所有调整信息
        all_adjustments = refinement_details + coordinate_adjustments + alignment_adjustments
        
        # 确保坐标顺序正确
        if refined_coords[0] > refined_coords[2]:  # left > right
            refined_coords[0], refined_coords[2] = refined_coords[2], refined_coords[0]
        if refined_coords[1] > refined_coords[3]:  # top > bottom
            refined_coords[1], refined_coords[3] = refined_coords[3], refined_coords[1]
        
        # 检查是否找到了足够的边框（至少2个边）
        found_count = sum(found_borders.values())
        if found_count >= 2:
            final_height = refined_coords[3] - refined_coords[1]
            height_change = final_height - pred_height
            
            if is_small_height_table:
                self._thread_safe_print(f"    📐 小高度表格修正完成: 找到 {found_count} 个边框 (高度: {pred_height:.1f} → {final_height:.1f}, 变化: {height_change:+.1f})")
            else:
                self._thread_safe_print(f"    📐 修正边框: 找到 {found_count} 个匹配的边框线")
            
            for detail in all_adjustments[:4]:  # 显示前4项调整
                self._thread_safe_print(f"      - {detail}")
            if len(all_adjustments) > 4:
                self._thread_safe_print(f"      - ... 等 {len(all_adjustments)} 项调整")
            return refined_coords
        
        return None
    
    def _refine_table_predictions(self, tables: List[Dict[str, Any]], page: fitz.Page) -> List[Dict[str, Any]]:
        """
        根据页面中的实际线条修正表格预测框
        
        Args:
            tables: 原始表格预测列表
            page: PyMuPDF页面对象
            
        Returns:
            修正后的表格列表
        """
        if not tables:
            return tables
        
        # 提取页面中的线条
        page_lines = self._extract_page_lines(page)
        if not page_lines:
            self._thread_safe_print(f"  📐 未找到页面线条，保持原始预测框")
            return tables
        
        self._thread_safe_print(f"  📐 找到 {len(page_lines)} 个页面线条，开始修正表格边框...")
        
        refined_tables = []
        for i, table in enumerate(tables):
            original_bbox = table['bbox'].copy()
            
            # 查找最近的边框线
            refined_bbox = self._find_nearest_table_borders(original_bbox, page_lines, tolerance=30.0)
            
            if refined_bbox:
                # 更新表格信息
                refined_table = table.copy()
                refined_table['bbox'] = refined_bbox
                refined_table['rect'] = fitz.Rect(refined_bbox)
                refined_table['refined'] = True
                refined_tables.append(refined_table)
                
                self._thread_safe_print(f"    ✅ 表格 {i+1} 边框已修正: {[round(x, 1) for x in original_bbox]} → {[round(x, 1) for x in refined_bbox]}")
            else:
                # 保持原始预测框
                table['refined'] = False
                refined_tables.append(table)
                self._thread_safe_print(f"    ⚪ 表格 {i+1} 保持原始边框: {[round(x, 1) for x in original_bbox]} (未找到匹配线条)")
        
        return refined_tables
    
    def _smart_resize(self, height: int, width: int, min_pixels: int = 512*28*28, max_pixels: int = 2048*28*28) -> Tuple[int, int]:
        """
        根据min_pixels和max_pixels计算模型输入尺寸
        模拟Qwen2.5-VL的smart_resize功能
        
        Args:
            height: 原图高度
            width: 原图宽度
            min_pixels: 最小像素数
            max_pixels: 最大像素数
            
        Returns:
            (input_height, input_width): 模型输入尺寸
        """
        pixels = height * width
        
        if pixels < min_pixels:
            # 需要放大
            scale = math.sqrt(min_pixels / pixels)
            input_height = int(height * scale)
            input_width = int(width * scale)
        elif pixels > max_pixels:
            # 需要缩小
            scale = math.sqrt(max_pixels / pixels)
            input_height = int(height * scale)
            input_width = int(width * scale)
        else:
            # 尺寸合适，不需要调整
            input_height = height
            input_width = width
        
        # 确保尺寸是28的倍数（Qwen2.5-VL的patch size）
        input_height = ((input_height + 27) // 28) * 28
        input_width = ((input_width + 27) // 28) * 28
        
        return input_height, input_width
    
    def extract_text_blocks(self, page: fitz.Page) -> List[Dict[str, Any]]:
        """
        提取页面中的文本块
        
        Args:
            page: PyMuPDF页面对象
            
        Returns:
            文本块信息列表
        """
        text_blocks = []
        text_instances = page.get_text("dict")["blocks"]
        
        for block in text_instances:
            if block["type"] == 0:  # 0 代表文本块
                text_blocks.append({
                    'type': 'text',
                    'bbox': block["bbox"],
                    'content': self._extract_block_text(block),
                    'rect': fitz.Rect(block["bbox"])
                })
        
        return text_blocks
    
    def extract_images(self, page: fitz.Page) -> List[Dict[str, Any]]:
        """
        提取页面中的图像
        
        Args:
            page: PyMuPDF页面对象
            
        Returns:
            图像信息列表
        """
        images = []
        
        try:
            # 直接从页面块中提取图像块，避免重复
            text_dict = page.get_text("dict")
            image_blocks = [block for block in text_dict["blocks"] if block["type"] == 1]
            
            for img_index, block in enumerate(image_blocks):
                images.append({
                    'type': 'image',
                    'bbox': block["bbox"],
                    'index': img_index,
                    'rect': fitz.Rect(block["bbox"])
                })
            
            # 去重：移除重叠的图像边框
            original_count = len(images)
            if len(images) > 1:
                images = self._remove_duplicate_images(images)
                if len(images) < original_count:
                    self._thread_safe_print(f"  图像去重: {original_count} → {len(images)}")
            
        except Exception as e:
            self._thread_safe_print(f"提取图像时出错: {str(e)}")
        
        return images
    
    def extract_tables_with_qwen(self, page_image_path: str, page_width: float, page_height: float, 
                                image_width: int, image_height: int, model_id: str = "Qwen/Qwen2.5-VL-72B-Instruct", 
                                max_retries: int = 3, retry_delay: float = 1.0) -> List[Dict[str, Any]]:
        """
        使用Qwen2.5-VL提取表格边框
        
        Args:
            page_image_path: 页面图片路径
            page_width: PDF页面宽度
            page_height: PDF页面高度  
            image_width: 图片宽度
            image_height: 图片高度
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
            
        Returns:
            表格信息列表
        """
        from utils.html_parser import inference_with_api
        
        tables = []
        
        try:
            # 第一步：预检查是否存在表格
            check_prompt = "该图片是否有表格，请回答是或否"
            check_sys_prompt = "You are an AI assistant. Please answer whether there are tables in the image with '是' (yes) or '否' (no)."
            
            self._thread_safe_print(f"    正在预检查是否存在表格...")
            
            # 调用API进行预检查
            check_result = inference_with_api(
                image_path=page_image_path,
                prompt=check_prompt,
                sys_prompt=check_sys_prompt,
                model_id=model_id, 
                max_retries=max_retries,
                retry_delay=retry_delay
            )
            
            # 判断是否包含表格
            has_table = False
            if check_result:
                check_result_lower = check_result.lower().strip()
                if '是' in check_result or 'yes' in check_result_lower or '有表格' in check_result:
                    has_table = True
                    self._thread_safe_print(f"      预检查结果: 检测到表格存在")
                else:
                    has_table = False
                    self._thread_safe_print(f"      预检查结果: 未检测到表格")
            
            # 如果没有表格，直接返回空列表
            if not has_table:
                self._thread_safe_print(f"      跳过详细表格检测")
                return tables
            
            # 第二步：详细表格边框检测
            self._thread_safe_print(f"    正在进行详细表格边框检测...")
            
            # 使用Qwen2.5-VL分析图片中的表格
            prompt = "请定位图片中所有表格的位置，以JSON格式输出其bbox坐标"
                        
            # 调用API获取表格检测结果
            result = inference_with_api(
                image_path=page_image_path,
                prompt=prompt,
                max_retries=max_retries,
                retry_delay=retry_delay
            )
            
            # 解析JSON结果
            try:
                # 提取JSON部分
                json_start = result.find('[')
                json_end = result.rfind(']') + 1
                
                if json_start != -1 and json_end > json_start:
                    json_str = result[json_start:json_end]
                    detected_tables = json.loads(json_str)
                    
                    # 根据API参数计算模型输入尺寸
                    min_pixels = 512*28*28
                    max_pixels = 2048*28*28
                    input_height, input_width = self._smart_resize(image_height, image_width, min_pixels, max_pixels)
                    
                    self._thread_safe_print(f"      原图尺寸: {image_width}x{image_height}, 模型输入尺寸: {input_width}x{input_height}")
                    
                    for i, table_data in enumerate(detected_tables):
                        if 'bbox_2d' in table_data:
                            # Qwen输出的坐标格式 [x1, y1, x2, y2]，相对于模型输入尺寸
                            qwen_bbox = table_data['bbox_2d']
                            
                            # 按照官方cookbook的坐标转换逻辑
                            # 先转换为实际图片坐标
                            abs_x1 = qwen_bbox[0] / input_width * image_width
                            abs_y1 = qwen_bbox[1] / input_height * image_height
                            abs_x2 = qwen_bbox[2] / input_width * image_width  
                            abs_y2 = qwen_bbox[3] / input_height * image_height
                            
                            # 确保坐标顺序正确
                            if abs_x1 > abs_x2:
                                abs_x1, abs_x2 = abs_x2, abs_x1
                            if abs_y1 > abs_y2:
                                abs_y1, abs_y2 = abs_y2, abs_y1
                            
                            # 再映射到PDF坐标系
                            scale_x = page_width / image_width
                            scale_y = page_height / image_height
                            
                            pdf_x1 = abs_x1 * scale_x
                            pdf_y1 = abs_y1 * scale_y
                            pdf_x2 = abs_x2 * scale_x
                            pdf_y2 = abs_y2 * scale_y
                            
                            pdf_bbox = [pdf_x1, pdf_y1, pdf_x2, pdf_y2]
                            
                            tables.append({
                                'type': 'table',
                                'bbox': pdf_bbox,
                                'index': i,
                                'rect': fitz.Rect(pdf_bbox),
                                'label': table_data.get('label', '表格'),
                                'confidence': table_data.get('confidence', 1.0)
                            })
                            
                            self._thread_safe_print(f"      检测到表格 {i+1}: Qwen坐标{qwen_bbox} -> 图片坐标[{abs_x1:.1f},{abs_y1:.1f},{abs_x2:.1f},{abs_y2:.1f}] -> PDF坐标{pdf_bbox}")
                    
                    self._thread_safe_print(f"    共检测到 {len(tables)} 个表格")
                    
                    # 绘制预测框到图片上并保存
                    if detected_tables:
                        # 转换为图片坐标用于绘制
                        image_predictions = []
                        for table_data in detected_tables:
                            if 'bbox_2d' in table_data:
                                qwen_bbox = table_data['bbox_2d']
                                # 转换为实际图片坐标
                                abs_x1 = qwen_bbox[0] / input_width * image_width
                                abs_y1 = qwen_bbox[1] / input_height * image_height
                                abs_x2 = qwen_bbox[2] / input_width * image_width  
                                abs_y2 = qwen_bbox[3] / input_height * image_height
                                
                                # 确保坐标顺序正确
                                if abs_x1 > abs_x2:
                                    abs_x1, abs_x2 = abs_x2, abs_x1
                                if abs_y1 > abs_y2:
                                    abs_y1, abs_y2 = abs_y2, abs_y1
                                
                                # 创建用于绘制的预测数据
                                image_pred = table_data.copy()
                                image_pred['bbox_2d'] = [abs_x1, abs_y1, abs_x2, abs_y2]
                                image_predictions.append(image_pred)
                        
                        self._draw_predictions_on_image(page_image_path, image_predictions, os.path.basename(page_image_path))
                
                else:
                    self._thread_safe_print(f"    未能从API响应中提取有效的JSON: {result[:200]}...")
                    
            except json.JSONDecodeError as e:
                self._thread_safe_print(f"    解析JSON时出错: {str(e)}")
                self._thread_safe_print(f"    API响应: {result[:500]}...")
                
        except Exception as e:
            self._thread_safe_print(f"    表格检测过程中出错: {str(e)}")
        
        return tables
    
    def draw_bboxes_on_page(self, page: fitz.Page, elements: List[Dict[str, Any]]) -> None:
        """
        在页面上绘制边界框
        
        Args:
            page: PyMuPDF页面对象
            elements: 要绘制的元素列表
        """
        for element in elements:
            element_type = element['type']
            rect = element['rect']
            color = self.colors.get(element_type, (0, 0, 0))
            
            # 确定线条宽度（修正过的表格使用更粗的线条）
            line_width = self.line_width
            if element_type == 'table' and element.get('refined', False):
                line_width = self.line_width * 2  # 修正过的表格使用2倍线宽
            
            # 绘制矩形框
            page.draw_rect(rect, color=color, width=line_width)
            
            # 添加标签
            label_point = fitz.Point(rect.x0, rect.y0 - 5)
            label_text = f"{element_type}"
            
            if element_type == 'image':
                label_text += f" #{element.get('index', 0)}"
            elif element_type == 'table':
                label_text += f" #{element.get('index', 0) + 1}"
                if element.get('confidence'):
                    label_text += f" ({element.get('confidence', 1.0):.2f})"
                if element.get('refined', False):
                    label_text += " 📐"  # 标识经过框线修正
            
            # 绘制标签文本
            page.insert_text(label_point, label_text, fontsize=8, color=color)
    
    def _process_single_page(self, pdf_path: str, page_num: int, page_image_path: Optional[str], 
                           enable_table_detection: bool, model_id: str, max_retries: int, 
                           retry_delay: float) -> Dict[str, Any]:
        """
        处理单个PDF页面（线程安全版本）
        
        Args:
            pdf_path: PDF文件路径
            page_num: 页面编号（从0开始）
            page_image_path: 页面图片路径（如果启用表格检测）
            enable_table_detection: 是否启用表格检测
            model_id: Qwen模型ID
            max_retries: API调用最大重试次数
            retry_delay: API调用重试间隔
            
        Returns:
            页面处理结果
        """
        thread_id = threading.current_thread().ident
        
        try:
            # 为每个线程创建独立的PDF文档实例（避免并发问题）
            doc = fitz.open(pdf_path)
            page = doc[page_num]
            
            self._thread_safe_print(f"🧵 线程 {thread_id}: 开始处理第 {page_num + 1} 页...")
            
            all_elements = []
            page_stats = {'text_blocks': 0, 'images': 0, 'tables': 0, 'refined_tables': 0}
            
            # 1. 优先提取表格（如果启用）
            tables = []
            if enable_table_detection and page_image_path and os.path.exists(page_image_path):
                try:
                    page_rect = page.rect
                    page_width = float(page_rect.width)
                    page_height = float(page_rect.height)
                    
                    # 获取图片信息
                    from PIL import Image
                    img = Image.open(page_image_path)
                    image_width, image_height = img.size
                    img.close()
                    
                    tables = self.extract_tables_with_qwen(
                        page_image_path,
                        page_width,
                        page_height,
                        image_width,
                        image_height,
                        model_id=model_id,
                        max_retries=max_retries,
                        retry_delay=retry_delay
                    )
                    tables = tables or []
                    
                    # 使用PyMuPDF线条信息修正表格边框
                    if tables:
                        self._thread_safe_print(f"🧵 线程 {thread_id}: 对第 {page_num + 1} 页的 {len(tables)} 个检测到的表格进行边框修正...")
                        tables = self._refine_table_predictions(tables, page)
                    
                    page_stats['tables'] = len(tables)
                    # 统计修正的表格数量
                    refined_count = sum(1 for table in tables if table.get('refined', False))
                    page_stats['refined_tables'] = refined_count
                    
                    if len(tables) > 0:
                        self._thread_safe_print(f"🧵 线程 {thread_id}: 第 {page_num + 1} 页成功检测到 {len(tables)} 个表格{f' (其中{refined_count}个边框已修正)' if refined_count > 0 else ''}")
                    else:
                        self._thread_safe_print(f"🧵 线程 {thread_id}: 第 {page_num + 1} 页预检查发现表格但详细检测未找到具体位置")
                        
                except Exception as e:
                    self._thread_safe_print(f"🧵 线程 {thread_id}: 第 {page_num + 1} 页表格检测失败: {str(e)}")
            else:
                self._thread_safe_print(f"🧵 线程 {thread_id}: 第 {page_num + 1} 页跳过表格检测（未启用或图片不可用）")
                tables = []
            
            # 2. 提取文本块并移除与表格重叠的
            text_blocks = self.extract_text_blocks(page)
            self._thread_safe_print(f"🧵 线程 {thread_id}: 第 {page_num + 1} 页找到 {len(text_blocks)} 个原始文本块")
            
            # 移除与表格重叠的文字块
            filtered_text_blocks = self._remove_overlapping_text_blocks(text_blocks, tables)
            page_stats['text_blocks'] = len(filtered_text_blocks)
            self._thread_safe_print(f"🧵 线程 {thread_id}: 第 {page_num + 1} 页保留 {len(filtered_text_blocks)} 个文本块（已移除与表格重叠的）")
            
            # 3. 提取图像并去重
            images = self.extract_images(page)
            page_stats['images'] = len(images)
            self._thread_safe_print(f"🧵 线程 {thread_id}: 第 {page_num + 1} 页找到 {len(images)} 个图像（已去重）")
            
            # 4. 移除与图像重叠的表格预测框，以图像为准
            if tables and images:
                original_table_count = len(tables)
                tables = self._remove_overlapping_tables(tables, images)
                removed_table_count = original_table_count - len(tables)
                page_stats['tables'] = len(tables)  # 更新表格统计
                
                if removed_table_count > 0:
                    self._thread_safe_print(f"🧵 线程 {thread_id}: 第 {page_num + 1} 页移除了 {removed_table_count} 个与图像重叠的表格预测框")
            
            # 合并所有元素
            all_elements.extend(tables)
            all_elements.extend(filtered_text_blocks)
            all_elements.extend(images)
            
            self._thread_safe_print(f"🧵 线程 {thread_id}: 第 {page_num + 1} 页处理完成，共 {len(all_elements)} 个元素")
            
            # 关闭文档实例
            doc.close()
            
            return {
                'page_num': page_num,
                'elements': all_elements,
                'stats': page_stats,
                'status': 'success',
                'thread_id': thread_id
            }
            
        except Exception as e:
            error_msg = f"处理第 {page_num + 1} 页时出错: {str(e)}"
            self._thread_safe_print(f"🧵 线程 {thread_id}: ❌ {error_msg}")
            return {
                'page_num': page_num,
                'elements': [],
                'stats': {'text_blocks': 0, 'images': 0, 'tables': 0, 'refined_tables': 0},
                'status': 'error',
                'error': error_msg,
                'thread_id': thread_id
            }
    
    def process_pdf(self, input_path: str, output_path: str, enable_table_detection: bool = True, 
                    model_id: str = "Qwen/Qwen2.5-VL-7B-Instruct", max_retries: int = 3, retry_delay: float = 1.0) -> Dict[str, Any]:
        """
        使用多线程并行处理整个PDF文件，提取并绘制所有边界框
        
        Args:
            input_path: 输入PDF路径
            output_path: 输出PDF路径
            enable_table_detection: 是否启用表格检测
            model_id: Qwen模型ID，可选择不同的模型版本
            max_retries: API调用最大重试次数
            retry_delay: API调用重试间隔
            
        Returns:
            处理结果统计
        """
        try:
            # 打开PDF文档获取基本信息
            doc = fitz.open(input_path)
            total_pages = len(doc)
            doc.close()
            
            total_elements = {
                'text_blocks': 0,
                'images': 0,
                'tables': 0,
                'refined_tables': 0,
                'pages': total_pages
            }
            
            # 收集所有页面的元素用于保存元数据
            all_elements_by_page = {}
            
            print(f"🚀 开始并行处理PDF文件: {input_path}")
            print(f"📄 总页数: {total_pages}")
            print(f"🧵 使用线程数: {self.max_workers}")
            
            # 如果启用表格检测，先转换PDF为图片
            page_images = {}
            if enable_table_detection:
                from utils.pdf_converter import pdf_to_jpg
                import tempfile
                
                print(f"🖼️ 开始转换PDF为图片以进行表格检测...")
                
                try:
                    # 读取PDF文件字节
                    with open(input_path, 'rb') as pdf_file:
                        pdf_bytes = pdf_file.read()
                    
                    # 创建临时目录用于存储图片
                    temp_dir = tempfile.mkdtemp()
                    
                    # 转换PDF为图片
                    image_paths = pdf_to_jpg(
                        pdf_bytes,
                        pdf_filename="temp_for_table_detection",
                        output_dir=temp_dir,
                        dpi=300
                    )
                    
                    # 构建页码到图片路径的映射
                    for i, img_path in enumerate(image_paths):
                        page_images[i] = img_path
                    
                    print(f"✅ PDF转换完成，共生成 {len(image_paths)} 张图片")
                    
                except Exception as e:
                    print(f"❌ PDF转换失败，将跳过表格检测: {str(e)}")
                    enable_table_detection = False
            
            # 多线程并行处理所有页面
            page_results = {}
            failed_pages = []
            
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有页面处理任务
                future_to_page = {}
                for page_num in range(total_pages):
                    page_image_path = page_images.get(page_num) if enable_table_detection else None
                    
                    future = executor.submit(
                        self._process_single_page,
                        input_path,
                        page_num,
                        page_image_path,
                        enable_table_detection,
                        model_id,
                        max_retries,
                        retry_delay
                    )
                    future_to_page[future] = page_num
                
                # 收集处理结果
                completed_count = 0
                for future in as_completed(future_to_page):
                    page_num = future_to_page[future]
                    try:
                        result = future.result()
                        completed_count += 1
                        
                        if result['status'] == 'success':
                            page_results[page_num] = result
                            # 更新统计信息
                            total_elements['text_blocks'] += result['stats']['text_blocks']
                            total_elements['images'] += result['stats']['images']
                            total_elements['tables'] += result['stats']['tables']
                            total_elements['refined_tables'] += result['stats']['refined_tables']
                        else:
                            failed_pages.append((page_num, result.get('error', '未知错误')))
                            # 为失败的页面创建空结果
                            page_results[page_num] = {
                                'page_num': page_num,
                                'elements': [],
                                'stats': {'text_blocks': 0, 'images': 0, 'tables': 0, 'refined_tables': 0},
                                'status': 'error'
                            }
                        
                        # 显示进度
                        progress = (completed_count / total_pages) * 100
                        print(f"📊 处理进度: {completed_count}/{total_pages} ({progress:.1f}%)")
                        
                    except Exception as e:
                        failed_pages.append((page_num, str(e)))
                        completed_count += 1
                        # 创建错误页面的空结果
                        page_results[page_num] = {
                            'page_num': page_num,
                            'elements': [],
                            'stats': {'text_blocks': 0, 'images': 0, 'tables': 0, 'refined_tables': 0},
                            'status': 'error'
                        }
            
            processing_time = time.time() - start_time
            print(f"⏱️ 并行处理完成，耗时: {processing_time:.2f} 秒")
            
            # 报告失败的页面
            if failed_pages:
                print(f"⚠️ {len(failed_pages)} 个页面处理失败:")
                for page_num, error in failed_pages:
                    print(f"  - 第 {page_num + 1} 页: {error}")
            
            # 清理临时图片文件
            if page_images:
                import shutil
                for img_path in page_images.values():
                    temp_dir = os.path.dirname(img_path)
                    break
                try:
                    shutil.rmtree(temp_dir)
                    print(f"🧹 清理临时图片文件: {temp_dir}")
                except Exception:
                    pass
            
            # 汇总并绘制边界框到最终PDF
            print(f"🎨 开始汇总并绘制边界框...")
            
            # 重新打开PDF进行绘制
            doc = fitz.open(input_path)
            
            for page_num in range(total_pages):
                if page_num in page_results:
                    page = doc[page_num]
                    elements = page_results[page_num]['elements']
                    
                    # 绘制所有边界框
                    if elements:
                        self.draw_bboxes_on_page(page, elements)
                        print(f"  ✅ 第 {page_num + 1} 页: 绘制了 {len(elements)} 个边界框")
                    else:
                        print(f"  ⚪ 第 {page_num + 1} 页: 无边界框可绘制")
                    
                    # 保存当前页面的元素信息
                    all_elements_by_page[page_num] = elements
            
            # 保存处理后的PDF
            doc.save(output_path)
            doc.close()
            
            # 保存元数据
            metadata_path = self._save_bbox_metadata(all_elements_by_page, output_path, input_path)
            
            print(f"\n✅ 多线程处理完成！")
            print(f"📄 输出文件: {output_path}")
            if metadata_path:
                print(f"📋 元数据文件: {metadata_path}")
            print(f"📊 统计信息:")
            print(f"  - 文本块: {total_elements['text_blocks']} (已移除与表格重叠的)")
            print(f"  - 图像: {total_elements['images']} (已去重)")
            refined_info = f" (其中{total_elements['refined_tables']}个边框已修正)" if total_elements['refined_tables'] > 0 else ""
            print(f"  - 表格: {total_elements['tables']}{refined_info}")
            print(f"  - 总页数: {total_elements['pages']}")
            print(f"🧵 使用线程数: {self.max_workers}")
            print(f"⏱️ 总耗时: {processing_time:.2f} 秒")
            print(f"🚀 平均每页耗时: {processing_time/total_pages:.2f} 秒")
            if failed_pages:
                print(f"⚠️ 失败页面数: {len(failed_pages)}")
            print(f"💡 表格优先检测已启用，重叠的文本块已自动移除")
            print(f"🖼️ 图像去重已启用，避免重复检测")
            if total_elements['refined_tables'] > 0:
                print(f"📐 框线修正已启用，{total_elements['refined_tables']}个表格边框已根据PDF线条修正")
            
            return {
                'status': 'success',
                'message': f'成功并行处理 {total_elements["pages"]} 页，共提取 {sum([total_elements[key] for key in ["text_blocks", "images", "tables"]])} 个元素',
                'statistics': total_elements,
                'input_path': input_path,
                'output_path': output_path,
                'metadata_path': metadata_path,
                'processing_time': processing_time,
                'failed_pages': failed_pages,
                'threads_used': self.max_workers
            }
            
        except Exception as e:
            error_msg = f"多线程处理PDF时出错: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                'status': 'error',
                'message': error_msg,
                'statistics': {},
                'input_path': input_path,
                'output_path': output_path,
                'metadata_path': '',
                'processing_time': 0,
                'failed_pages': [],
                'threads_used': self.max_workers
            }
    
    def _save_bbox_metadata(self, all_elements_by_page: Dict[int, List[Dict[str, Any]]], 
                           output_path: str, input_path: str) -> str:
        """
        保存边界框元数据到JSON文件
        
        Args:
            all_elements_by_page: 按页码分组的所有元素
            output_path: 输出PDF路径
            input_path: 输入PDF路径
            
        Returns:
            元数据文件路径
        """
        try:
            # 生成元数据文件路径
            output_dir = os.path.dirname(output_path)
            input_filename = os.path.basename(input_path)
            filename_without_ext = os.path.splitext(input_filename)[0]
            metadata_filename = f"{filename_without_ext}_bbox_metadata.json"
            metadata_path = os.path.join(output_dir, metadata_filename)
            
            # 构建元数据结构
            metadata = {
                "source_file": input_path,
                "output_file": output_path,
                "creation_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_pages": len(all_elements_by_page),
                "summary": {
                    "total_text_blocks": 0,
                    "total_images": 0,
                    "total_tables": 0,
                    "refined_tables": 0
                },
                "pages": {}
            }
            
            # 按页处理元素
            for page_num, elements in all_elements_by_page.items():
                page_data = {
                    "page_number": page_num + 1,
                    "elements": []
                }
                
                for element in elements:
                    element_data = {
                        "type": element['type'],
                        "bbox": element['bbox'],
                        "index": element.get('index', 0)
                    }
                    
                    # 添加类型特定的信息
                    if element['type'] == 'text':
                        element_data['content'] = element.get('content', '')[:200]  # 限制长度
                    elif element['type'] == 'table':
                        element_data['label'] = element.get('label', '表格')
                        element_data['confidence'] = element.get('confidence', 1.0)
                        element_data['refined'] = element.get('refined', False)  # 是否被框线修正
                    
                    page_data['elements'].append(element_data)
                    
                    # 更新统计
                    if element['type'] == 'text':
                        metadata["summary"]["total_text_blocks"] += 1
                    elif element['type'] == 'image':
                        metadata["summary"]["total_images"] += 1
                    elif element['type'] == 'table':
                        metadata["summary"]["total_tables"] += 1
                        if element.get('refined', False):
                            metadata["summary"]["refined_tables"] += 1
                
                metadata["pages"][str(page_num + 1)] = page_data
            
            # 保存到JSON文件
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            print(f"📄 元数据已保存: {metadata_path}")
            return metadata_path
            
        except Exception as e:
            print(f"❌ 保存元数据失败: {str(e)}")
            return ""
    
    def _extract_block_text(self, block: Dict[str, Any]) -> str:
        """
        从文本块中提取文本内容
        
        Args:
            block: 文本块字典
            
        Returns:
            提取的文本内容
        """
        text_content = ""
        
        try:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text_content += span.get("text", "") + " "
            return text_content.strip()
        except Exception as e:
            return f"[提取文本失败: {str(e)}]"
    
    def _draw_predictions_on_image(self, image_path: str, predictions: List[Dict[str, Any]], image_filename: str) -> None:
        """
        在图片上绘制Qwen预测的表格边框并保存
        
        Args:
            image_path: 原始图片路径
            predictions: 预测结果列表（bbox_2d已转换为图片坐标）
            image_filename: 图片文件名
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
            import os
            
            # 打开原始图片
            img = Image.open(image_path)
            draw = ImageDraw.Draw(img)
            
            # 设置绘制参数
            colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
            line_width = 3
            
            # 尝试加载字体
            try:
                # Windows系统字体
                font = ImageFont.truetype("arial.ttf", 20)
            except:
                try:
                    # 其他系统默认字体
                    font = ImageFont.load_default()
                except:
                    font = None
            
            # 绘制每个预测框
            for i, pred in enumerate(predictions):
                if 'bbox_2d' in pred:
                    bbox = pred['bbox_2d']  # [x1, y1, x2, y2]
                    color = colors[i % len(colors)]
                    
                    # 绘制矩形框（确保坐标为整数）
                    draw.rectangle(
                        [(int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3]))],
                        outline=color,
                        width=line_width
                    )
                    
                    # 绘制标签
                    label = pred.get('label', f'表格 {i+1}')
                    confidence = pred.get('confidence', 1.0)
                    text = f"{label} {confidence:.2f}" if confidence < 1.0 else label
                    
                    # 标签位置（框的左上角上方）
                    text_x = int(bbox[0])
                    text_y = max(0, int(bbox[1]) - 25)
                    
                    # 绘制文本背景
                    if font:
                        text_bbox = draw.textbbox((text_x, text_y), text, font=font)
                        draw.rectangle(text_bbox, fill=color)
                        draw.text((text_x, text_y), text, fill=(255, 255, 255), font=font)
                    else:
                        # 如果没有字体，绘制简单文本
                        draw.text((text_x, text_y), text, fill=color)
            
            # 保存标注后的图片到tmp目录
            output_dir = "tmp"
            os.makedirs(output_dir, exist_ok=True)
            
            # 生成输出文件名
            base_name = os.path.splitext(image_filename)[0]
            output_filename = f"{base_name}_predicted.jpg"
            output_path = os.path.join(output_dir, output_filename)
            
            # 保存图片
            img.save(output_path, 'JPEG', quality=95)
            print(f"      预测框标注图片已保存: {output_path}")
            
        except Exception as e:
            print(f"      绘制预测框时出错: {str(e)}")
        finally:
            try:
                img.close()
            except:
                pass


def extract_pdf_bboxes(input_pdf_path: str, output_dir: str = "tmp", enable_table_detection: bool = True, 
                       model_id: str = "Qwen/Qwen2.5-VL-7B-Instruct", max_retries: int = 3, retry_delay: float = 1.0,
                       max_workers: int = 10) -> Dict[str, Any]:
    """
    提取PDF边界框的主函数（支持多线程）
    
    Args:
        input_pdf_path: 输入PDF文件路径
        output_dir: 输出目录
        enable_table_detection: 是否启用表格检测
        model_id: Qwen模型ID，可选择不同的模型版本
        max_retries: API调用最大重试次数
        retry_delay: API调用重试间隔
        max_workers: 最大工作线程数，默认10个
        
    Returns:
        处理结果
    """
    try:
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成输出文件名
        input_filename = os.path.basename(input_pdf_path)
        filename_without_ext = os.path.splitext(input_filename)[0]
        output_filename = f"{filename_without_ext}_bbox.pdf"
        output_path = os.path.join(output_dir, output_filename)
        
        # 创建提取器并处理（支持自定义线程数）
        extractor = PDFBboxExtractor(max_workers=max_workers)
        result = extractor.process_pdf(input_pdf_path, output_path, enable_table_detection, model_id, max_retries, retry_delay)
        
        return result
        
    except Exception as e:
        return {
            'status': 'error',
            'message': f'边界框提取失败: {str(e)}',
            'statistics': {},
            'input_path': input_pdf_path,
            'output_path': '',
            'metadata_path': '',
            'processing_time': 0,
            'failed_pages': [],
            'threads_used': max_workers
        }


if __name__ == "__main__":
    # 测试代码
    test_pdf = "test.pdf"
    if os.path.exists(test_pdf):
        result = extract_pdf_bboxes(test_pdf, max_workers=10)
        print(f"处理结果: {result}")
    else:
        print("请将测试PDF文件命名为 'test.pdf' 并放在当前目录") 