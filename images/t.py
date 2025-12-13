from PIL import Image
import os

def resize_and_crop_to_square(image_path, output_size=720):
    """
    将图片裁剪成一个正方形，并调整大小到指定的尺寸。

    参数:
    image_path (str): 输入图片的路径。
    output_size (int): 目标正方形图片的边长（例如 720）。
    """
    try:
        # 1. 打开图片
        img = Image.open(image_path)
        original_width, original_height = img.size

        print(f"原始图片尺寸: {original_width}x{original_height}")

        # 2. 确定最大的正方形裁剪区域
        # 裁剪的边长取原始图片的较小边
        crop_size = min(original_width, original_height)
        
        # 计算裁剪区域的左上角和右下角坐标
        # 我们希望裁剪区域以图片中心为中心
        left = (original_width - crop_size) // 2
        top = (original_height - crop_size) // 2
        right = left + crop_size
        bottom = top + crop_size
        
        # 3. 裁剪图片
        cropped_img = img.crop((left, top, right, bottom))
        print(f"裁剪后的图片尺寸: {crop_size}x{crop_size}")

        # 4. 调整大小
        resized_img = cropped_img.resize((output_size, output_size))
        print(f"调整大小后的图片尺寸: {output_size}x{output_size}")

        # 5. 生成输出文件名
        # 假设原文件是 'zzl.jpg'，输出文件名为 'zzl_720x720.jpg'
        base_name, ext = os.path.splitext(image_path)
        output_path = f"{base_name}_{output_size}x{output_size}{ext}"

        # 6. 保存图片
        resized_img.save(output_path)
        print(f"图片已成功保存到: {output_path}")

    except FileNotFoundError:
        print(f"错误: 文件未找到，请检查路径: {image_path}")
    except Exception as e:
        print(f"处理图片时发生错误: {e}")

# --- 如何使用 ---
# 假设您将代码保存在同一目录下，并且您的图片名为 'zzl.jpg'
input_file_path = 'zzl.png'

# 调用函数进行处理，目标尺寸为 720x720
resize_and_crop_to_square(input_file_path, output_size=720)