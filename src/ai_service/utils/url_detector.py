"""
URL 链接类型检测工具
自动识别链接的平台和类型
"""

import re
from typing import Dict, Optional, Literal


def detect_platform(url: str) -> Literal['douyin', 'tiktok', 'bilibili', 'unknown']:
    """
    检测链接所属平台
    
    Args:
        url: 视频链接
        
    Returns:
        平台类型: 'douyin', 'tiktok', 'bilibili', 'unknown'
    """
    url_lower = url.lower()
    
    if 'bilibili.com' in url_lower:
        return 'bilibili'
    elif 'tiktok.com' in url_lower or 'tiktok.co' in url_lower:
        return 'tiktok'
    elif 'douyin.com' in url_lower or 'iesdouyin.com' in url_lower:
        return 'douyin'
    else:
        return 'unknown'


def detect_link_type(url: str, platform: Optional[str] = None) -> Literal['video', 'mix', 'account', 'live', 'unknown']:
    """
    检测链接类型
    
    Args:
        url: 视频链接
        platform: 平台类型（可选，如果不提供会自动检测）
        
    Returns:
        链接类型: 'video', 'mix', 'account', 'live', 'unknown'
    """
    if platform is None:
        platform = detect_platform(url)
    
    url_lower = url.lower()
    
    # Bilibili 平台
    if platform == 'bilibili':
        # Bilibili 视频链接通常包含 /video/BV 或 /video/av
        if '/video/' in url_lower and ('bv' in url_lower or 'av' in url_lower):
            return 'video'
        elif '/space/' in url_lower or '/user/' in url_lower:
            return 'account'
        elif '/playlist/' in url_lower or '/medialist/' in url_lower:
            return 'mix'
        else:
            return 'video'  # 默认作为视频
    
    # TikTok/Douyin 平台
    elif platform in ['tiktok', 'douyin']:
        # 合集/Mix 链接
        if ('/collection/' in url_lower or 
            '/mix/' in url_lower or 
            '/video/' in url_lower and ('mix' in url_lower or 'collection' in url_lower)):
            return 'mix'
        
        # 用户主页链接
        elif ('/user/' in url_lower or 
              '/@' in url_lower or
              'sec_uid' in url_lower or
              'user_id' in url_lower or
              '/profile/' in url_lower):
            return 'account'
        
        # 直播链接
        elif '/live/' in url_lower or '/lives/' in url_lower:
            return 'live'
        
        # 单个视频链接（包含视频ID）
        elif re.search(r'/video/(\d+)', url_lower) or re.search(r'item_id=(\d+)', url_lower):
            return 'video'
        
        # 默认作为视频
        else:
            return 'video'
    
    # 未知平台
    else:
        return 'unknown'


def analyze_url(url: str) -> Dict[str, any]:
    """
    完整分析链接，返回平台和类型信息
    
    Args:
        url: 视频链接
        
    Returns:
        包含平台、类型、是否支持等信息的字典
    """
    platform = detect_platform(url)
    link_type = detect_link_type(url, platform)
    
    # 判断是否支持
    is_supported = platform in ['douyin', 'tiktok', 'bilibili']
    
    # 获取平台显示名称
    platform_names = {
        'douyin': '抖音',
        'tiktok': 'TikTok',
        'bilibili': 'Bilibili',
        'unknown': '未知平台'
    }
    
    # 获取类型显示名称
    type_names = {
        'video': '单个视频',
        'mix': '合集/合辑',
        'account': '用户主页',
        'live': '直播',
        'unknown': '未知类型'
    }
    
    result = {
        'platform': platform,
        'platform_name': platform_names.get(platform, '未知平台'),
        'type': link_type,
        'type_name': type_names.get(link_type, '未知类型'),
        'is_supported': is_supported,
        'url': url
    }
    
    # 提取额外的信息
    if platform == 'bilibili':
        # 提取 BV 号或 av 号
        bv_match = re.search(r'BV([a-zA-Z0-9]+)', url, re.IGNORECASE)
        av_match = re.search(r'av(\d+)', url, re.IGNORECASE)
        if bv_match:
            result['video_id'] = f"BV{bv_match.group(1)}"
        elif av_match:
            result['video_id'] = f"av{av_match.group(1)}"
    
    elif platform in ['douyin', 'tiktok']:
        # 提取视频ID
        video_id_match = re.search(r'/video/(\d+)', url)
        if video_id_match:
            result['video_id'] = video_id_match.group(1)
        
        # 提取用户ID
        user_match = re.search(r'/user/(\d+)', url)
        if user_match:
            result['user_id'] = user_match.group(1)
    
    return result

