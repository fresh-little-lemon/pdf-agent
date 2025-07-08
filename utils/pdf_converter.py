import fitz  # PyMuPDF
import os
from typing import List, Tuple
import uuid


def pdf_to_jpg(pdf_file_bytes: bytes, pdf_filename: str = None, output_dir: str = "tmp", dpi: int = 150) -> List[str]:
    """
    将PDF文件转换为JPG图片
    
    Args:
        pdf_file_bytes: PDF文件的字节数据
        pdf_filename: PDF文件名（不含扩展名），用于创建子文件夹
        output_dir: 输出目录，默认为tmp
        dpi: 图片分辨率，默认150
    
    Returns:
        转换后的JPG文件路径列表
    """
    # 如果提供了pdf_filename，创建专门的子文件夹
    if pdf_filename:
        final_output_dir = os.path.join(output_dir, f"{pdf_filename}_converted_to_img")
    else:
        final_output_dir = output_dir
    
    # 确保输出目录存在
    if not os.path.exists(final_output_dir):
        os.makedirs(final_output_dir)
    
    # 生成唯一的文件名前缀
    file_prefix = str(uuid.uuid4()) if not pdf_filename else pdf_filename
    output_paths = []
    
    try:
        # 打开PDF文件
        pdf_document = fitz.open("pdf", pdf_file_bytes)
        
        # 遍历每一页
        for page_num in range(len(pdf_document)):
            # 获取页面
            page = pdf_document.load_page(page_num)
            
            # 设置缩放比例以调整图片质量
            zoom = dpi / 72  # 72是PDF的默认DPI
            mat = fitz.Matrix(zoom, zoom)
            
            # 渲染页面为图片
            pix = page.get_pixmap(matrix=mat)
            
            # 生成输出文件名
            output_filename = f"{file_prefix}_page_{page_num + 1}.jpg"
            output_path = os.path.join(final_output_dir, output_filename)
            
            # 保存图片
            pix.save(output_path)
            output_paths.append(output_path)
            
            # 释放内存
            pix = None
        
        # 关闭PDF文档
        pdf_document.close()
        
        return output_paths
        
    except Exception as e:
        raise Exception(f"PDF转换过程中出现错误: {str(e)}")


def get_pdf_info(pdf_file_bytes: bytes) -> dict:
    """
    获取PDF文件信息
    
    Args:
        pdf_file_bytes: PDF文件的字节数据
    
    Returns:
        包含PDF信息的字典
    """
    try:
        pdf_document = fitz.open("pdf", pdf_file_bytes)
        
        info = {
            "页数": len(pdf_document),
            "标题": pdf_document.metadata.get("title", "未知"),
            "作者": pdf_document.metadata.get("author", "未知"),
            "创建日期": pdf_document.metadata.get("creationDate", "未知"),
            "修改日期": pdf_document.metadata.get("modDate", "未知")
        }
        
        pdf_document.close()
        return info
        
    except Exception as e:
        raise Exception(f"获取PDF信息时出现错误: {str(e)}")


def clean_tmp_folder(output_dir: str = "tmp", keep_latest: int = 0, pdf_filename: str = None):
    """
    清理临时文件夹
    
    Args:
        output_dir: 要清理的目录
        keep_latest: 保留最新的几个文件组
        pdf_filename: PDF文件名，如果指定则只清理该文件的转换图片文件夹
    """
    try:
        if pdf_filename:
            # 清理指定PDF文件的转换图片文件夹
            target_dir = os.path.join(output_dir, f"{pdf_filename}_converted_to_img")
            if os.path.exists(target_dir):
                import shutil
                shutil.rmtree(target_dir)
        else:
            # 清理所有转换图片相关文件夹
            if os.path.exists(output_dir):
                files = os.listdir(output_dir)
                conversion_dirs = [f for f in files if f.endswith('_converted_to_img') and os.path.isdir(os.path.join(output_dir, f))]
                
                if keep_latest > 0 and conversion_dirs:
                    # 按修改时间排序，保留最新的几个
                    conversion_dirs.sort(key=lambda x: os.path.getmtime(os.path.join(output_dir, x)), reverse=True)
                    dirs_to_delete = conversion_dirs[keep_latest:]
                else:
                    dirs_to_delete = conversion_dirs
                
                for dir_name in dirs_to_delete:
                    try:
                        import shutil
                        shutil.rmtree(os.path.join(output_dir, dir_name))
                    except Exception:
                        pass
                
    except Exception as e:
        print(f"清理临时文件夹时出现错误: {str(e)}")