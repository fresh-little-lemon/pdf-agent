import fitz  # PyMuPDF
import os
from typing import List, Tuple
import uuid


def extract_images_from_pdf(pdf_file_bytes: bytes, pdf_filename: str, output_dir: str = "tmp") -> List[str]:
    """
    从PDF文件中提取所有图片
    
    Args:
        pdf_file_bytes: PDF文件的字节数据
        pdf_filename: PDF文件名（不包含扩展名）
        output_dir: 输出目录，默认为tmp
    
    Returns:
        提取的图片文件路径列表
    """
    # 创建专门的图片提取文件夹
    final_output_dir = os.path.join(output_dir, f"{pdf_filename}_figure")
    
    # 确保输出目录存在
    if not os.path.exists(final_output_dir):
        os.makedirs(final_output_dir)
    
    extracted_images = []
    
    try:
        # 打开PDF文件
        pdf_document = fitz.open("pdf", pdf_file_bytes)
        
        # 遍历每一页
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            
            # 获取页面中的图片列表
            image_list = page.get_images()
            
            # 遍历页面中的每张图片
            for img_index, img in enumerate(image_list):
                # 获取图片的xref（交叉引用编号）
                xref = img[0]
                
                try:
                    # 提取图片数据
                    base_image = pdf_document.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # 生成文件名：{pdf文件名}_page_{页码}_{图片序号}.jpg
                    # 页码从1开始，图片序号从1开始
                    image_filename = f"{pdf_filename}_page_{page_num + 1}_{img_index + 1}.{image_ext}"
                    image_path = os.path.join(final_output_dir, image_filename)
                    
                    # 保存图片
                    with open(image_path, "wb") as img_file:
                        img_file.write(image_bytes)
                    
                    extracted_images.append(image_path)
                    
                except Exception as e:
                    print(f"提取第{page_num + 1}页第{img_index + 1}张图片时出错: {str(e)}")
                    continue
        
        # 关闭PDF文档
        pdf_document.close()
        
        return extracted_images
        
    except Exception as e:
        raise Exception(f"PDF图片提取过程中出现错误: {str(e)}")


def get_pdf_image_info(pdf_file_bytes: bytes) -> dict:
    """
    获取PDF文件中的图片信息
    
    Args:
        pdf_file_bytes: PDF文件的字节数据
    
    Returns:
        包含图片信息的字典
    """
    try:
        pdf_document = fitz.open("pdf", pdf_file_bytes)
        
        total_images = 0
        page_image_counts = []
        image_details = []
        
        # 遍历每一页
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            image_list = page.get_images()
            page_image_count = len(image_list)
            page_image_counts.append(page_image_count)
            total_images += page_image_count
            
            # 获取图片详细信息
            for img_index, img in enumerate(image_list):
                xref = img[0]
                try:
                    base_image = pdf_document.extract_image(xref)
                    image_info = {
                        "页码": page_num + 1,
                        "图片序号": img_index + 1,
                        "格式": base_image["ext"],
                        "宽度": base_image["width"],
                        "高度": base_image["height"],
                        "大小": f"{len(base_image['image']) / 1024:.1f} KB"
                    }
                    image_details.append(image_info)
                except Exception:
                    continue
        
        pdf_document.close()
        
        return {
            "总图片数": total_images,
            "总页数": len(pdf_document),
            "每页图片数": page_image_counts,
            "图片详情": image_details
        }
        
    except Exception as e:
        raise Exception(f"获取PDF图片信息时出现错误: {str(e)}")


def clean_extracted_images(output_dir: str = "tmp", pdf_filename: str = None):
    """
    清理指定PDF文件提取的图片
    
    Args:
        output_dir: 输出目录
        pdf_filename: PDF文件名，如果指定则只清理该文件的图片
    """
    try:
        if pdf_filename:
            # 清理指定PDF文件的图片文件夹
            target_dir = os.path.join(output_dir, f"{pdf_filename}_figure")
            if os.path.exists(target_dir):
                import shutil
                shutil.rmtree(target_dir)
        else:
            # 清理所有图片相关文件夹
            if os.path.exists(output_dir):
                files = os.listdir(output_dir)
                for file in files:
                    if file.endswith('_figure') and os.path.isdir(os.path.join(output_dir, file)):
                        import shutil
                        shutil.rmtree(os.path.join(output_dir, file))
                
    except Exception as e:
        print(f"清理图片文件时出现错误: {str(e)}")


def convert_images_to_jpg(image_paths: List[str]) -> List[str]:
    """
    将提取的图片统一转换为JPG格式
    
    Args:
        image_paths: 图片路径列表
    
    Returns:
        转换后的JPG图片路径列表
    """
    from PIL import Image
    
    jpg_paths = []
    
    for img_path in image_paths:
        try:
            # 如果已经是JPG格式，直接添加
            if img_path.lower().endswith(('.jpg', '.jpeg')):
                jpg_paths.append(img_path)
                continue
            
            # 转换为JPG
            img = Image.open(img_path)
            
            # 如果是RGBA模式，转换为RGB
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            
            # 生成新的JPG文件名
            jpg_path = os.path.splitext(img_path)[0] + '.jpg'
            
            # 保存为JPG
            img.save(jpg_path, 'JPEG', quality=95)
            jpg_paths.append(jpg_path)
            
            # 删除原文件（如果不是JPG）
            if img_path != jpg_path:
                try:
                    os.remove(img_path)
                except Exception:
                    pass
            
        except Exception as e:
            print(f"转换图片 {img_path} 为JPG时出错: {str(e)}")
            continue
    
    return jpg_paths 